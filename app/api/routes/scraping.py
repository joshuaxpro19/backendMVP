import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.schemas.hateoas import Link, with_links
from app.api.schemas.scraped_post import ScrapedPostOut, ScrapingRunRequest, ScrapingRunResult
from app.domain.models.scraped_post import ScrapedPost
from app.domain.models.user import User
from app.infrastructure.database.connection import get_db
from app.services import scraping_service
from app.usecases.auth import get_current_active_user

router = APIRouter(prefix="/scraping", tags=["Scraping de Facebook"])


@router.post("/run", response_model=ScrapingRunResult, status_code=status.HTTP_200_OK)
def run_scraping(
    data: ScrapingRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Ejecuta un scraper de Facebook (Playwright) y guarda las publicaciones nuevas.

    Tardía varios minutos: hace scroll humano en varias búsquedas y descarga imágenes.
    Requiere inicio de sesión y credenciales de Facebook válidas (FB_EMAIL / FB_PASSWORD).
    """
    return scraping_service.run(db, data)


@router.get("/posts")
def list_scraped_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: Optional[str] = Query(default=None, max_length=100),
    has_phone: Optional[bool] = Query(default=None, description="Solo publicaciones con teléfono"),
    q: Optional[str] = Query(default=None, max_length=200, description="Busca en texto o autor"),
    db: Session = Depends(get_db),
):
    """
    Lista las publicaciones capturadas. Consulta pública sin login.
    """
    posts, total = scraping_service.get_all(db, page, page_size, city, has_phone, q)
    items = [
        with_links(
            ScrapedPostOut.model_validate(post),
            {"self": Link(href=f"/api/scraping/posts/{post.id}")},
        )
        for post in posts
    ]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "_links": {
            "self": {"href": f"/api/scraping/posts?page={page}&page_size={page_size}", "method": "GET"},
            "next": {"href": f"/api/scraping/posts?page={page + 1}&page_size={page_size}", "method": "GET"}
            if (page * page_size) < total
            else None,
            "prev": {"href": f"/api/scraping/posts?page={page - 1}&page_size={page_size}", "method": "GET"}
            if page > 1
            else None,
            "export": {"href": "/api/scraping/export", "method": "GET"},
            "run": {"href": "/api/scraping/run", "method": "POST"},
        },
    }


@router.get("/posts/{post_id}")
def get_scraped_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Detalle de una publicación capturada. Acceso público.
    """
    post = scraping_service.get_by_id(db, post_id)
    return with_links(
        ScrapedPostOut.model_validate(post),
        {"self": Link(href=f"/api/scraping/posts/{post.id}")},
    )


@router.get("/export")
def export_scraped_posts(db: Session = Depends(get_db)):
    """
    Exporta todo el dataset capturado como JSON descargable.
    """
    payload = scraping_service.export_json(db)
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="scraped_posts_{payload["city"].lower()}.json"'},
    )
