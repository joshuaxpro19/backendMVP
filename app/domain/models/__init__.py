# Import models here so SQLAlchemy can discover them when create_all is called.
from app.domain.models.user import User
from app.domain.models.service import Service
from app.domain.models.product import Product
from app.domain.models.alert import Alert
from app.domain.models.order import Order, OrderItemType, OrderStatus
from app.domain.models.news import NewsItem

__all__ = [
    "User",
    "Service",
    "Product",
    "Alert",
    "Order",
    "OrderItemType",
    "OrderStatus",
    "NewsItem",
]
