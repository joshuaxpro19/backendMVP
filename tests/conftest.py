"""Prepara el esquema antes de las pruebas.

Las pruebas usan la base indicada en DATABASE_URL tal cual, sin crear un
esquema aparte. Para que una instalación previa no falle por columnas que se
agregaron después (por ejemplo `services.source`), aquí se crean las tablas
faltantes y se aplican las migraciones idempotentes antes de importar la app.
"""

from app.infrastructure.database.base import Base
from app.infrastructure.database.connection import engine
from app.infrastructure.database.migrations import aplicar_migraciones

# Registra todos los modelos en Base.metadata antes de create_all.
import app.domain.models  # noqa: F401


def _preparar_esquema() -> None:
    Base.metadata.create_all(bind=engine)
    aplicar_migraciones(engine)


_preparar_esquema()
