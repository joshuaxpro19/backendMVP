import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Enum as SAEnum, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.infrastructure.database.base import Base
from app.domain.models.role import Roles


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dni: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[Roles] = mapped_column(
        SAEnum(Roles, name="roles_enum"), default=Roles.USER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Perfil vecinal (lo que pinta el front de Vecinal Solidaria)
    zona: Mapped[str] = mapped_column(String(80), default="Piura Centro", nullable=False)
    yape: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    plin: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    telefono_verificado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mostrar_contacto: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Freno a la fuerza bruta en /api/login
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bloqueado_hasta: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    services: Mapped[list["Service"]] = relationship("Service", back_populates="owner", cascade="all, delete-orphan")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="owner", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="owner", cascade="all, delete-orphan")
    orders_bought: Mapped[list["Order"]] = relationship("Order", foreign_keys="Order.buyer_id", back_populates="buyer", cascade="all, delete-orphan")
    orders_sold: Mapped[list["Order"]] = relationship("Order", foreign_keys="Order.seller_id", back_populates="seller", cascade="all, delete-orphan")
