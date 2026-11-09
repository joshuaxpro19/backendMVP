import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NewsOut(BaseModel):
    """Representación pública de una noticia o alerta externa."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    title: str
    summary: Optional[str] = None
    url: str
    pdf_url: Optional[str] = None
    category: str
    published_at: Optional[datetime] = None
    created_at: datetime
