"""Extracción de reportes y boletines públicos de INDECI.

La fuente es un portal público del Estado peruano. No se intenta saltar
protecciones: solo se lee el HTML de la página de monitoreo y se normalizan
los enlaces que el propio portal publica.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Iterable, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.config.settings import settings

DEFAULT_SOURCE = "INDECI"
DEFAULT_URL = "https://portal.indeci.gob.pe/informe/informe-de-peligros/"
USER_AGENT = "VecinalSolidaria/1.0 (+https://github.com/Pierre-code189/app-vecinal-mobile)"

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _sin_acentos(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def _limpiar(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parsear_fecha(texto: str) -> Optional[datetime]:
    """Intenta leer la fecha que INDECI incluye en el título del reporte."""
    if not texto:
        return None

    # Formatos numéricos: 8/11/2026 o 08-11-2026
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", texto)
    if m:
        dia, mes, anio = (int(x) for x in m.groups())
        try:
            return datetime(anio, mes, dia, tzinfo=timezone.utc)
        except ValueError:
            pass

    # Formatos con mes escrito: "8 de noviembre de 2026" o "08DE NOVIEMBRE DE 2026"
    normalizado = _sin_acentos(texto).lower()
    m = re.search(
        r"(\d{1,2})\s*(?:de)?\s*([a-z]+)\s*(?:de)?\s*(\d{4})", normalizado
    )
    if m:
        dia = int(m.group(1))
        mes = _MONTHS.get(m.group(2))
        anio = int(m.group(3))
        if mes:
            try:
                return datetime(anio, mes, dia, tzinfo=timezone.utc)
            except ValueError:
                pass
    return None


def _categoria(titulo: str) -> str:
    t = _sin_acentos(titulo).upper()
    if "REPORTE" in t:
        return "reporte"
    if "BOLETIN" in t:
        return "boletin"
    if "AVISO" in t:
        return "aviso"
    return "otro"


def parsear_indeci(html: str, base_url: str = DEFAULT_URL) -> list[dict]:
    """Convierte el HTML de INDECI en una lista de noticias normalizadas."""
    soup = BeautifulSoup(html, "lxml")
    resultados: list[dict] = []
    vistos: set[str] = set()

    for article in soup.find_all("article"):
        encabezado = article.find(["h2", "h3"])
        if not encabezado:
            continue
        enlace = encabezado.find("a", href=True)
        if not enlace:
            continue

        titulo = _limpiar(encabezado.get_text(" ", strip=True))
        if not titulo or not re.search(r"REPORTE|BOLET|AVISO", titulo, re.I):
            continue

        url = urljoin(base_url, enlace["href"].strip())
        if url in vistos:
            continue
        vistos.add(url)

        pdf = article.select_one("a.btn-download[href]")
        resultados.append(
            {
                "source": DEFAULT_SOURCE,
                "external_id": url,
                "title": titulo,
                "summary": None,
                "url": url,
                "pdf_url": urljoin(base_url, pdf["href"].strip()) if pdf else None,
                "category": _categoria(titulo),
                "published_at": parsear_fecha(titulo),
            }
        )

    # Más recientes primero cuando la fecha se pudo interpretar.
    resultados.sort(
        key=lambda item: item["published_at"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return resultados


def obtener_indeci(
    url: Optional[str] = None,
    timeout: Optional[int] = None,
    client: Optional[httpx.Client] = None,
) -> list[dict]:
    """Descarga y parsea la página pública de INDECI."""
    destino = url or getattr(settings, "indeci_url", DEFAULT_URL)
    limite = timeout or getattr(settings, "http_timeout_seconds", 45)

    propio = client is None
    if propio:
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=limite,
            follow_redirects=True,
        )
    try:
        respuesta = client.get(destino)
        respuesta.raise_for_status()
        return parsear_indeci(respuesta.text, base_url=str(respuesta.url))
    finally:
        if propio and client is not None:
            client.close()


def guardar_indeci(db, noticias: Iterable[dict]) -> dict:
    """Inserta o actualiza las noticias sin duplicar por fuente + external_id."""
    from app.domain.models.news import NewsItem

    creadas = actualizadas = 0
    for datos in noticias:
        existente = (
            db.query(NewsItem)
            .filter(
                NewsItem.source == datos["source"],
                NewsItem.external_id == datos["external_id"],
            )
            .first()
        )
        if existente:
            for campo in ("title", "summary", "url", "pdf_url", "category", "published_at"):
                setattr(existente, campo, datos.get(campo))
            actualizadas += 1
        else:
            db.add(NewsItem(**datos))
            creadas += 1
    db.commit()
    return {"created": creadas, "updated": actualizadas, "total": creadas + actualizadas}
