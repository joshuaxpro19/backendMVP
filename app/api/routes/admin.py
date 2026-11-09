import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.domain.models.role import Roles
from app.domain.models.user import User
from app.infrastructure.database.connection import get_db
from app.scraping.indeci import guardar_indeci, obtener_indeci
from app.scraping.osm import importar_lugares, obtener_lugares_osm
from app.usecases.auth import get_current_admin, get_current_staff, hash_password

router = APIRouter(prefix="/admin", tags=["Administración e importación"])


class OsmSeedRequest(BaseModel):
    lat: float = Field(default=-5.1945, ge=-90, le=90, description="Latitud del centro")
    lng: float = Field(default=-80.6328, ge=-180, le=180, description="Longitud del centro")
    radius_m: int = Field(default=4000, ge=200, le=20000, description="Radio en metros")
    max_items: int = Field(default=300, ge=1, le=500, description="Máximo de lugares a importar")


def _usuario_directorio(db: Session) -> User:
    """Usuario técnico que figura como propietario del catálogo importado."""
    usuario = db.query(User).filter(User.username == "directorio_vecinal").first()
    if usuario:
        return usuario

    # Valores reservados para el catálogo; si ya existieran, se usa un sufijo.
    sufijo = secrets.token_hex(3)
    usuario = User(
        dni=f"99{sufijo}".upper()[:20],
        phone=f"+5199{secrets.randbelow(10**7):07d}",
        username="directorio_vecinal",
        email="directorio@vecinal.local",
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        full_name="Directorio Vecinal (datos abiertos)",
        role=Roles.USER,
        is_active=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/news/refresh")
def refrescar_noticias(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_staff),
):
    """
    Descarga y guarda los reportes públicos de INDECI. Solo moderadores/admin.
    """
    try:
        noticias = obtener_indeci()
    except Exception as exc:  # red, timeout o cambio de HTML
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo leer INDECI: {exc}",
        ) from exc
    resultado = guardar_indeci(db, noticias)
    return {"source": "INDECI", **resultado}


@router.post("/catalog/seed/osm")
def sembrar_catalogo_osm(
    datos: OsmSeedRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    Importa negocios y servicios reales desde OpenStreetMap (datos abiertos).
    Solo administradores. No scrapea redes sociales.
    """
    try:
        lugares = obtener_lugares_osm(
            lat=datos.lat,
            lng=datos.lng,
            radio_m=datos.radius_m,
            max_items=datos.max_items,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo consultar OpenStreetMap: {exc}",
        ) from exc

    propietario = _usuario_directorio(db)
    resultado = importar_lugares(db, lugares, propietario.id)
    return {
        "source": "openstreetmap",
        "license": "ODbL",
        "lat": datos.lat,
        "lng": datos.lng,
        "radius_m": datos.radius_m,
        **resultado,
    }
