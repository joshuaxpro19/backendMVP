"""Migraciones ligeras aplicadas al arrancar (modo MVP sin Alembic).

`Base.metadata.create_all` crea tablas nuevas, pero no altera tablas que ya
existen. Estas sentencias agregan columnas e índices a instalaciones previas.
Son idempotentes: se pueden ejecutar en cada arranque y también en las pruebas.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


MIGRACIONES: tuple[str, ...] = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20) UNIQUE;",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS source VARCHAR(50);",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS source_url VARCHAR(500);",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS external_id VARCHAR(200);",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS price_note VARCHAR(150);",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50);",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS contact_website VARCHAR(500);",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS address VARCHAR(255);",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;",
    "ALTER TABLE services ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS source VARCHAR(50);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS source_url VARCHAR(500);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS external_id VARCHAR(200);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS price_note VARCHAR(150);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS contact_website VARCHAR(500);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS address VARCHAR(255);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;",
    "CREATE INDEX IF NOT EXISTS ix_services_source ON services (source);",
    "CREATE INDEX IF NOT EXISTS ix_products_source ON products (source);",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_services_source_external ON services (source, external_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_products_source_external ON products (source, external_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_news_source_external ON news_items (source, external_id);",
)


def aplicar_migraciones(engine: Engine) -> list[str]:
    """Ejecuta cada migración en su propia transacción.

    Devuelve las sentencias que fallaron. Una migración fallida no debe impedir
    el arranque ni abortar las demás (en PostgreSQL, un error dentro de una
    transacción la deja inutilizable hasta el rollback).
    """
    fallidas: list[str] = []
    for migracion in MIGRACIONES:
        try:
            with engine.begin() as conn:
                conn.execute(text(migracion))
        except Exception:
            fallidas.append(migracion)
    return fallidas
