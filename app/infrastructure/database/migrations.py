"""Migraciones aditivas sin Alembic.

`Base.metadata.create_all` crea las tablas nuevas pero **no** añade columnas a
tablas existentes; estas funciones agregan las que falten en cada arranque.
Idempotentes y seguras tanto en PostgreSQL como en SQLite.
"""

from sqlalchemy import inspect, text

# tabla -> [(columna, tipo y default)]
ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("phone", "VARCHAR(20)"),
        ("zona", "TEXT DEFAULT 'Piura Centro'"),
        ("yape", "TEXT DEFAULT ''"),
        ("plin", "TEXT DEFAULT ''"),
        ("telefono_verificado", "BOOLEAN DEFAULT FALSE"),
        ("mostrar_contacto", "BOOLEAN DEFAULT TRUE"),
        ("intentos_fallidos", "INTEGER DEFAULT 0"),
        ("bloqueado_hasta", "TIMESTAMP"),
    ],
    "publicaciones": [
        ("version", "INTEGER DEFAULT 1"),
    ],
    "scraped_posts": [
        ("ia_estado", "VARCHAR(20)"),
        ("ia_motivo", "TEXT"),
        ("ia_titulo", "VARCHAR(200)"),
        ("ia_descripcion", "TEXT"),
        ("ia_categoria", "VARCHAR(60)"),
        ("ia_telefono", "VARCHAR(20)"),
        ("ia_ubicacion", "VARCHAR(120)"),
        ("ia_revisado", "TIMESTAMP"),
    ],
}


def ensure_columns(engine) -> None:
    """Añade las columnas de ADDITIVE_COLUMNS que todavía no existan.

    Cada ALTER va en su propia transacción: en PostgreSQL, un error aborta la
    transacción y haría fallar los ALTER siguientes.
    """
    inspector = inspect(engine)
    tablas = set(inspector.get_table_names())
    for tabla, columnas in ADDITIVE_COLUMNS.items():
        if tabla not in tablas:
            continue
        existentes = {c["name"] for c in inspector.get_columns(tabla)}
        for nombre, definicion in columnas:
            if nombre in existentes:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))
            except Exception:
                # Otra sesión lo añadió a la vez u otro dialecto lo rechazó.
                pass
