"""Pruebas del scraping (INDECI) y de la importación del catálogo (OSM).

No tocan la red: el HTML y el JSON de Overpass se simulan con datos fijos.
Las pruebas de base de datos usan la misma conexión de DATABASE_URL y limpian
lo que crean, para poder repetirlas sin acumular registros.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.domain.models.category import ProductCategory, ServiceCategory
from app.domain.models.news import NewsItem
from app.domain.models.product import Product
from app.domain.models.role import Roles
from app.domain.models.service import Service
from app.domain.models.user import User
from app.infrastructure.database.connection import SessionLocal
from app.main import app
from app.scraping.indeci import guardar_indeci, parsear_fecha, parsear_indeci
from app.scraping.osm import construir_consulta, importar_lugares, mapear_lugar
from app.usecases.auth import hash_password

client = TestClient(app)

HTML_INDECI = """
<html><body>
  <div class="box-alerts alerts-slick">
    <article>
      <h2><a href="/informe/reporte-15663">REPORTE COMPLEMENTARIO N.° 15663 – 8/11/2026 / COEN – INDECI</a></h2>
      <a class="btn-download" href="/storage/reporte-15663.pdf">Descargar</a>
    </article>
    <article>
      <h2><a href="/informe/reporte-15663">REPORTE COMPLEMENTARIO N.° 15663 – 8/11/2026 / COEN – INDECI</a></h2>
    </article>
    <article>
      <h2>Sin enlace</h2>
    </article>
    <article>
      <h3><a href="/informe/aviso-1121">AVISO METEOROLÓGICO – 08-11-2026</a></h3>
    </article>
    <article>
      <h2><a href="/informe/nota-prensa">NOTA DE PRENSA SOBRE CAPACITACIÓN</a></h2>
    </article>
  </div>
</body></html>
"""


# --------------------------------------------------------------------------
# INDECI
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("REPORTE N.° 1 – 8/11/2026", (2026, 11, 8)),
        ("BOLETÍN 07-11-2026", (2026, 11, 7)),
        ("AVISO – 8 de noviembre de 2026", (2026, 11, 8)),
        ("REPORTE – 06 DE NOVIEMBRE DE 2026", (2026, 11, 6)),
    ],
)
def test_parsear_fecha_formatos(texto, esperado):
    fecha = parsear_fecha(texto)
    assert fecha is not None
    assert (fecha.year, fecha.month, fecha.day) == esperado


def test_parsear_fecha_sin_fecha_devuelve_none():
    assert parsear_fecha("REPORTE SIN FECHA") is None
    assert parsear_fecha("") is None


def test_parsear_indeci_normaliza_y_deduplica():
    items = parsear_indeci(HTML_INDECI, base_url="https://portal.indeci.gob.pe/informe/informe-de-peligros/")

    # Dos artículos válidos: el duplicado por URL y la nota de prensa se descartan.
    assert len(items) == 2
    reporte, aviso = items
    assert reporte["category"] == "reporte"
    assert reporte["external_id"] == "https://portal.indeci.gob.pe/informe/reporte-15663"
    assert reporte["pdf_url"] == "https://portal.indeci.gob.pe/storage/reporte-15663.pdf"
    assert reporte["published_at"].date().isoformat() == "2026-11-08"
    assert aviso["category"] == "aviso"
    assert aviso["pdf_url"] is None
    assert items[0]["published_at"] >= items[1]["published_at"]


def test_guardar_indeci_es_idempotente():
    sufijo = uuid.uuid4().hex[:8]
    external = f"test:{sufijo}"
    noticias = [
        {
            "source": "TEST_INDECI",
            "external_id": external,
            "title": "Reporte de prueba",
            "summary": None,
            "url": "https://example.test/reporte",
            "pdf_url": None,
            "category": "reporte",
            "published_at": None,
        }
    ]
    db = SessionLocal()
    try:
        primera = guardar_indeci(db, noticias)
        assert primera["created"] == 1 and primera["updated"] == 0

        noticias[0]["title"] = "Reporte de prueba (actualizado)"
        segunda = guardar_indeci(db, noticias)
        assert segunda["created"] == 0 and segunda["updated"] == 1

        guardado = db.query(NewsItem).filter(NewsItem.external_id == external).one()
        assert guardado.title == "Reporte de prueba (actualizado)"
    finally:
        db.query(NewsItem).filter(NewsItem.external_id == external).delete()
        db.commit()
        db.close()


def test_endpoint_news_lista_y_filtra():
    sufijo = uuid.uuid4().hex[:8]
    external = f"test-endpoint:{sufijo}"
    db = SessionLocal()
    try:
        db.add(
            NewsItem(
                source="TEST_INDECI",
                external_id=external,
                title="Aviso visible por API",
                url="https://example.test/aviso",
                category="aviso",
            )
        )
        db.commit()

        respuesta = client.get("/api/news", params={"source": "test_indeci", "page_size": 100})
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["total"] >= 1
        assert any(item["external_id"] == external for item in cuerpo["items"])

        filtrado = client.get("/api/news", params={"category": "reporte", "page_size": 100})
        assert all(item["category"] == "reporte" for item in filtrado.json()["items"])

        assert client.get("/api/news", params={"page": 0}).status_code == 422
    finally:
        db.query(NewsItem).filter(NewsItem.external_id == external).delete()
        db.commit()
        db.close()


# --------------------------------------------------------------------------
# OpenStreetMap
# --------------------------------------------------------------------------


def test_mapear_lugar_supermercado_es_producto():
    elemento = {
        "type": "node",
        "id": 123,
        "lat": -5.19,
        "lon": -80.63,
        "tags": {
            "name": "Plaza Vea",
            "shop": "supermarket",
            "addr:street": "Av. Sánchez Cerro",
            "addr:housenumber": "123",
            "phone": "+51 73 123456",
        },
    }
    lugar = mapear_lugar(elemento)
    assert lugar["kind"] == "product"
    assert lugar["category"] == "alimentos"
    assert lugar["title"] == "Plaza Vea"
    assert lugar["address"] == "Av. Sánchez Cerro 123"
    assert lugar["contact_phone"] == "+51 73 123456"
    assert lugar["source_url"] == "https://www.openstreetmap.org/node/123"


def test_mapear_lugar_gasfitero_es_servicio():
    lugar = mapear_lugar(
        {
            "type": "way",
            "id": 456,
            "center": {"lat": -5.2, "lon": -80.6},
            "tags": {"name": "Gasfitería Don José", "craft": "plumber"},
        }
    )
    assert lugar["kind"] == "service"
    assert lugar["category"] == "plomeria"
    assert lugar["latitude"] == -5.2


def test_mapear_lugar_descarta_sin_nombre_y_oficinas_ignoradas():
    assert mapear_lugar({"type": "node", "id": 1, "tags": {"shop": "supermarket"}}) is None
    assert (
        mapear_lugar(
            {"type": "node", "id": 2, "tags": {"name": "Municipalidad", "office": "government"}}
        )
        is None
    )
    # Una notaría sí es un servicio del barrio (categoría «otro»).
    notaria = mapear_lugar(
        {"type": "node", "id": 3, "tags": {"name": "Notaría", "office": "notary"}}
    )
    assert notaria is not None
    assert notaria["kind"] == "service"
    assert notaria["category"] == "otro"


def test_construir_consulta_incluye_radio_y_limite():
    consulta = construir_consulta(-5.1945, -80.6328, 1500, 25)
    assert "around:1500,-5.1945,-80.6328" in consulta
    assert "out center tags 25;" in consulta


def _crear_usuario_prueba(db) -> User:
    sufijo = uuid.uuid4().hex[:8]
    usuario = User(
        dni=f"T{sufijo}"[:20],
        phone=f"+5199{sufijo[:6].translate(str.maketrans('abcdef', '123456'))}",
        username=f"test_osm_{sufijo}",
        email=f"test_osm_{sufijo}@example.test",
        hashed_password=hash_password("Password123!"),
        full_name="Usuario de prueba OSM",
        role=Roles.USER,
        is_active=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_importar_lugares_crea_y_actualiza_sin_duplicar():
    sufijo = uuid.uuid4().hex[:8]
    externos = [f"test-osm:{sufijo}:1", f"test-osm:{sufijo}:2"]
    db = SessionLocal()
    usuario = _crear_usuario_prueba(db)
    lugares = [
        {
            "kind": "service",
            "title": "Gasfitería de prueba",
            "description": "Servicio importado en la prueba",
            "category": "plomeria",
            "latitude": -5.2,
            "longitude": -80.6,
            "address": "Calle Falsa 123",
            "contact_phone": None,
            "contact_website": None,
            "source": "test_osm",
            "source_url": "https://www.openstreetmap.org/node/1",
            "external_id": externos[0],
            "price_note": "Precio a consultar",
        },
        {
            "kind": "product",
            "title": "Bodega de prueba",
            "description": "Producto importado en la prueba",
            "category": "alimentos",
            "latitude": -5.2,
            "longitude": -80.6,
            "address": None,
            "contact_phone": None,
            "contact_website": None,
            "source": "test_osm",
            "source_url": "https://www.openstreetmap.org/node/2",
            "external_id": externos[1],
            "price_note": "Precio a consultar",
        },
    ]
    try:
        primera = importar_lugares(db, lugares, usuario.id)
        assert primera == {"created": 2, "updated": 0, "total": 2}

        lugares[0]["title"] = "Gasfitería de prueba (renombrada)"
        segunda = importar_lugares(db, lugares, usuario.id)
        assert segunda == {"created": 0, "updated": 2, "total": 2}

        servicio = db.query(Service).filter(Service.external_id == externos[0]).one()
        producto = db.query(Product).filter(Product.external_id == externos[1]).one()
        assert servicio.title == "Gasfitería de prueba (renombrada)"
        assert servicio.category == ServiceCategory.PLUMBING
        assert producto.category == ProductCategory.FOOD
        assert servicio.price_per_hour == 0.0
        assert producto.stock == 0

        assert db.query(Service).filter(Service.external_id == externos[0]).count() == 1
        assert db.query(Product).filter(Product.external_id == externos[1]).count() == 1
    finally:
        db.query(Service).filter(Service.source == "test_osm").delete()
        db.query(Product).filter(Product.source == "test_osm").delete()
        db.query(User).filter(User.id == usuario.id).delete()
        db.commit()
        db.close()
