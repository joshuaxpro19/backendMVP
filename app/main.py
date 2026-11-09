import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import api
from app.config.settings import settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.connection import engine
from app.infrastructure.database.migrations import ensure_columns

# Import all models so SQLAlchemy registers them before create_all
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables and columns on startup (dev/MVP mode)."""
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)

    # Scraping cada N horas + limpieza con IA en segundo plano
    from app.services import scheduler

    scheduler.iniciar()
    try:
        yield
    finally:
        scheduler.detener()


app = FastAPI(
    title="API Vecinal",
    version="0.1.0",
    description="REST API para la comunidad vecinal — servicios y productos entre vecinos.",
    lifespan=lifespan,
)

# Enable CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _cabeceras_seguridad(request: Request, call_next):
    """Cabeceras de seguridad para navegadores (sin CSP: rompería la PWA).

    Un cliente React Native las ignora por completo.
    """
    inicio = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(self), microphone=()"
    response.headers["X-Response-Time-ms"] = str(int((time.perf_counter() - inicio) * 1000))
    return response


@app.exception_handler(RequestValidationError)
async def _validacion_legible(request: Request, exc: RequestValidationError):
    """El front pinta `detail` como texto: devolvemos un mensaje, no una lista."""
    primero = (exc.errors() or [{}])[0]
    campo = ".".join(str(x) for x in primero.get("loc", ()) if x != "body")
    msg = str(primero.get("msg", "Dato inválido")).replace("Value error, ", "")
    return JSONResponse(
        status_code=422,
        content={"detail": f"{campo}: {msg}" if campo else msg},
    )


@app.get("/")
async def root():
    return {
        "message": "API Vecinal",
        "_links": {
            "api": {"href": "/api/", "method": "GET"},
            "docs": {"href": "/docs", "method": "GET"},
            "redoc": {"href": "/redoc", "method": "GET"},
        },
    }


# Fotos subidas por el front (el contrato exige rutas relativas /fotos/...)
Path(settings.fotos_dir).mkdir(parents=True, exist_ok=True)
app.mount("/fotos", StaticFiles(directory=settings.fotos_dir), name="fotos")

# Imágenes descargadas por el scraper de Facebook
Path(settings.scraping_images_dir).mkdir(parents=True, exist_ok=True)
app.mount(
    "/scraping-images",
    StaticFiles(directory=settings.scraping_images_dir),
    name="scraping-images",
)

app.include_router(api.apiRouter)