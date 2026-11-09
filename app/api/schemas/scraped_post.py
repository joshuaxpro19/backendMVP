import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScrapingRunRequest(BaseModel):
    """Parameters for one Facebook scraping run."""

    queries: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Consultas de búsqueda. Vacío = consultas por defecto de la ciudad configurada.",
    )
    scrolls_per_query: int = Field(default=3, ge=1, le=8, description="Rounds de scroll por consulta")
    city: Optional[str] = Field(default=None, max_length=100, description="Ciudad objetivo (vacío = settings)")
    download_images: bool = Field(default=True, description="Descarga las imágenes de los posts")


class ScrapedPostOut(BaseModel):
    """Publicación de Facebook capturada."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author: Optional[str]
    posted_at: Optional[str]
    source_name: Optional[str]
    source_type: str
    content: str
    city: Optional[str]
    phones: list[str]
    whatsapp: list[str]
    image_urls: list[str]
    image_files: list[str]
    phone_count: int
    image_count: int
    post_url: Optional[str]
    profile_url: Optional[str]
    query_origen: Optional[str]
    is_active: bool
    captured_at: datetime


class ScrapingRunResult(BaseModel):
    """Summary of a scraping run."""

    queries: list[str]
    city: str
    found: int
    out_of_city: int
    saved: int
    with_phone: int
    with_images: int
    images_downloaded: int
    total_in_db: int
