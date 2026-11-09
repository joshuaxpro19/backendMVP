"""Planificador en segundo plano: scrapear cada N horas y limpiar con IA.

- Scrape: cada `SCRAPE_CADA_HORAS` (por defecto 6), solo si hay sesión de
  Facebook (FB_EMAIL/FB_PASSWORD o `data/fb_state.json`). Así no se satura
  Facebook con peticiones constantes.
- IA: mientras haya publicaciones sin revisar, procesa `IA_LOTE` por minuto.
- Un fallo seguido de la IA (sin créditos, key inválida) espera 30 min.

Se arranca desde el lifespan de FastAPI en un hilo daemon: no bloquea la API.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config.settings import settings
from app.domain.models.reporte import Ajuste
from app.domain.models.scraped_post import ScrapedPost
from app.infrastructure.database.connection import SessionLocal
from app.services import ia_service

log = logging.getLogger("delbarrio.scheduler")
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("INFO:     [planificador] %(message)s"))
    log.addHandler(_handler)
log.setLevel(logging.INFO)
log.propagate = False

CLAVE_ULTIMO = "auto_scrape_ultimo"
CLAVE_ERROR = "auto_scrape_error"

_ESPERA_IA_FALLO = 30 * 60  # segundos
_ESPERA_SCRAPE_FALLO = 30 * 60

_hilo: threading.Thread | None = None
_parar = threading.Event()
_ia_cooldown_hasta = 0.0
_scrape_cooldown_hasta = 0.0


# --- estado persistente ------------------------------------------------------


def _leer(db, clave: str) -> str:
    fila = db.query(Ajuste).filter(Ajuste.clave == clave).first()
    return (fila.valor or "") if fila else ""


def _guardar(db, clave: str, valor: str) -> None:
    fila = db.query(Ajuste).filter(Ajuste.clave == clave).first()
    ahora = datetime.now(timezone.utc)
    if fila:
        fila.valor = valor
        fila.actualizado = ahora
    else:
        db.add(Ajuste(clave=clave, valor=valor, actualizado=ahora))
    db.commit()


def marcar_scrape(db) -> None:
    """Registra que el scraping se ejecutó (programado o manual)."""
    _guardar(db, CLAVE_ULTIMO, datetime.now(timezone.utc).isoformat())
    _guardar(db, CLAVE_ERROR, "")


def puede_scrapear() -> bool:
    if settings.fb_email and settings.fb_password:
        return True
    return Path(settings.fb_state_path).exists()


def estado(db) -> dict:
    ultimo = _leer(db, CLAVE_ULTIMO)
    proximo = None
    if ultimo:
        try:
            proximo = (
                datetime.fromisoformat(ultimo) + timedelta(hours=settings.scrape_cada_horas)
            ).isoformat()
        except ValueError:
            proximo = None
    return {
        "activo": bool(_hilo and _hilo.is_alive()),
        "scrape_cada_horas": settings.scrape_cada_horas,
        "ultimo_scrape": ultimo or None,
        "proximo_scrape": proximo,
        "puede_scrapear": puede_scrapear(),
        "ultimo_error": _leer(db, CLAVE_ERROR) or None,
        "ia_auto": settings.ia_auto,
        "ia_lote": settings.ia_lote,
    }


# --- ciclo -------------------------------------------------------------------


def iniciar() -> None:
    global _hilo
    if not settings.automatizacion or _hilo is not None:
        return
    _parar.clear()
    _hilo = threading.Thread(target=_bucle, name="delbarrio-scheduler", daemon=True)
    _hilo.start()
    log.info(
        "planificador iniciado: scrape cada %s h, IA automática=%s",
        settings.scrape_cada_horas,
        settings.ia_auto,
    )


def detener() -> None:
    _parar.set()


def _bucle() -> None:
    time.sleep(20)  # deja terminar el arranque de la API
    while not _parar.is_set():
        try:
            _tick()
        except Exception:  # noqa: BLE001
            log.exception("fallo en el ciclo del planificador")
        _parar.wait(60)


def _tick() -> None:
    global _ia_cooldown_hasta
    db = SessionLocal()
    try:
        _limpiar_con_ia(db)
        _scrapear_si_toca(db)
    finally:
        db.close()


def _limpiar_con_ia(db) -> None:
    global _ia_cooldown_hasta
    if not settings.ia_auto or time.time() < _ia_cooldown_hasta:
        return

    pendientes = (
        db.query(ScrapedPost)
        .filter(ScrapedPost.is_active.is_(True), ScrapedPost.ia_estado.is_(None))
        .count()
    )
    if not pendientes:
        return

    api_key, _ = ia_service.obtener_config(db)
    if not api_key:
        return

    try:
        resumen = ia_service.revisar_pendientes(db, settings.ia_lote)
    except Exception as exc:  # noqa: BLE001
        log.warning("IA automática falló: %s", exc)
        _ia_cooldown_hasta = time.time() + _ESPERA_IA_FALLO
        return

    if resumen["revisados"]:
        log.info(
            "IA: %s revisadas (%s aprobadas, %s rechazadas)",
            resumen["revisados"],
            resumen["aprobados"],
            resumen["rechazados"],
        )
    if resumen["errores"] and not resumen["revisados"]:
        log.warning("IA sin avances (%s errores); espera 30 min", resumen["errores"])
        _ia_cooldown_hasta = time.time() + _ESPERA_IA_FALLO


def _scrapear_si_toca(db) -> None:
    global _scrape_cooldown_hasta
    if time.time() < _scrape_cooldown_hasta:
        return  # tras un fallo no se reintenta cada minuto

    ultimo = _leer(db, CLAVE_ULTIMO)
    ahora = datetime.now(timezone.utc)
    if ultimo:
        try:
            if ahora - datetime.fromisoformat(ultimo) < timedelta(hours=settings.scrape_cada_horas):
                return
        except ValueError:
            pass

    if not puede_scrapear():
        return  # sin sesión de Facebook: no se intenta

    log.info("scraping programado: inicio")
    try:
        from app.api.schemas.scraped_post import ScrapingRunRequest
        from app.services import scraping_service

        resultado = scraping_service.run(db, ScrapingRunRequest())
        marcar_scrape(db)
        log.info("scraping: %s publicaciones nuevas", resultado.get("saved", 0))
    except Exception as exc:  # noqa: BLE001
        _guardar(db, CLAVE_ERROR, str(exc)[:300])
        _scrape_cooldown_hasta = time.time() + _ESPERA_SCRAPE_FALLO
        log.warning("scraping falló: %s (reintento en 30 min)", exc)
