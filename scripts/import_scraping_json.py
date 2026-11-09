"""Importa un JSON del scraper (PoC o export) a `scraped_posts`, con sus imágenes.

- Copia las imágenes locales a `data/scraping_images/` con nombres únicos.
- Limpia el texto que Facebook inyecta en cada tarjeta (grupo, autor, fecha,
  "Unirte", contadores).
- Es idempotente: `content_hash` = sha256 del texto limpio.
- Borra los leads de ejemplo (`content_hash` que empieza por `demo-`).

Uso:
    python scripts/import_scraping_json.py "C:/ruta/piura_resultados.json"
    docker exec mvp-api python scripts/import_scraping_json.py /ruta.json
"""

import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.models import scraped_post  # noqa: F401,E402
from app.domain.models.scraped_post import ScrapedPost  # noqa: E402
from app.infrastructure.database.base import Base  # noqa: E402
from app.infrastructure.database.connection import SessionLocal, engine  # noqa: E402
from app.infrastructure.database.migrations import ensure_columns  # noqa: E402
from app.scraping.text_utils import AUTHOR_NOISE, DATE_RE, clean_lines  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DESTINO_IMAGENES = RAIZ / "data" / "scraping_images"

RUIDO = {
    "Unirte",
    "Seguir",
    "Unirse",
    "Participante anónimo",
    "Se desactivaron los comentarios para esta publicación.",
    "Ver más",
    "…",
}
SOLO_NUMEROS = re.compile(r"^[\d.,\s]+$")


def limpiar(texto: str, autor: str | None, grupo: str | None) -> str:
    lineas = clean_lines(texto or "")
    utiles = []
    for linea in lineas:
        if grupo and linea == grupo:
            continue
        if autor and linea == autor:
            continue
        if linea in RUIDO or linea in AUTHOR_NOISE:
            continue
        if DATE_RE.match(linea) or SOLO_NUMEROS.match(linea):
            continue
        if linea.startswith("Se desactivaron los comentarios"):
            continue
        utiles.append(linea)
    limpio = re.sub(r"\s+", " ", " ".join(utiles)).strip()
    if len(limpio) < 5:
        limpio = f"Publicación de {grupo or 'Facebook'}"
    return limpio[:2000]


def copiar_imagen(ruta: Path, clave: str, indice: int) -> str | None:
    if not ruta.exists() or not ruta.is_file():
        return None
    extension = ruta.suffix.lower()
    nombre = f"fb_{clave[:10]}_{indice}{extension}"
    destino = DESTINO_IMAGENES / nombre
    if not destino.exists():
        try:
            if extension == ".webp":
                from PIL import Image  # opcional

                with Image.open(ruta) as im:
                    im.convert("RGB").save(destino.with_suffix(".jpg"), quality=85)
                nombre = destino.with_suffix(".jpg").name
            else:
                shutil.copy2(ruta, destino)
        except Exception:
            shutil.copy2(ruta, destino)
    return nombre


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python scripts/import_scraping_json.py <resultados.json> [base]")
        raise SystemExit(1)

    origen = Path(sys.argv[1]).resolve()
    base = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else origen.parent.parent
    datos = json.loads(origen.read_text(encoding="utf-8"))
    posts = datos.get("posts", datos) if isinstance(datos, dict) else datos

    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)
    DESTINO_IMAGENES.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    borrados = db.query(ScrapedPost).filter(ScrapedPost.content_hash.like("demo-%")).delete(
        synchronize_session=False
    )
    db.commit()

    nuevos = 0
    con_imagen = 0
    con_telefono = 0
    for post in posts:
        texto = limpiar(post.get("texto"), post.get("autor"), post.get("grupo_o_pagina"))
        clave = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        if db.query(ScrapedPost.id).filter(ScrapedPost.content_hash == clave).first():
            continue

        imagenes = []
        for i, relativa in enumerate(post.get("imagenes_local") or []):
            nombre = copiar_imagen(base / str(relativa).replace("\\", "/"), clave, i)
            if nombre:
                imagenes.append(f"data/scraping_images/{nombre}")
        if imagenes:
            con_imagen += 1

        telefonos = [t for t in (post.get("telefonos") or []) if t]
        whatsapp = [w for w in (post.get("whatsapp") or []) if w]
        if telefonos:
            con_telefono += 1

        ciudad = (post.get("ciudad") or "").strip()
        db.add(
            ScrapedPost(
                author=post.get("autor"),
                posted_at=post.get("fecha"),
                source_name=post.get("grupo_o_pagina"),
                source_type=post.get("tipo") or "grupo",
                content=texto,
                city=ciudad.title() if ciudad else None,
                phones=telefonos,
                whatsapp=whatsapp,
                image_urls=[u for u in (post.get("imagenes") or []) if u],
                image_files=imagenes,
                phone_count=len(telefonos),
                image_count=len(imagenes),
                post_url=post.get("url_post"),
                profile_url=post.get("url_perfil"),
                query_origen=post.get("query_origen"),
                content_hash=clave,
                captured_at=datetime.now(timezone.utc),
            )
        )
        nuevos += 1
    db.commit()
    total = db.query(ScrapedPost).count()
    db.close()

    print(f"Importados: {nuevos} (con imagen: {con_imagen}, con teléfono: {con_telefono})")
    print(f"Leads de ejemplo borrados: {borrados}")
    print(f"Total en scraped_posts: {total}")


if __name__ == "__main__":
    main()
