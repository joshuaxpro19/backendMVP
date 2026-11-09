import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Text, JSON, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.infrastructure.database.base import Base


class ScrapedPost(Base):
    """Publicación de Facebook capturada por el scraper (lead de servicios)."""

    __tablename__ = "scraped_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    posted_at: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="perfil")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    phones: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    whatsapp: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    image_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    image_files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    phone_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_origen: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Revisión con IA (OpenRouter): NULL = pendiente de revisar
    ia_estado: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    ia_motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ia_titulo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ia_descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    ia_categoria: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ia_telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ia_ubicacion: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ia_revisado: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
