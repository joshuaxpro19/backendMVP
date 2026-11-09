import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.scraping.facebook import content_hash
from app.scraping.text_utils import clean_lines, extract_phones, match_location, pick_author
from app.services import scraping_service

client = TestClient(app)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _auth_headers() -> dict:
    suffix = uuid.uuid4().hex[:6]
    client.post(
        "/api/auth/register",
        json={
            "username": f"scraper_{suffix}",
            "email": f"scraper_{suffix}@example.com",
            "password": "Password123!",
            "full_name": "Vecino Scraper",
            "dni": f"5{uuid.uuid4().int % 10000000:07d}",
            "phone": f"+5193{uuid.uuid4().int % 10000000:07d}",
        },
    )
    token = client.post(
        "/api/auth/login",
        data={"username": f"scraper_{suffix}@example.com", "password": "Password123!"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _fake_post(**overrides) -> dict:
    seed = uuid.uuid4().hex
    post = {
        "author": "Reto Hernández",
        "posted_at": "sábado, 10 de enero de 2026 a las 9:04 am",
        "source_name": "TRABAJOS EN PIURA - DATEA CHAMBA",
        "source_type": "grupo",
        "content": "Ofrezco mi servicio de carpintero, estoy en Piura.\nMi número 999 888 777",
        "city": "piura",
        "phones": ["999888777"],
        "whatsapp": [],
        "image_urls": ["https://scontent.example/image_n.jpg"],
        "image_files": ["data/scraping_images/post_000_0.jpg"],
        "post_url": f"https://www.facebook.com/groups/{seed}",
        "profile_url": None,
        "query_origen": "carpintero Piura",
        "content_hash": content_hash(f"https://www.facebook.com/groups/{seed}", ""),
    }
    post.update(overrides)
    return post


class FakeScraper:
    """Drop-in replacement for FacebookScraper: returns canned posts, no network."""

    def __init__(self, posts: list[dict], **_kwargs):
        self.posts = posts

    def run(self, *, queries, city, localities, scrolls_per_query, download_images):
        return list(self.posts), {
            "found": len(self.posts) + 2,
            "out_of_city": 2,
            "images_downloaded": 1,
        }


def _use_fake_scraper(monkeypatch, posts: list[dict]):
    monkeypatch.setattr(
        scraping_service, "scraper_factory", lambda **kwargs: FakeScraper(posts, **kwargs)
    )


# --------------------------------------------------------------------------- #
# Unit tests: text parsing (no browser, no DB)
# --------------------------------------------------------------------------- #
def test_phone_extraction_ignores_reaction_counters():
    # Reaction counters arrive on separate lines: "337\n22\n16" must not become a phone.
    assert extract_phones("Buenos dias\n337\n22\n16") == []
    assert extract_phones("WhatsApp: 969 317 713") == ["969317713"]
    assert extract_phones("Escribir al +51 966 519 425") == ["+51966519425"]
    assert extract_phones("cel 954318898") == ["954318898"]
    # A public resolution number like "001-2026" is not a contact number.
    assert extract_phones("PRONUNCIAMIENTO N° 001-2026-SETP") == []


def test_location_matching_and_author_pick():
    assert match_location("Ofrezco servicios en Piura", "Piura", ["castilla"]) == "Piura"
    assert match_location("Trabajo en Castilla", "Piura", ["castilla"]) == "castilla"
    assert match_location("Solo Lima", "Piura", ["castilla"]) is None

    lines = clean_lines(
        "Facebook\nGrupo Chamba Piura\nUnirte\nJuan Perez\nlunes, 2 de noviembre de 2026\nBusco carpintero"
    )
    assert "Facebook" not in lines
    assert pick_author(lines) == "Juan Perez"


# --------------------------------------------------------------------------- #
# API tests: run / list / export (scraper mocked)
# --------------------------------------------------------------------------- #
def test_scraping_run_requires_authentication():
    r = client.post("/api/scraping/run", json={"queries": ["carpintero Piura"]})
    assert r.status_code == 401


def test_scraping_run_persists_and_deduplicates(monkeypatch):
    posts = [_fake_post()]
    _use_fake_scraper(monkeypatch, posts)
    headers = _auth_headers()

    r_first = client.post(
        "/api/scraping/run",
        json={"queries": ["carpintero Piura"], "scrolls_per_query": 1, "download_images": False},
        headers=headers,
    )
    assert r_first.status_code == 200, r_first.text
    first = r_first.json()
    assert first["saved"] == 1
    assert first["out_of_city"] == 2
    assert first["with_phone"] == 1
    assert first["total_in_db"] >= 1

    # Same content again -> detected as duplicate, nothing saved twice.
    r_second = client.post(
        "/api/scraping/run",
        json={"queries": ["carpintero Piura"], "scrolls_per_query": 1, "download_images": False},
        headers=headers,
    )
    assert r_second.status_code == 200
    assert r_second.json()["saved"] == 0


def test_scraped_posts_listing_filter_and_detail(monkeypatch):
    with_phone = _fake_post(content="Carpintero en Piura, cel 970510236", phones=["970510236"])
    without_phone = _fake_post(content="Carpintero en Piura, escríbeme por mensaje", phones=[])
    _use_fake_scraper(monkeypatch, [with_phone, without_phone])
    headers = _auth_headers()

    client.post(
        "/api/scraping/run",
        json={"queries": ["carpintero Piura"], "scrolls_per_query": 1, "download_images": False},
        headers=headers,
    )

    # Listing is public (no auth needed)
    r_all = client.get("/api/scraping/posts")
    assert r_all.status_code == 200
    assert r_all.json()["total"] >= 2

    r_with = client.get("/api/scraping/posts?has_phone=true")
    assert r_with.status_code == 200
    assert all(item["phone_count"] > 0 for item in r_with.json()["items"])

    target = next(i for i in r_with.json()["items"] if i["phones"] == ["970510236"])
    r_detail = client.get(f"/api/scraping/posts/{target['id']}")
    assert r_detail.status_code == 200
    assert r_detail.json()["city"] == "piura"
    assert "_links" in r_detail.json()

    r_missing = client.get(f"/api/scraping/posts/{uuid.uuid4()}")
    assert r_missing.status_code == 404


def test_scraped_posts_export_json():
    r = client.get("/api/scraping/export")
    assert r.status_code == 200
    payload = r.json()
    assert "attachment" in r.headers.get("content-disposition", "")
    assert payload["total"] == len(payload["posts"])
    assert {"telefonos", "imagenes", "texto", "ciudad"} <= set(payload["posts"][0])
