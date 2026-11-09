import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.category import ServiceCategory


class ServiceCreate(BaseModel):
    """Schema for publishing a new service."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    price_per_hour: float = Field(..., gt=0)
    category: ServiceCategory


class ServiceUpdate(BaseModel):
    """Schema for editing an existing service."""
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, min_length=10)
    price_per_hour: Optional[float] = Field(default=None, gt=0)
    category: Optional[ServiceCategory] = None
    is_active: Optional[bool] = None


class ServiceOut(BaseModel):
    """Public representation of a service."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    price_per_hour: float
    category: ServiceCategory
    owner_id: uuid.UUID
    is_active: bool
    created_at: datetime
    source: Optional[str] = None
    source_url: Optional[str] = None
    price_note: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_website: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
