"""Importación de un catálogo inicial desde OpenStreetMap (Overpass API).

OpenStreetMap es datos abiertos bajo licencia ODbL. Se usa su API pública
Overpass, no se scrapea ninguna red social ni se saltan protecciones.
"""

from __future__ import annotations

from typing import Optional

import httpx

from app.config.settings import settings

USER_AGENT = "VecinalSolidaria/1.0 (+https://github.com/Pierre-code189/app-vecinal-mobile)"

# Categorías de servicio de backendMVP
SERVICE_BY_CRAFT = {
    "plumber": "plomeria",
    "electrician": "electricidad",
    "cleaner": "limpieza",
    "carpenter": "carpinteria",
    "joiner": "carpinteria",
    "gardener": "jardineria",
}

SERVICE_BY_AMENITY = {
    "restaurant": "otro",
    "cafe": "otro",
    "fast_food": "otro",
    "food_court": "otro",
    "dentist": "otro",
    "clinic": "otro",
    "doctors": "otro",
    "veterinary": "otro",
    "car_repair": "otro",
    "bicycle_repair_station": "otro",
}

SERVICE_BY_SHOP = {
    "laundry": "limpieza",
    "dry_cleaning": "limpieza",
    "copyshop": "otro",
}

PRODUCT_BY_SHOP = {
    "supermarket": "alimentos",
    "convenience": "alimentos",
    "greengrocer": "alimentos",
    "butcher": "alimentos",
    "bakery": "alimentos",
    "deli": "alimentos",
    "seafood": "alimentos",
    "beverages": "alimentos",
    "cheese": "alimentos",
    "clothes": "ropa",
    "shoes": "ropa",
    "fashion": "ropa",
    "electronics": "electronica",
    "mobile_phone": "electronica",
    "computer": "electronica",
    "hifi": "electronica",
    "furniture": "muebles",
    "interior_decoration": "muebles",
    "hardware": "herramientas",
    "doityourself": "herramientas",
    "tools": "herramientas",
    "paint": "herramientas",
    "books": "libros",
    "stationery": "libros",
}

PRODUCT_BY_AMENITY = {
    "marketplace": "alimentos",
    "pharmacy": "otro",
    "fuel": "otro",
}

# Oficinas que no aportan al catálogo vecinal.
OFFICE_SKIP = {"government", "diplomatic", "administrative", "company", "bank"}


def _texto(tags: dict, *claves: str) -> Optional[str]:
    for clave in claves:
        valor = tags.get(clave)
        if valor:
            return str(valor).strip()
    return None


def _direccion(tags: dict) -> Optional[str]:
    calle = tags.get("addr:street")
    numero = tags.get("addr:housenumber")
    if calle and numero:
        return f"{calle} {numero}"
    return calle or tags.get("addr:full")


def _descripcion(tags: dict, nombre: str) -> str:
    propia = tags.get("description")
    if propia:
        return propia
    return (
        f"{nombre} — negocio local registrado en OpenStreetMap. "
        "Datos abiertos; la información puede estar desactualizada."
    )


def mapear_lugar(elemento: dict) -> Optional[dict]:
    """Convierte un elemento Overpass en datos para Service o Product."""
    tags = elemento.get("tags") or {}
    nombre = _texto(tags, "name", "operator")
    if not nombre:
        return None

    centro = elemento.get("center") or {}
    lat = elemento.get("lat", centro.get("lat"))
    lon = elemento.get("lon", centro.get("lon"))

    tipo = elemento.get("type")
    osm_id = elemento.get("id")
    if not tipo or osm_id is None:
        return None

    shop = tags.get("shop")
    craft = tags.get("craft")
    amenity = tags.get("amenity")
    office = tags.get("office")

    kind = None
    categoria = "otro"

    if shop in SERVICE_BY_SHOP:
        kind = "service"
        categoria = SERVICE_BY_SHOP[shop]
    elif shop:
        kind = "product"
        categoria = PRODUCT_BY_SHOP.get(shop, "otro")
    elif craft:
        kind = "service"
        categoria = SERVICE_BY_CRAFT.get(craft, "otro")
    elif amenity in SERVICE_BY_AMENITY:
        kind = "service"
        categoria = SERVICE_BY_AMENITY[amenity]
    elif amenity in PRODUCT_BY_AMENITY:
        kind = "product"
        categoria = PRODUCT_BY_AMENITY[amenity]
    elif office:
        if office in OFFICE_SKIP:
            return None
        kind = "service"
        categoria = "otro"

    if not kind:
        return None

    externo = f"osm:{tipo}/{osm_id}"
    return {
        "kind": kind,
        "title": nombre[:200],
        "description": _descripcion(tags, nombre),
        "category": categoria,
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lon) if lon is not None else None,
        "address": (_direccion(tags) or "")[:255] or None,
        "contact_phone": _texto(tags, "phone", "contact:phone", "mobile"),
        "contact_website": _texto(tags, "website", "contact:website"),
        "source": "openstreetmap",
        "source_url": f"https://www.openstreetmap.org/{tipo}/{osm_id}",
        "external_id": externo,
        "price_note": "Precio a consultar · stock no informado",
    }


def construir_consulta(lat: float, lng: float, radio_m: int, max_items: int) -> str:
    radio = int(radio_m)
    limite = int(max_items)
    return f"""
[out:json][timeout:60];
(
  nwr["shop"](around:{radio},{lat},{lng});
  nwr["craft"](around:{radio},{lat},{lng});
  nwr["office"](around:{radio},{lat},{lng});
  nwr["amenity"~"restaurant|cafe|fast_food|food_court|pharmacy|marketplace|medical_clinic|clinic|dentist|doctors|veterinary|car_repair|fuel|bicycle_repair_station"](around:{radio},{lat},{lng});
);
out center tags {limite};
""".strip()


def obtener_lugares_osm(
    lat: float,
    lng: float,
    radio_m: int = 4000,
    max_items: int = 300,
    timeout: Optional[int] = None,
    client: Optional[httpx.Client] = None,
) -> list[dict]:
    """Consulta Overpass y devuelve lugares ya normalizados."""
    url = getattr(settings, "overpass_url", "https://overpass-api.de/api/interpreter")
    limite = timeout or getattr(settings, "osm_timeout_seconds", 90)

    propio = client is None
    if propio:
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=limite,
            follow_redirects=True,
        )
    try:
        respuesta = client.post(
            url,
            data={"data": construir_consulta(lat, lng, radio_m, max_items)},
        )
        respuesta.raise_for_status()
        elementos = respuesta.json().get("elements", [])
    finally:
        if propio and client is not None:
            client.close()

    lugares: list[dict] = []
    vistos: set[str] = set()
    for elemento in elementos:
        lugar = mapear_lugar(elemento)
        if not lugar or lugar["external_id"] in vistos:
            continue
        vistos.add(lugar["external_id"])
        lugares.append(lugar)
    return lugares


def importar_lugares(db, lugares: list[dict], propietario_id) -> dict:
    """Inserta o actualiza servicios/productos importados sin duplicarlos."""
    from app.domain.models.product import Product
    from app.domain.models.service import Service

    creados = actualizados = 0
    for lugar in lugares:
        modelo = Service if lugar["kind"] == "service" else Product
        existente = (
            db.query(modelo)
            .filter(
                modelo.source == lugar["source"],
                modelo.external_id == lugar["external_id"],
            )
            .first()
        )
        comunes = {
            "title": lugar["title"],
            "description": lugar["description"],
            "category": lugar["category"],
            "owner_id": propietario_id,
            "source": lugar["source"],
            "source_url": lugar["source_url"],
            "external_id": lugar["external_id"],
            "price_note": lugar["price_note"],
            "latitude": lugar["latitude"],
            "longitude": lugar["longitude"],
            "address": lugar["address"],
            "contact_phone": (lugar["contact_phone"] or "")[:50] or None,
            "contact_website": (lugar["contact_website"] or "")[:500] or None,
            "is_active": True,
        }

        if existente:
            for campo, valor in comunes.items():
                setattr(existente, campo, valor)
            if lugar["kind"] == "service":
                existente.price_per_hour = existente.price_per_hour or 0.0
            else:
                existente.price = existente.price or 0.0
                existente.stock = existente.stock or 0
            actualizados += 1
            continue

        if lugar["kind"] == "service":
            db.add(Service(price_per_hour=0.0, **comunes))
        else:
            db.add(Product(price=0.0, stock=0, **comunes))
        creados += 1

    db.commit()
    return {"created": creados, "updated": actualizados, "total": creados + actualizados}
