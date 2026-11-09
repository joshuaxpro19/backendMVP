import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class Publicacion(Base):
    """Publicación vecinal (servicio, producto, favor o emergencia).

    Es el modelo que consume el front de Vecinal Solidaria; no se confunde con
    Service/Product, que son el catálogo HATEOAS del MVP.
    """

    __tablename__ = "publicaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    autor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # servicio | producto | favor_solicitado | favor_ofrecido
    subtipo_favor: Mapped[Optional[str]] = mapped_column(String(40))
    categoria: Mapped[str] = mapped_column(String(60), nullable=False, default="otros")
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False, default="")

    precio: Mapped[Optional[str]] = mapped_column(String(60))  # "S/ 40.00" | "A convenir" | ...
    stock: Mapped[Optional[int]] = mapped_column(Integer)
    medios_pago: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    politica_pago: Mapped[str] = mapped_column(String(60), nullable=False, default="")

    zona: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    lat_publica: Mapped[Optional[float]] = mapped_column(Float)
    lng_publica: Mapped[Optional[float]] = mapped_column(Float)

    punto_encuentro: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    franja_horaria: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    checklist_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    es_emergencia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    necesidad: Mapped[Optional[str]] = mapped_column(String(40))

    mostrar_contacto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    wa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    telefono_externo: Mapped[str] = mapped_column(String(20), nullable=False, default="")

    fotos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    avaladores: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activa")
    vistos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    origen: Mapped[str] = mapped_column(String(20), nullable=False, default="nativo")
    fuente: Mapped[Optional[str]] = mapped_column(String(80))
    url_origen: Mapped[Optional[str]] = mapped_column(String(500))

    client_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True)

    creado: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    autor = relationship("User", foreign_keys=[autor_id], lazy="joined")


class PublicacionVisto(Base):
    """Una recomendación ('vistos') de un vecino sobre una publicación ajena."""

    __tablename__ = "publicacion_vistos"
    __table_args__ = (UniqueConstraint("publicacion_id", "usuario_id", name="uq_visto_pub_usuario"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publicacion_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("publicaciones.id"), nullable=False, index=True
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    comentario: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    creado: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
