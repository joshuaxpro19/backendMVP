from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas.news import NewsOut
from app.domain.models.news import NewsItem
from app.infrastructure.database.connection import get_db

router = APIRouter(prefix="/news", tags=["Noticias y alertas externas"])


@router.get("/")
def listar_noticias(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(default=None, description="Fuente, por ejemplo INDECI"),
    category: Optional[str] = Query(default=None, description="reporte, boletin, aviso u otro"),
    db: Session = Depends(get_db),
):
    """
    Lista las noticias y alertas públicas importadas de fuentes externas.
    No requiere login.
    """
    query = db.query(NewsItem)
    if source:
        query = query.filter(NewsItem.source == source.upper())
    if category:
        query = query.filter(NewsItem.category == category.lower())

    total = query.count()
    items = (
        query.order_by(NewsItem.published_at.desc().nullslast(), NewsItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [NewsOut.model_validate(item).model_dump(mode="json") for item in items],
        "_links": {
            "self": {
                "href": f"/api/news?page={page}&page_size={page_size}",
                "method": "GET",
            },
            "refresh": {"href": "/api/admin/news/refresh", "method": "POST"},
            "next": {
                "href": f"/api/news?page={page + 1}&page_size={page_size}",
                "method": "GET",
            }
            if (page * page_size) < total
            else None,
            "prev": {
                "href": f"/api/news?page={page - 1}&page_size={page_size}",
                "method": "GET",
            }
            if page > 1
            else None,
        },
    }
