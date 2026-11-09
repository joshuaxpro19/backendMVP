"""Carga 6 leads de ejemplo en `scraped_posts` para la demo.

Útil cuando no hay tiempo (o sesión de Facebook) para correr el scraper real.
Es idempotente: el `content_hash` evita duplicados.

Uso:
    python scripts/seed_demo_scraping.py
    docker exec mvp-api python scripts/seed_demo_scraping.py
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func  # noqa: E402

from app.domain.models import scraped_post  # noqa: F401,E402
from app.domain.models.scraped_post import ScrapedPost  # noqa: E402
from app.infrastructure.database.base import Base  # noqa: E402
from app.infrastructure.database.connection import SessionLocal, engine  # noqa: E402
from app.infrastructure.database.migrations import ensure_columns  # noqa: E402

DEMO = [
    (
        "Carlos M.",
        "Gasfitero 24 horas: destapes, fugas e instalación de sanitarios. "
        "Atiendo en todo Piura. Llama al 968 123 456.",
        ["968123456"],
        "gasfitero Piura",
    ),
    (
        "Luis Electricista",
        "Electricista certificado. Instalaciones, tableros y mantenimiento de "
        "pozos a tierra. Urgencias al 912 345 678.",
        ["912345678"],
        "electricista Piura",
    ),
    (
        "Taller Don José",
        "Carpintero en melamina: muebles a medida, closets y repisas. "
        "Cotizaciones sin compromiso al 955 111 222.",
        ["955111222"],
        "carpintero Piura",
    ),
    (
        "Enf. Rosa",
        "Enfermera técnica ofrece cuidado de adultos mayores por horas o turno "
        "completo. Referencias comprobables. 944 555 666.",
        ["944555666"],
        "enfermera Piura ofrece servicio",
    ),
    (
        "Prof. Ana",
        "Clases particulares de matemática y comunicación, primaria y secundaria. "
        "Refuerzo antes de exámenes. 933 777 888.",
        ["933777888"],
        "clases particulares Piura",
    ),
    (
        "Fletes Piura",
        "Servicio de mudanza y flete dentro de la ciudad. Camión 3 toneladas. "
        "Coordina al 922 333 444.",
        ["922333444"],
        "movilidad Piura",
    ),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)

    db = SessionLocal()
    nuevos = 0
    for autor, texto, telefonos, busqueda in DEMO:
        clave = "demo-" + hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]
        if db.query(ScrapedPost.id).filter(ScrapedPost.content_hash == clave).first():
            continue
        db.add(
            ScrapedPost(
                author=autor,
                source_name="Servicios Piura (demo)",
                source_type="grupo",
                content=texto,
                city="Piura",
                phones=telefonos,
                whatsapp=telefonos,
                image_urls=[],
                image_files=[],
                phone_count=len(telefonos),
                content_hash=clave,
                query_origen=busqueda,
                post_url=None,
            )
        )
        nuevos += 1
    db.commit()
    total = db.query(func.count(ScrapedPost.id)).scalar()
    db.close()
    print(f"Leads de demo nuevos: {nuevos}. Total en scraped_posts: {total}.")


if __name__ == "__main__":
    main()
