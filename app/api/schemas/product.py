import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.category import ProductCategory


class ProductCreate(BaseModel):
    """Schema for publishing a new product."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    price: float = Field(..., gt=0)
    stock: int = Field(..., ge=0)
    category: ProductCategory


class ProductUpdate(BaseModel):
    """Schema for editing an existing product."""
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, min_length=10)
    price: Optional[float] = Field(default=None, gt=0)
    stock: Optional[int] = Field(default=None, ge=0)
    category: Optional[ProductCategory] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    """Public representation of a product."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    price: float
    stock: int
    category: ProductCategory
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
