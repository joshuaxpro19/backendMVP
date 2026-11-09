"""Ensure DB schema exists before the test suite runs.

`TestClient(app)` is instantiated at module level in test_api.py, so FastAPI's
lifespan (which calls `create_all`) never runs. Creating the schema here keeps
the suite self-contained on both PostgreSQL and SQLite.
"""

from app.infrastructure.database.base import Base
from app.infrastructure.database.connection import engine
from app.infrastructure.database.migrations import ensure_columns

# Import all models so SQLAlchemy can discover them when create_all is called.
from app.domain.models import (  # noqa: F401
    user,
    service,
    product,
    alert,
    order,
    scraped_post,
    publicacion,
    reporte,
)

Base.metadata.create_all(bind=engine)
ensure_columns(engine)

import pytest  # noqa: E402

from app.api.routes import vecinal  # noqa: E402


@pytest.fixture(autouse=True)
def _limpiar_rate_limit():
    """El limitador de peticiones vive en memoria: se vacía entre tests."""
    vecinal._RL.clear()
    yield
    vecinal._RL.clear()
