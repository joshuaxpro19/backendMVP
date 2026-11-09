"""Facebook post scraper (Playwright, sync API).

Port of the proof-of-concept Node script: searches Facebook posts, scrolls
through the lazy-loaded results, extracts text / author / phones / images and
optionally downloads the images to disk.
"""

from __future__ import annotations

import hashlib
import random
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright

from app.scraping.text_utils import (
    PROFILE_EXCLUDE_RE,
    clean_lines,
    extract_phones,
    extract_whatsapp,
    match_location,
    pick_author,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Each search result card is mounted in a div[aria-posinset] inside role=feed.
_EXTRACT_JS = """
() => {
  const out = [];
  const DATE_RE =
    /^(hace\\s|lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|\\d{1,2}\\s+de\\s)/i;
  const NOISE = new Set(['Unirte', 'Seguir', 'Unirse', 'Ver más', 'Responder', 'Compartir']);
  const SKIP = new Set(['Facebook', 'Indicador de estado online', 'Activo', 'Contenido de IA']);
  const SYMBOL = /^[\\s·•|.,:;\\-–—]+$/;

  for (const el of document.querySelectorAll('div[aria-posinset]')) {
    const lines = (el.innerText || '')
      .split('\\n')
      .map((l) => l.trim())
      .filter((l) => l && !SKIP.has(l) && !SYMBOL.test(l));
    const texto = lines.join('\\n');
    if (texto.length < 20) continue;

    const imagenes = [...el.querySelectorAll('img')]
      .map((i) => i.src)
      .filter((s) => s && s.startsWith('http') && !s.includes('emoji') && !s.includes('static/'));

    const enlaces = [
      ...new Set(
        [...el.querySelectorAll('a[href]')].map((a) => {
          try {
            const u = new URL(a.href);
            u.search = '';
            u.hash = '';
            return u.href;
          } catch (e) {
            return a.href;
          }
        }),
      ),
    ];

    const di = lines.findIndex((l) => DATE_RE.test(l));
    let autor = null;
    if (di > 0) {
      for (let i = di - 1; i >= 0 && i >= di - 3; i--) {
        if (!NOISE.has(lines[i]) && lines[i].length <= 70) {
          autor = lines[i];
          break;
        }
      }
    }

    const postLink = enlaces.find((l) => /story_fbid=|\\/posts\\/\\d+/.test(l)) || null;
    const container = enlaces.find((l) => /facebook\\.com\\/(groups|pages)\\//.test(l)) || null;
    const profile =
      enlaces.find(
        (l) =>
          /facebook\\.com\\/(profile\\.php\\?id=|[^/?#]+\\/?$)/.test(l) &&
          !/facebook\\.com\\/(search|marketplace|watch|gaming|groups|pages|events|photos?|reels|menu|home|login|help|settings|privacy|terms|ads|business|story\\.php|permalink\\.php|video)/.test(
            l,
          ),
      ) || null;

    out.push({
      autor,
      fecha: di >= 0 ? lines[di] : null,
      grupo_o_pagina: container ? lines[0] : null,
      texto,
      imagenes,
      enlaces: enlaces.filter((l) => !l.includes('/search/')).slice(0, 6),
      url_post: postLink || container || profile,
      tipo: container ? (container.includes('/groups/') ? 'grupo' : 'pagina') : 'perfil',
      url_perfil: profile,
    });
  }
  return out;
}
"""


class FacebookScraperError(RuntimeError):
    """Raised when Facebook blocks the run (login wall, checkpoint, rate limit)."""


def content_hash(url_post: Optional[str], content: str) -> str:
    seed = url_post or content[:200]
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _sleep(low: float = 0.25, high: float = 0.6) -> None:
    time.sleep(random.uniform(low, high))


class FacebookScraper:
    def __init__(
        self,
        *,
        email: Optional[str] = None,
        password: Optional[str] = None,
        state_path: Optional[str] = None,
        headless: bool = True,
        images_dir: str = "data/scraping_images",
        max_images: int = 60,
        timeout_ms: int = 60000,
    ) -> None:
        self.email = email
        self.password = password
        self.state_path = Path(state_path) if state_path else None
        self.headless = headless
        self.images_dir = Path(images_dir)
        self.max_images = max_images
        self.timeout_ms = timeout_ms

    # ---------------------------------------------------------------- session
    def _ensure_session(self, page: Page) -> None:
        """Reuse a saved session; otherwise log in with the configured credentials."""
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(2500)

        if self._is_logged_in(page):
            return

        if not (self.email and self.password):
            raise FacebookScraperError(
                "Sesión de Facebook no válida y faltan FB_EMAIL/FB_PASSWORD en el entorno."
            )

        page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.fill('input[name="email"]', self.email)
        page.fill('input[name="pass"]', self.password)
        page.press('input[name="pass"]', "Enter")
        page.wait_for_timeout(6000)

        if "checkpoint" in page.url:
            raise FacebookScraperError(
                "Facebook pidió verificación (checkpoint). Resuélvelo manualmente en una sesión con UI."
            )

        if not self._is_logged_in(page):
            raise FacebookScraperError("Facebook rechazó las credenciales (FB_EMAIL / FB_PASSWORD).")

        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            page.context.storage_state(path=str(self.state_path))

    @staticmethod
    def _is_logged_in(page: Page) -> bool:
        if "login" in page.url or "checkpoint" in page.url:
            return False
        # Logged-out pages always render the password field.
        return page.locator('input[name="pass"]').count() == 0

    # --------------------------------------------------------------- scrolling
    @staticmethod
    def _human_scroll(page: Page) -> None:
        for _ in range(random.randint(3, 6)):
            page.mouse.wheel(0, random.randint(400, 900))
            _sleep(0.25, 0.65)

    # ------------------------------------------------------------------ search
    def run(
        self,
        *,
        queries: list[str],
        city: str,
        localities: list[str],
        scrolls_per_query: int = 3,
        download_images: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        stats: dict[str, Any] = {
            "queries": len(queries),
            "found": 0,
            "out_of_city": 0,
            "images_downloaded": 0,
        }
        seen: set[str] = set()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            storage = str(self.state_path) if self.state_path and self.state_path.exists() else None
            context = browser.new_context(
                storage_state=storage,
                viewport={"width": 1280, "height": 900},
                locale="es-419",
                user_agent=USER_AGENT,
            )
            page = context.new_page()
            self._ensure_session(page)

            for query in queries:
                url = f"https://www.facebook.com/search/posts/?q={quote(query)}"
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_timeout(random.randint(3000, 5000))

                stagnant = 0
                for _ in range(scrolls_per_query):
                    self._human_scroll(page)
                    page.wait_for_timeout(random.randint(1000, 2200))

                    batch = page.evaluate(_EXTRACT_JS)
                    new_in_round = 0
                    for item in batch:
                        key = content_hash(item.get("url_post"), item.get("texto", ""))
                        if key in seen:
                            continue
                        seen.add(key)

                        full_text = f"{item.get('texto') or ''}\n{item.get('grupo_o_pagina') or ''}"
                        location = match_location(full_text, city, localities)
                        if not location:
                            stats["out_of_city"] += 1
                            continue

                        posts.append(
                            {
                                "author": item.get("autor"),
                                "posted_at": item.get("fecha"),
                                "source_name": item.get("grupo_o_pagina"),
                                "source_type": item.get("tipo") or "perfil",
                                "content": item.get("texto") or "",
                                "city": location,
                                "phones": extract_phones(item.get("texto") or ""),
                                "whatsapp": extract_whatsapp(item.get("texto") or ""),
                                "image_urls": item.get("imagenes") or [],
                                "image_files": [],
                                "post_url": item.get("url_post"),
                                "profile_url": item.get("url_perfil"),
                                "query_origen": query,
                                "content_hash": key,
                            }
                        )
                        new_in_round += 1

                    stats["found"] += len(batch)
                    if new_in_round == 0:
                        stagnant += 1
                        if stagnant >= 3:
                            break
                    else:
                        stagnant = 0

            if download_images:
                stats["images_downloaded"] = self._download_images(context, posts)

            browser.close()

        return posts, stats

    # ------------------------------------------------------------------ images
    def _download_images(self, context, posts: list[dict[str, Any]]) -> int:
        downloaded = 0
        self.images_dir.mkdir(parents=True, exist_ok=True)

        for index, post in enumerate(posts):
            for position, src in enumerate(post["image_urls"][:3]):
                if downloaded >= self.max_images:
                    return downloaded
                try:
                    response = context.request.get(src, timeout=20000)
                    if not response.ok:
                        continue
                    extension = _image_extension(src)
                    target = self.images_dir / f"post_{index:03d}_{position}.{extension}"
                    target.write_bytes(response.body())
                    post["image_files"].append(str(target))
                    downloaded += 1
                    _sleep(0.25, 0.65)
                except Exception:
                    continue
            _sleep(0.1, 0.25)
        return downloaded


def _image_extension(url: str) -> str:
    found = re.search(r"\.(jpg|jpeg|png|webp|avif)", url, re.I)
    return found.group(1).lower() if found else "jpg"


# Re-exported for callers that only need the parsing helpers.
__all__ = [
    "FacebookScraper",
    "FacebookScraperError",
    "content_hash",
    "clean_lines",
    "extract_phones",
    "extract_whatsapp",
    "match_location",
    "pick_author",
    "PROFILE_EXCLUDE_RE",
]
