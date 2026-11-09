"""Scraping use cases: run the Facebook scraper and persist the results."""

import uuid
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.scraped_post import ScrapingRunRequest
from app.config.settings import settings
from app.domain.models.scraped_post import ScrapedPost
from app.scraping.facebook import FacebookScraper, FacebookScraperError

# Indirection so tests can swap in a fake scraper without hitting Facebook.
scraper_factory = FacebookScraper


def _build_scraper() -> FacebookScraper:
    return scraper_factory(
        email=settings.fb_email,
        password=settings.fb_password,
        state_path=settings.fb_state_path,
        headless=settings.scraping_headless,
        images_dir=settings.scraping_images_dir,
        max_images=settings.scraping_max_images,
    )


def run(db: Session, data: ScrapingRunRequest) -> dict[str, Any]:
    """
    Execute a scraping run and store every new post (deduplicated by content_hash).
    Raises 502 when Facebook blocks the session (bad credentials / checkpoint).
    """
    queries = [q.strip() for q in data.queries if q.strip()] or settings.default_queries
    city = (data.city or settings.scraping_city).strip()

    try:
        posts, stats = _build_scraper().run(
            queries=queries,
            city=city,
            localities=settings.locality_list,
            scrolls_per_query=data.scrolls_per_query,
            download_images=data.download_images,
        )
    except FacebookScraperError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    saved = _persist(db, posts)

    return {
        "queries": queries,
        "city": city,
        "found": stats.get("found", 0),
        "out_of_city": stats.get("out_of_city", 0),
        "saved": saved,
        "with_phone": sum(1 for p in posts if p.get("phones")),
        "with_images": sum(1 for p in posts if p.get("image_urls")),
        "images_downloaded": stats.get("images_downloaded", 0),
        "total_in_db": db.query(ScrapedPost).filter(ScrapedPost.is_active == True).count(),  # noqa: E712
    }


def _persist(db: Session, posts: list[dict[str, Any]]) -> int:
    if not posts:
        return 0

    hashes = [p["content_hash"] for p in posts]
    existing = {
        row[0]
        for row in db.query(ScrapedPost.content_hash).filter(ScrapedPost.content_hash.in_(hashes))
    }

    saved = 0
    for post in posts:
        if post["content_hash"] in existing:
            continue
        db.add(
            ScrapedPost(
                author=post.get("author"),
                posted_at=post.get("posted_at"),
                source_name=post.get("source_name"),
                source_type=post.get("source_type") or "perfil",
                content=post["content"],
                city=post.get("city"),
                phones=post.get("phones") or [],
                whatsapp=post.get("whatsapp") or [],
                image_urls=post.get("image_urls") or [],
                image_files=post.get("image_files") or [],
                phone_count=len(post.get("phones") or []),
                image_count=len(post.get("image_urls") or []),
                post_url=post.get("post_url"),
                profile_url=post.get("profile_url"),
                query_origen=post.get("query_origen"),
                content_hash=post["content_hash"],
            )
        )
        existing.add(post["content_hash"])
        saved += 1

    db.commit()
    return saved


def get_all(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    city: Optional[str] = None,
    has_phone: Optional[bool] = None,
    query: Optional[str] = None,
) -> tuple[list[ScrapedPost], int]:
    query_builder = db.query(ScrapedPost).filter(ScrapedPost.is_active == True)  # noqa: E712
    if city:
        query_builder = query_builder.filter(ScrapedPost.city.ilike(f"%{city}%"))
    if has_phone is True:
        query_builder = query_builder.filter(ScrapedPost.phone_count > 0)
    elif has_phone is False:
        query_builder = query_builder.filter(ScrapedPost.phone_count == 0)
    if query:
        pattern = f"%{query}%"
        query_builder = query_builder.filter(
            ScrapedPost.content.ilike(pattern) | ScrapedPost.author.ilike(pattern)
        )

    total = query_builder.count()
    posts = (
        query_builder.order_by(ScrapedPost.captured_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return posts, total


def get_by_id(db: Session, post_id: uuid.UUID) -> ScrapedPost:
    post = db.query(ScrapedPost).filter(ScrapedPost.id == post_id, ScrapedPost.is_active == True).first()  # noqa: E712
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")
    return post


def export_json(db: Session) -> dict[str, Any]:
    """Full dataset as JSON (the format used during the proof of concept."""
    posts = (
        db.query(ScrapedPost)
        .filter(ScrapedPost.is_active == True)  # noqa: E712
        .order_by(ScrapedPost.captured_at.desc())
        .all()
    )
    return {
        "city": settings.scraping_city,
        "total": len(posts),
        "with_phone": sum(1 for p in posts if p.phone_count),
        "with_images": sum(1 for p in posts if p.image_count),
        "posts": [_as_dict(p) for p in posts],
    }


def _as_dict(post: ScrapedPost) -> dict[str, Any]:
    return {
        "id": str(post.id),
        "autor": post.author,
        "fecha": post.posted_at,
        "grupo_o_pagina": post.source_name,
        "tipo": post.source_type,
        "texto": post.content,
        "ciudad": post.city,
        "telefonos": post.phones,
        "whatsapp": post.whatsapp,
        "imagenes": post.image_urls,
        "imagenes_local": post.image_files,
        "url_post": post.post_url,
        "url_perfil": post.profile_url,
        "query_origen": post.query_origen,
        "capturado_en": post.captured_at.isoformat() if post.captured_at else None,
    }
