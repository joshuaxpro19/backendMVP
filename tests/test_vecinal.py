"""Contrato del front de Vecinal Solidaria (fase 1: núcleo).

Ver `front/API-CONTRATO.md`. Estos tests fijan la forma exacta que espera el
frontend: rutas, `{token, usuario}`, `{items: [...]}` y los campos de
`Publicacion`.
"""

import base64
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PIXEL = base64.b64encode(
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xd9"
).decode()


def _telefono() -> str:
    return f"9{uuid.uuid4().int % 100000000:08d}"


def _cuenta(prefijo: str = "front") -> dict:
    """Registra y entra; devuelve los headers Bearer."""
    sufijo = uuid.uuid4().hex[:8]
    email = f"{prefijo}_{sufijo}@vecinal.test"
    r = client.post(
        "/api/registro",
        json={
            "nombre": "Ana Vecina",
            "email": email,
            "password": "123456",
            "telefono": _telefono(),
            "zona": "Piura Centro",
            "yape": "987654321",
            "plin": "",
            "acepta_privacidad": True,
        },
    )
    assert r.status_code == 201, r.text

    r = client.post("/api/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_registro_login_perfil():
    """Alta en JSON, login con {token, usuario} y perfil con `rol` en español."""
    headers = _cuenta("cuenta")

    perfil = client.get("/api/perfil", headers=headers).json()
    assert perfil["rol"] == "vecino"
    assert perfil["zona"] == "Piura Centro"
    assert perfil["telefono_verificado"] is False
    assert perfil["nombre"] == "Ana Vecina"
    assert len(perfil["telefono"]) == 9
    assert perfil["publicaciones"] == 0

    r = client.post("/api/login", json={"email": "no-existe@vecinal.test", "password": "x"})
    assert r.status_code == 401
    assert "detail" in r.json()


def test_editar_perfil():
    headers = _cuenta("perfil")
    nuevo_tel = _telefono()
    r = client.put(
        "/api/perfil",
        json={"nombre": "Ana Paredes", "telefono": nuevo_tel, "zona": "Castilla",
              "yape": "111222333", "plin": ""},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    perfil = client.get("/api/perfil", headers=headers).json()
    assert perfil["nombre"] == "Ana Paredes"
    assert perfil["zona"] == "Castilla"
    assert perfil["telefono"] == nuevo_tel


def test_zonas_salud_y_notificaciones():
    zonas = client.get("/api/zonas").json()
    assert isinstance(zonas, list) and len(zonas) >= 5
    assert {"nombre", "lat", "lng"} <= set(zonas[0])

    assert client.get("/api/salud").json()["status"] == "ok"

    headers = _cuenta("avisos")
    assert client.get("/api/notificaciones", headers=headers).json() == {"items": []}
    assert client.post("/api/notificaciones/leer", headers=headers).json()["ok"] is True


def test_publicaciones_ciclo_completo():
    """Crear, listar, leer, editar y borrar una publicación."""
    headers = _cuenta("pub")
    cuerpo = {
        "tipo": "servicio",
        "categoria": "gasfitería",
        "titulo": "Gasfitero para fugas",
        "descripcion": "Atiendo fugas en todo el centro.",
        "precio": "S/ 40.00",
        "stock": None,
        "medios_pago": "yape,efectivo",
        "politica_pago": "contra_entrega",
        "zona": "Piura Centro",
        "lat": -5.1945,
        "lng": -80.6328,
        "es_emergencia": False,
        "mostrar_contacto": True,
        "whatsapp": True,
        "telefono_whatsapp": "",
        "fotos": [],
        "client_id": f"c-{uuid.uuid4().hex}",
    }
    r = client.post("/api/publicaciones", json=cuerpo, headers=headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    # Idempotencia: el mismo client_id no duplica (cola offline del front)
    r_dup = client.post("/api/publicaciones", json=cuerpo, headers=headers)
    assert r_dup.json()["id"] == pid
    assert r_dup.json().get("duplicado") is True

    # Lista pública con lat/lng del sector -> ordenada por cercanía
    lista = client.get("/api/publicaciones?limit=30&orden=cercania&lat=-5.1945&lng=-80.6328").json()
    assert "items" in lista
    fila = next((x for x in lista["items"] if x["id"] == pid), None)
    assert fila is not None
    assert fila["titulo"] == "Gasfitero para fugas"
    assert fila["es_mio"] is False  # anónimo
    assert fila["creado"] > 0
    # Sin sesión no se revela contacto ni distancia
    assert fila["distancia_km"] is None
    assert fila["telefono"] is None
    assert fila["whatsapp"] is None
    assert fila["contacto_visible"] is False

    # Con sesión sí hay distancia y contacto
    con_sesion = client.get(
        "/api/publicaciones?limit=30&orden=cercania&lat=-5.1945&lng=-80.6328", headers=headers
    ).json()["items"]
    propia = next(x for x in con_sesion if x["id"] == pid)
    assert propia["distancia_km"] is not None
    assert propia["whatsapp"] and propia["whatsapp"].isdigit()

    # Detalle: anónimo sin contacto, autor con contacto
    detalle = client.get(f"/api/publicaciones/{pid}").json()
    assert detalle["telefono"] is None and detalle["whatsapp"] is None
    assert detalle["es_mio"] is False
    assert detalle["mi_trato"] is None
    detalle_mio = client.get(f"/api/publicaciones/{pid}", headers=headers).json()
    assert detalle_mio["whatsapp"] and detalle_mio["whatsapp"].isdigit()
    assert detalle_mio["es_mio"] is True

    # mis-publicaciones
    mias = client.get("/api/mis-publicaciones", headers=headers).json()
    assert isinstance(mias, list)
    propio = next(x for x in mias if x["id"] == pid)
    assert "cotizaciones" in propio

    # Editar (el front manda zona, que el backend de referencia ignoraba)
    r = client.patch(
        f"/api/publicaciones/{pid}", json={"zona": "Castilla", "estado": "pausada"},
        headers=headers,
    )
    assert r.status_code == 200
    assert client.get(f"/api/publicaciones/{pid}").json()["zona"] == "Castilla"
    # Pausada no aparece en la lista pública
    publicas = client.get("/api/publicaciones").json()["items"]
    assert all(x["id"] != pid for x in publicas)

    # Borrar (borrado suave)
    assert client.delete(f"/api/publicaciones/{pid}", headers=headers).status_code == 200
    assert client.get(f"/api/publicaciones/{pid}").status_code == 404


def test_publicaciones_filtros_del_front():
    headers = _cuenta("filtros")
    base = {"tipo": "favor_solicitado", "subtipo_favor": "prestamo",
            "categoria": "herramientas", "titulo": "Préstamo de andamio",
            "descripcion": "Lo presto el fin de semana.", "medios_pago": "intercambio",
            "zona": "Castilla", "fotos": []}
    r = client.post("/api/publicaciones", json=base, headers=headers)
    assert r.status_code == 201, r.text

    favores = client.get("/api/publicaciones?solo_favores=true&tipo_favor=prestamo").json()["items"]
    assert any(x["titulo"] == "Préstamo de andamio" for x in favores)
    assert all(str(x["tipo"]).startswith("favor") for x in favores)

    por_categoria = client.get("/api/publicaciones?categoria=herramientas").json()["items"]
    assert any(x["titulo"] == "Préstamo de andamio" for x in por_categoria)

    busca = client.get("/api/publicaciones?q=andamio").json()["items"]
    assert len(busca) >= 1

    emergencia = client.get("/api/publicaciones?emergencia=true").json()["items"]
    assert all(x["es_emergencia"] for x in emergencia)


def test_fotos_suben_y_se_sirven():
    headers = _cuenta("fotos")
    r = client.post("/api/fotos", json={"data": f"data:image/jpeg;base64,{PIXEL}"}, headers=headers)
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("/fotos/")

    descarga = client.get(url)
    assert descarga.status_code == 200
    assert descarga.content[:2] == b"\xff\xd8"  # JPEG

    # Sin sesión no se puede subir
    assert client.post("/api/fotos", json={"data": f"data:image/jpeg;base64,{PIXEL}"}).status_code == 401


def test_recomendar_y_reportar():
    autor = _cuenta("autor")
    otro = _cuenta("otro")
    pid = client.post(
        "/api/publicaciones",
        json={"tipo": "producto", "categoria": "alimentos", "titulo": "Miel de 1 kg",
              "descripcion": "Miel del valle.", "precio": "S/ 30.00", "stock": 5,
              "medios_pago": "efectivo", "zona": "Piura Centro", "fotos": []},
        headers=autor,
    ).json()["id"]

    # Recomendar incrementa vistos y se puede repetir sin duplicar
    r = client.post("/api/vistos", json={"publicacion_id": pid, "comentario": "Buena"},
                    headers=otro)
    assert r.status_code == 200
    assert r.json()["vistos"] == 1
    client.post("/api/vistos", json={"publicacion_id": pid}, headers=otro)
    assert client.get(f"/api/publicaciones/{pid}").json()["vistos"] == 1
    assert client.get(f"/api/publicaciones/{pid}", headers=otro).json()["ya_recomende"] is True

    # Reporte único por vecino
    r = client.post("/api/reportes", json={"publicacion_id": pid, "motivo": "Parece una estafa"},
                    headers=otro)
    assert r.status_code == 200
    r2 = client.post("/api/reportes", json={"publicacion_id": pid, "motivo": "Otra vez"},
                     headers=otro)
    assert r2.json()["mensaje"].startswith("Ya habías reportado")

    # No se puede recomendar/reportar lo propio
    assert client.post("/api/vistos", json={"publicacion_id": pid},
                       headers=autor).status_code == 400
    assert client.post("/api/reportes", json={"publicacion_id": pid, "motivo": "x"},
                       headers=autor).status_code == 400


def test_emergencia_tablero_y_directorio():
    tablero = client.get("/api/emergencia").json()
    assert set(tablero) == {"activo", "motivo"}

    directorio = client.get("/api/emergencia/directorio").json()["items"]
    assert {"id", "nombre", "detalle", "telefono"} <= set(directorio[0])

    headers = _cuenta("emerg")
    r = client.post("/api/emergencia/activar", json={"activo": True, "motivo": "Inundación"},
                    headers=headers)
    assert r.status_code == 403  # solo moderador

    # El rol del MVP es `moderator`; el front lo traduce a "moderador"
    from app.domain.models.role import Roles
    from app.domain.models.user import User
    from app.infrastructure.database.connection import SessionLocal

    db = SessionLocal()
    email = client.get("/api/perfil", headers=headers).json()["email"]
    db.query(User).filter(User.email == email).update({"role": Roles.MOD})
    db.commit()
    db.close()

    r = client.post("/api/emergencia/activar", json={"activo": True, "motivo": "Inundación"},
                    headers=headers)
    assert r.status_code == 200
    assert client.get("/api/emergencia").json() == {"activo": True, "motivo": "Inundación"}

    # Se deja apagado para no ensuciar el resto de la suite
    client.post("/api/emergencia/activar", json={"activo": False, "motivo": ""}, headers=headers)
    assert client.get("/api/emergencia").json()["activo"] is False


def test_401_sin_token_en_rutas_protegidas():
    for ruta in ("/api/perfil", "/api/mis-publicaciones", "/api/notificaciones"):
        assert client.get(ruta).status_code == 401
    assert client.post(
        "/api/publicaciones", json={"tipo": "servicio", "titulo": "x"}
    ).status_code == 401


# --- reglas de negocio migradas del proyecto original ----------------------


def _pub_valida(**extra) -> dict:
    cuerpo = {
        "tipo": "servicio",
        "categoria": "gasfitería",
        "titulo": "Servicio de prueba",
        "descripcion": "Descripción suficientemente larga.",
        "precio": "S/ 30.00",
        "medios_pago": "efectivo",
        "zona": "Piura Centro",
        "fotos": [],
    }
    cuerpo.update(extra)
    return cuerpo


def test_registro_reglas_de_cuenta():
    headers = _cuenta("reglas")
    base = {
        "nombre": "Vecino Prueba",
        "email": f"otro_{uuid.uuid4().hex[:8]}@vecinal.test",
        "password": "123456",
        "telefono": _telefono(),
        "zona": "Piura Centro",
        "yape": "",
        "plin": "",
        "acepta_privacidad": True,
    }

    # Aviso de privacidad obligatorio
    r = client.post("/api/registro", json={**base, "acepta_privacidad": False})
    assert r.status_code == 400
    assert "privacidad" in r.json()["detail"].lower()

    # Zona de la lista
    r = client.post("/api/registro", json={**base, "zona": "Zona Inventada"})
    assert r.status_code == 400
    assert "zona" in r.json()["detail"].lower()

    # Yape de 9 dígitos
    r = client.post("/api/registro", json={**base, "yape": "123"})
    assert r.status_code == 400
    assert "Yape" in r.json()["detail"]

    # Perfil: zona y Yape también se validan
    assert client.put("/api/perfil", json={"zona": "Nada"}, headers=headers).status_code == 400
    assert client.put("/api/perfil", json={"yape": "1"}, headers=headers).status_code == 400


def test_login_bloqueo_tras_5_fallos():
    email = f"bloqueo_{uuid.uuid4().hex[:8]}@vecinal.test"
    client.post(
        "/api/registro",
        json={
            "nombre": "Vecino Bloqueo",
            "email": email,
            "password": "123456",
            "telefono": _telefono(),
            "zona": "Piura Centro",
            "acepta_privacidad": True,
        },
    )

    for _ in range(5):
        r = client.post("/api/login", json={"email": email, "password": "mala"})
        assert r.status_code == 401

    r = client.post("/api/login", json={"email": email, "password": "mala"})
    assert r.status_code == 429
    assert "Demasiados intentos" in r.json()["detail"]

    # Ni con la contraseña buena mientras está bloqueado
    r = client.post("/api/login", json={"email": email, "password": "123456"})
    assert r.status_code == 429


def test_rate_limit_de_login():
    for _ in range(30):
        r = client.post("/api/login", json={"email": "nadie@vecinal.test", "password": "x"})
        assert r.status_code == 401
    r = client.post("/api/login", json={"email": "nadie@vecinal.test", "password": "x"})
    assert r.status_code == 429
    assert "Demasiadas solicitudes" in r.json()["detail"]


def test_publicacion_validaciones():
    headers = _cuenta("valida")

    r = client.post("/api/publicaciones", json=_pub_valida(categoria="inventada"), headers=headers)
    assert r.status_code == 400 and r.json()["detail"] == "Categoría inválida"

    r = client.post("/api/publicaciones", json=_pub_valida(descripcion="abc"), headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "El título y la descripción son obligatorios"

    r = client.post("/api/publicaciones", json=_pub_valida(medios_pago="bitcoin"), headers=headers)
    assert r.status_code == 400 and r.json()["detail"] == "Medio de pago inválido"

    r = client.post(
        "/api/publicaciones",
        json=_pub_valida(tipo="favor_ofrecido", subtipo_favor=""),
        headers=headers,
    )
    assert r.status_code == 400 and r.json()["detail"] == "Elige un tipo de favor válido"

    # Sector libre sin GPS
    r = client.post(
        "/api/publicaciones",
        json=_pub_valida(zona="Zona Inventada", lat=None, lng=None),
        headers=headers,
    )
    assert r.status_code == 400
    assert "comparte tu ubicación" in r.json()["detail"].lower()


def test_movilidad_protege_al_menor():
    headers = _cuenta("movilidad")
    base = _pub_valida(
        tipo="favor_ofrecido",
        subtipo_favor="movilidad",
        categoria="movilidad",
        franja_horaria="7:00 a 8:00",
        punto_encuentro="Parque Central",
        checklist_ok=True,
    )

    r = client.post(
        "/api/publicaciones",
        json={**base, "descripcion": "Llevo a los niños al colegio San José."},
        headers=headers,
    )
    assert r.status_code == 400
    assert "colegio" in r.json()["detail"].lower()

    assert client.post(
        "/api/publicaciones", json={**base, "franja_horaria": ""}, headers=headers
    ).status_code == 400
    assert client.post(
        "/api/publicaciones", json={**base, "punto_encuentro": ""}, headers=headers
    ).status_code == 400
    assert client.post(
        "/api/publicaciones", json={**base, "checklist_ok": False}, headers=headers
    ).status_code == 400

    assert client.post("/api/publicaciones", json=base, headers=headers).status_code == 201


def test_vistos_estado_y_limite_diario():
    autor = _cuenta("vautor")
    otro = _cuenta("votro")

    pausada = client.post(
        "/api/publicaciones", json=_pub_valida(titulo="Pausada"), headers=autor
    ).json()["id"]
    client.patch(f"/api/publicaciones/{pausada}", json={"estado": "pausada"}, headers=autor)
    r = client.post("/api/vistos", json={"publicacion_id": pausada}, headers=otro)
    assert r.status_code == 400
    assert "activas o cerradas" in r.json()["detail"]

    # 5 al día como máximo
    for i in range(5):
        pid = client.post(
            "/api/publicaciones", json=_pub_valida(titulo=f"Recomendable {i}"), headers=autor
        ).json()["id"]
        assert client.post(
            "/api/vistos", json={"publicacion_id": pid}, headers=otro
        ).status_code == 200

    sexta = client.post(
        "/api/publicaciones", json=_pub_valida(titulo="Sexta"), headers=autor
    ).json()["id"]
    r = client.post("/api/vistos", json={"publicacion_id": sexta}, headers=otro)
    assert r.status_code == 429
    assert "5 vistos" in r.json()["detail"]


def test_patch_version_y_publicacion_cerrada():
    headers = _cuenta("version")
    pid = client.post("/api/publicaciones", json=_pub_valida(), headers=headers).json()["id"]

    # Versión desactualizada -> 409
    r = client.patch(
        f"/api/publicaciones/{pid}", json={"titulo": "Nuevo", "version": 99}, headers=headers
    )
    assert r.status_code == 409
    assert "versión" in r.json()["detail"]

    # Versión correcta -> 200
    assert client.patch(
        f"/api/publicaciones/{pid}", json={"titulo": "Nuevo", "version": 1}, headers=headers
    ).status_code == 200

    # Una publicación cerrada ya no se edita
    assert client.patch(
        f"/api/publicaciones/{pid}", json={"estado": "cerrada"}, headers=headers
    ).status_code == 200
    r = client.patch(f"/api/publicaciones/{pid}", json={"titulo": "Otra"}, headers=headers)
    assert r.status_code == 400
    assert "cerrada" in r.json()["detail"]


def test_ubicacion_aproximada_es_el_centro_del_sector():
    headers = _cuenta("zona")
    pid = client.post(
        "/api/publicaciones", json=_pub_valida(zona="Castilla", lat=None, lng=None), headers=headers
    ).json()["id"]

    detalle = client.get(f"/api/publicaciones/{pid}", headers=headers).json()
    assert detalle["ubicacion_aproximada"] is True
    assert detalle["lat_publica"] is not None  # se guardó con jitter desde el centro


def test_cabeceras_de_seguridad():
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "permissions-policy" in r.headers


def test_scraped_aparece_en_economia_local():
    """Los posts de Facebook salen en el feed con su teléfono de contacto."""
    from app.domain.models.scraped_post import ScrapedPost
    from app.infrastructure.database.connection import SessionLocal

    db = SessionLocal()
    post = ScrapedPost(
        author="Carlos Gasfitero",
        source_name="Servicios Piura",
        source_type="grupo",
        content="Gasfitero 24 horas, fugas y destapes. Llamar al 987654321.",
        city="Piura Centro",
        phones=["987654321"],
        whatsapp=["987654321"],
        image_urls=[],
        image_files=[],
        phone_count=1,
        content_hash=uuid.uuid4().hex,
        query_origen="gasfitero Piura",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    sid = str(post.id)
    db.close()

    # Anónimo: aparece, pero sin contacto (misma regla de privacidad)
    items = client.get("/api/publicaciones?limit=100&q=Gasfitero 24 horas").json()["items"]
    fila = next((x for x in items if x["id"] == sid), None)
    assert fila is not None
    assert fila["origen"] == "scraping"
    assert fila["categoria"] == "gasfitería"  # deducida de la búsqueda
    assert fila["whatsapp"] is None
    assert fila["es_mio"] is False

    # Con sesión: el número extraído se usa para contactar
    headers = _cuenta("scraped")
    con_sesion = client.get(
        "/api/publicaciones?limit=100&q=Gasfitero 24 horas", headers=headers
    ).json()["items"]
    fila = next(x for x in con_sesion if x["id"] == sid)
    assert fila["whatsapp"] == "987654321"

    detalle = client.get(f"/api/publicaciones/{sid}", headers=headers).json()
    assert detalle["origen"] == "scraping"
    assert detalle["whatsapp"] == "987654321"
    assert detalle["url_origen"] is None

    # Favores y emergencias no mezclan contenido de Facebook
    favores = client.get("/api/publicaciones?solo_favores=true&limit=100").json()["items"]
    assert all(x["origen"] != "scraping" for x in favores)
    emergencias = client.get("/api/publicaciones?emergencia=true&limit=100").json()["items"]
    assert all(x["origen"] != "scraping" for x in emergencias)

    # No se recomienda ni reporta contenido de Facebook
    assert client.post("/api/vistos", json={"publicacion_id": sid}, headers=headers).status_code == 400
    assert client.post(
        "/api/reportes", json={"publicacion_id": sid, "motivo": "x"}, headers=headers
    ).status_code == 400


def test_quitar_visto_es_toggle():
    autor = _cuenta("toggleautor")
    otro = _cuenta("toggleotro")
    pid = client.post("/api/publicaciones", json=_pub_valida(), headers=autor).json()["id"]

    r = client.post("/api/vistos", json={"publicacion_id": pid}, headers=otro)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "vistos": 1, "ya_recomende": True}

    r = client.delete(f"/api/vistos?publicacion_id={pid}", headers=otro)
    assert r.status_code == 200
    assert r.json()["vistos"] == 0
    assert r.json()["ya_recomende"] is False

    # Se puede volver a recomendar
    r = client.post("/api/vistos", json={"publicacion_id": pid}, headers=otro)
    assert r.json()["vistos"] == 1


def test_editar_mi_publicacion_con_fotos_y_contacto():
    """El autor puede cambiar datos, fotos y WhatsApp de su publicación."""
    headers = _cuenta("editar")
    pid = client.post("/api/publicaciones", json=_pub_valida(), headers=headers).json()["id"]

    foto = client.post(
        "/api/fotos", json={"data": f"data:image/jpeg;base64,{PIXEL}"}, headers=headers
    ).json()["url"]

    r = client.patch(
        f"/api/publicaciones/{pid}",
        json={
            "titulo": "Servicio editado",
            "descripcion": "Descripción nueva y más larga.",
            "precio": "S/ 55.00",
            "categoria": "electricidad",
            "medios_pago": "yape,efectivo",
            "fotos": [foto],
            "whatsapp": True,
            "telefono_whatsapp": "987654321",
            "mostrar_contacto": True,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text

    d = client.get(f"/api/publicaciones/{pid}", headers=headers).json()
    assert d["titulo"] == "Servicio editado"
    assert d["descripcion"].startswith("Descripción nueva")
    assert d["precio"] == "S/ 55.00"
    assert d["categoria"] == "electricidad"
    assert d["fotos"] == [foto]
    assert d["whatsapp"] == "987654321"

    # Validaciones al editar
    assert client.patch(
        f"/api/publicaciones/{pid}", json={"categoria": "inventada"}, headers=headers
    ).status_code == 400
    assert client.patch(
        f"/api/publicaciones/{pid}", json={"medios_pago": "bitcoin"}, headers=headers
    ).status_code == 400
    assert client.patch(
        f"/api/publicaciones/{pid}", json={"zona": "Nada"}, headers=headers
    ).status_code == 400

    # Editar un servicio manda subtipo_favor=null (como la app): no debe fallar
    r = client.patch(
        f"/api/publicaciones/{pid}",
        json={
            "titulo": "Servicio editado 2",
            "descripcion": "Otra descripción válida.",
            "precio": "S/ 60.00",
            "categoria": "gasfitería",
            "subtipo_favor": None,
            "medios_pago": "efectivo",
            "politica_pago": "contra_entrega",
            "necesidad": None,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_revision_con_ia_clasifica_y_limpia_el_feed(monkeypatch):
    """La IA aprueba servicios y descarta basura; el feed solo muestra aprobados."""
    from app.domain.models.scraped_post import ScrapedPost
    from app.infrastructure.database.connection import SessionLocal
    from app.services import ia_service

    db = SessionLocal()
    servicio = ScrapedPost(
        author="Gasfitero Real",
        source_name="Servicios Piura",
        content="Gasfitero 24 horas, fugas y destapes. Llamar al 988777666.",
        city="Piura",
        phones=[],
        whatsapp=[],
        image_urls=[],
        image_files=[],
        phone_count=0,
        content_hash=uuid.uuid4().hex,
        query_origen="gasfitero Piura",
    )
    basura = ScrapedPost(
        author="Meme",
        source_name="Grupo de memes",
        content="Mira este meme, ver más",
        city="Piura",
        phones=[],
        whatsapp=[],
        image_urls=[],
        image_files=[],
        phone_count=0,
        content_hash=uuid.uuid4().hex,
        query_origen="",
    )
    db.add_all([servicio, basura])
    db.commit()
    db.refresh(servicio)
    db.refresh(basura)
    id_servicio, id_basura = str(servicio.id), str(basura.id)
    db.close()

    def falso(api_key, modelo, texto, imagen):
        if "Gasfitero" in texto:
            return {
                "es_servicio": True,
                "motivo": "Ofrece gasfitería con teléfono",
                "titulo": "Gasfitero con IA",
                "descripcion": "Destapes y fugas, atención 24 h.",
                "categoria": "gasfitería",
                "telefono": "988777666",
                "ubicacion": "Piura Centro",
            }
        return {
            "es_servicio": False,
            "motivo": "Es un meme, no ofrece nada",
            "titulo": "",
            "descripcion": "",
            "categoria": "otros",
            "telefono": None,
            "ubicacion": None,
        }

    monkeypatch.setattr(ia_service, "_llamar_openrouter", falso)

    # Limpia cualquier key que haya quedado de una corrida anterior
    from app.domain.models.reporte import Ajuste

    db = SessionLocal()
    db.query(Ajuste).filter(Ajuste.clave == "openrouter_api_key").delete()
    db.commit()
    db.close()

    headers = _cuenta("ia")

    # Sin API key -> 400
    r = client.post("/api/ia/revisar", json={"limite": 5}, headers=headers)
    assert r.status_code == 400

    # Guardar la key
    r = client.put(
        "/api/ia/config", json={"api_key": "sk-or-v1-test", "modelo": "google/gemini-2.5-flash"},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["configurada"] is True

    config = client.get("/api/ia/config", headers=headers).json()
    assert config["configurada"] is True
    assert "api_key" not in config  # nunca se devuelve la clave

    # Revisar (puede haber otros pendientes de la BD de pruebas)
    r = client.post("/api/ia/revisar", json={"limite": 15}, headers=headers)
    assert r.status_code == 200, r.text
    resumen = r.json()
    assert resumen["revisados"] >= 2
    assert resumen["aprobados"] >= 1
    assert resumen["rechazados"] >= 1

    # El aprobado aparece con los datos de la IA y su teléfono
    items = client.get("/api/publicaciones?limit=100", headers=headers).json()["items"]
    aprobado = next((x for x in items if x["id"] == id_servicio), None)
    assert aprobado is not None
    assert aprobado["titulo"] == "Gasfitero con IA"
    assert aprobado["categoria"] == "gasfitería"
    assert aprobado["whatsapp"] == "988777666"

    # El rechazado desaparece del feed
    assert all(x["id"] != id_basura for x in items)

    # Y sigue accesible por detalle (no rompe enlaces guardados)
    assert client.get(f"/api/publicaciones/{id_basura}", headers=headers).status_code == 200


def test_registro_y_login_por_celular():
    """El alta no pide correo: celular + contraseña de solo dígitos (mín. 6)."""
    telefono = f"9{uuid.uuid4().int % 100000000:08d}"

    r = client.post(
        "/api/registro",
        json={
            "nombre": "Vecino Celular",
            "telefono": telefono,
            "password": "123456",
            "zona": "Piura Centro",
            "acepta_privacidad": True,
        },
    )
    assert r.status_code == 201, r.text

    # Contraseña con letras -> rechazada
    r = client.post(
        "/api/registro",
        json={
            "nombre": "Vecino Letras",
            "telefono": f"9{uuid.uuid4().int % 100000000:08d}",
            "password": "abc123",
            "zona": "Piura Centro",
            "acepta_privacidad": True,
        },
    )
    assert r.status_code == 422

    # Contraseña corta -> rechazada
    r = client.post(
        "/api/registro",
        json={
            "nombre": "Vecino Corto",
            "telefono": f"9{uuid.uuid4().int % 100000000:08d}",
            "password": "12345",
            "zona": "Piura Centro",
            "acepta_privacidad": True,
        },
    )
    assert r.status_code == 422

    # Celular repetido -> 409
    r = client.post(
        "/api/registro",
        json={
            "nombre": "Vecino Repetido",
            "telefono": telefono,
            "password": "654321",
            "zona": "Piura Centro",
            "acepta_privacidad": True,
        },
    )
    assert r.status_code == 409

    # Login con celular
    r = client.post("/api/login", json={"telefono": telefono, "password": "123456"})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["telefono"] == telefono

    # Login sin identificador -> 422
    assert client.post("/api/login", json={"password": "123456"}).status_code == 422
