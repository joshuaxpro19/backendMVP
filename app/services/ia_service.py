"""Revisión de publicaciones de Facebook con un modelo de visión (OpenRouter).

El modelo recibe el texto y, si existe, la imagen del post; traduce/limpia el
texto, decide si es una oferta real de servicio y extrae teléfono y ubicación
(incluso si solo aparecen en la imagen).

La API key se guarda en la tabla `ajustes` (o se toma de OPENROUTER_API_KEY).
"""

import base64
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.domain.catalogos import CATEGORIAS
from app.domain.models.reporte import Ajuste
from app.domain.models.scraped_post import ScrapedPost

CLAVE_API = "openrouter_api_key"
CLAVE_MODELO = "openrouter_model"

SISTEMA = """Eres el moderador de DelBarrio, un directorio vecinal donde solo se publican \
ofertas reales de servicios o productos de personas del barrio (gasfitería, carpintería, \
electricidad, clases, fletes, alimentos, etc.).

Recibirás el texto y, si existe, la imagen de una publicación de Facebook. Tu tarea:

1. Traduce y limpia el texto al español neutro. Ignora el ruido de Facebook \
("Ver más", "Unirte", "Seguir", contadores de reacciones, nombres de grupos, fechas).
2. Decide si es una OFERTA REAL de servicio o producto de un vecino. Rechaza memes, \
noticias, política, ventas de cuentas, spam, publicaciones sin oferta, pedidos genéricos \
sin datos de contacto ni propuesta, o cualquier cosa que no sirva para contratar a alguien.
3. Si hay un teléfono (Perú, 9 dígitos, puede empezar en 9) en el texto O en la imagen, \
extráelo sin espacios.
4. Si hay una ubicación (distrito, sector, ciudad) en el texto o en la imagen, extráela.
5. Asigna UNA categoría de esta lista: gasfitería, carpintería, electricidad, cerrajería, \
clases, alimentos, paseo de mascotas, herramientas, movilidad, préstamo, otros.

Responde SOLO con JSON válido, sin markdown, con este esquema exacto:
{"es_servicio": true|false,
 "motivo": "por qué lo apruebas o rechazas (máx 160 caracteres)",
 "titulo": "título corto y claro (máx 90 caracteres)",
 "descripcion": "descripción útil para el vecino (máx 400 caracteres)",
 "categoria": "una de la lista",
 "telefono": "9 dígitos o null",
 "ubicacion": "texto o null"}"""


class IaError(Exception):
    """Error al hablar con OpenRouter."""


# --- configuración ----------------------------------------------------------


def _leer(db: Session, clave: str) -> str:
    fila = db.query(Ajuste).filter(Ajuste.clave == clave).first()
    return (fila.valor or "") if fila else ""


def _guardar(db: Session, clave: str, valor: str) -> None:
    fila = db.query(Ajuste).filter(Ajuste.clave == clave).first()
    if fila:
        fila.valor = valor
        fila.actualizado = datetime.now(timezone.utc)
    else:
        db.add(Ajuste(clave=clave, valor=valor, actualizado=datetime.now(timezone.utc)))
    db.commit()


def obtener_config(db: Session) -> tuple[str, str]:
    """(api_key, modelo) con la tabla `ajustes` por delante del .env."""
    api_key = _leer(db, CLAVE_API) or (settings.openrouter_api_key or "")
    modelo = _leer(db, CLAVE_MODELO) or settings.openrouter_model
    return api_key.strip(), modelo.strip()


def configurar(db: Session, api_key: Optional[str], modelo: Optional[str]) -> None:
    if api_key is not None:
        _guardar(db, CLAVE_API, api_key.strip())
    if modelo is not None and modelo.strip():
        _guardar(db, CLAVE_MODELO, modelo.strip())


def estado(db: Session) -> dict[str, Any]:
    total = db.query(ScrapedPost).filter(ScrapedPost.is_active.is_(True)).count()
    pendientes = (
        db.query(ScrapedPost)
        .filter(ScrapedPost.is_active.is_(True), ScrapedPost.ia_estado.is_(None))
        .count()
    )
    aprobados = (
        db.query(ScrapedPost)
        .filter(ScrapedPost.is_active.is_(True), ScrapedPost.ia_estado == "aprobado")
        .count()
    )
    rechazados = (
        db.query(ScrapedPost)
        .filter(ScrapedPost.is_active.is_(True), ScrapedPost.ia_estado == "rechazado")
        .count()
    )
    return {
        "total": total,
        "pendientes": pendientes,
        "aprobados": aprobados,
        "rechazados": rechazados,
    }


# --- llamada al modelo ------------------------------------------------------


def _imagen_data_url(post: ScrapedPost) -> Optional[str]:
    """Primera imagen local del post, como data URL (si no pesa demasiado)."""
    limite = settings.ia_max_imagen_kb * 1024
    for ruta in post.image_files or []:
        archivo = Path(str(ruta))
        if not archivo.exists() or not archivo.is_file() or archivo.stat().st_size > limite:
            continue
        extension = archivo.suffix.lower().lstrip(".")
        mime = {"png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(
            extension, "image/jpeg"
        )
        datos = base64.b64encode(archivo.read_bytes()).decode()
        return f"data:{mime};base64,{datos}"
    return None


def _parsear_json(texto: str) -> dict[str, Any]:
    limpio = (texto or "").strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```[a-zA-Z]*\s*", "", limpio)
        limpio = re.sub(r"\s*```$", "", limpio)
    inicio, fin = limpio.find("{"), limpio.rfind("}")
    if inicio == -1 or fin == -1:
        raise IaError("La IA no devolvió JSON")
    try:
        return json.loads(limpio[inicio : fin + 1])
    except json.JSONDecodeError as exc:
        raise IaError(f"JSON inválido de la IA: {exc}") from exc


def _llamar_openrouter(api_key: str, modelo: str, texto: str, imagen: Optional[str]) -> dict[str, Any]:
    contenido: list[dict[str, Any]] = [{"type": "text", "text": (texto or "")[:4000]}]
    if imagen:
        contenido.append({"type": "image_url", "image_url": {"url": imagen}})

    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": contenido},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    peticion = urllib.request.Request(
        f"{settings.openrouter_base.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://delbarrio.app",
            "X-Title": "DelBarrio",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=90) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "ignore")[:300]
        raise IaError(f"OpenRouter {exc.code}: {detalle}") from exc
    except Exception as exc:  # noqa: BLE001
        raise IaError(f"No se pudo consultar la IA: {exc}") from exc

    try:
        mensaje = datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise IaError("Respuesta inesperada de OpenRouter") from exc
    return _parsear_json(mensaje)


# --- revisión por lotes -----------------------------------------------------


def revisar_pendientes(db: Session, limite: int = 5) -> dict[str, Any]:
    """Revisa hasta `limite` posts sin revisar. Devuelve un resumen."""
    api_key, modelo = obtener_config(db)
    if not api_key:
        raise ValueError("Configura tu API key de OpenRouter primero")

    posts = (
        db.query(ScrapedPost)
        .filter(ScrapedPost.is_active.is_(True), ScrapedPost.ia_estado.is_(None))
        .order_by(ScrapedPost.captured_at.desc())
        .limit(limite)
        .all()
    )

    resumen = {"revisados": 0, "aprobados": 0, "rechazados": 0, "con_telefono": 0, "errores": 0}
    ultimo_error = ""

    for post in posts:
        try:
            resultado = _llamar_openrouter(api_key, modelo, post.content, _imagen_data_url(post))
        except IaError as exc:
            resumen["errores"] += 1
            ultimo_error = str(exc)
            continue

        aprobado = bool(resultado.get("es_servicio"))
        post.ia_estado = "aprobado" if aprobado else "rechazado"
        post.ia_motivo = (str(resultado.get("motivo") or ""))[:500] or None
        post.ia_titulo = (str(resultado.get("titulo") or "")).strip()[:200] or None
        post.ia_descripcion = (str(resultado.get("descripcion") or "")).strip()[:2000] or None

        categoria = (str(resultado.get("categoria") or "")).strip().lower()
        post.ia_categoria = categoria if categoria in CATEGORIAS else ("otros" if aprobado else None)

        telefono = re.sub(r"\D", "", str(resultado.get("telefono") or ""))
        if len(telefono) == 11 and telefono.startswith("51"):
            telefono = telefono[2:]
        # Solo celulares peruanos: 9 dígitos que empiezan en 9.
        post.ia_telefono = telefono if re.fullmatch(r"9\d{8}", telefono) else None

        ubicacion = (str(resultado.get("ubicacion") or "")).strip()
        post.ia_ubicacion = ubicacion[:120] or None
        post.ia_revisado = datetime.now(timezone.utc)

        resumen["revisados"] += 1
        if aprobado:
            resumen["aprobados"] += 1
            if post.ia_telefono:
                resumen["con_telefono"] += 1
        else:
            resumen["rechazados"] += 1
        db.commit()

    if ultimo_error:
        resumen["ultimo_error"] = ultimo_error
    return resumen
