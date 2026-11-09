"""Contrato que consume el front de Vecinal Solidaria (`front/web`).

Fase 1 (núcleo): cuenta, perfil, catálogos, publicaciones y fotos.
El detalle completo de qué envía/recibe cada endpoint está en
`front/API-CONTRATO.md`. Lo que queda para la fase 2 (cotizaciones, tratos,
mensajes, moderación) sigue sin existir aquí y devuelve 404.
"""

import base64
import binascii
import math
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.schemas.vecinal import (
    EmergenciaIn,
    IaConfigIn,
    IaRevisarIn,
    LoginIn,
    PerfilIn,
    PublicacionIn,
    PublicacionPatch,
    RegistroIn,
    ReporteIn,
    VistoIn,
)
from app.config.settings import settings
from app.domain.models.publicacion import Publicacion, PublicacionVisto
from app.domain.models.reporte import Ajuste, Reporte
from app.domain.models.role import Roles
from app.domain.models.scraped_post import ScrapedPost
from app.domain.models.user import User
from app.infrastructure.database.connection import get_db
from app.services import ia_service, scheduler
from app.usecases.auth import (
    create_access_token,
    get_current_active_user,
    hash_password,
    verify_password,
)

router = APIRouter(tags=["Vecinal (front)"])

# Sector por defecto del front y catálogo de zonas (nombre + centro aproximado).
ZONAS = [
    {"nombre": "Piura Centro", "lat": -5.1945, "lng": -80.6328},
    {"nombre": "Castilla", "lat": -5.1994, "lng": -80.6475},
    {"nombre": "Catacaos", "lat": -5.2667, "lng": -80.6833},
    {"nombre": "Veintiséis de Octubre", "lat": -5.1333, "lng": -80.6167},
    {"nombre": "Los Pinos", "lat": -5.1594, "lng": -80.6103},
    {"nombre": "Miraflores", "lat": -5.1789, "lng": -80.6139},
    {"nombre": "Obrero", "lat": -5.1864, "lng": -80.6647},
    {"nombre": "Sullana", "lat": -4.9075, "lng": -80.6864},
    {"nombre": "Paita", "lat": -5.0944, "lng": -81.1056},
    {"nombre": "Talara", "lat": -4.5767, "lng": -81.2714},
]

DIRECTORIO = [
    {"id": "policial", "nombre": "Policía Nacional", "detalle": "Emergencias y delitos", "telefono": "105"},
    {"id": "bomberos", "nombre": "Bomberos Voluntarios", "detalle": "Incendios y rescate", "telefono": "116"},
    {"id": "defensa", "nombre": "Defensa Civil", "detalle": "Desastres y evacuación", "telefono": "115"},
    {"id": "samu", "nombre": "SAMU", "detalle": "Ambulancias", "telefono": "106"},
    {"id": "salud-barrio", "nombre": "Puesto de salud del barrio", "detalle": "Atención primaria 24 h", "telefono": "01"},
]

ROLES_FRONT = {
    Roles.USER: "vecino",
    Roles.MOD: "moderador",
    Roles.ADMIN: "admin",
}

# --- catálogos (los mismos del backend de referencia) -----------------------

from app.domain.catalogos import (
    CATEGORIAS,
    ESTADOS_PUB,
    MEDIOS_PAGO,
    NECESIDADES_72H,
    POLITICAS_PAGO,
    SUBTIPOS_FAVOR,
    TIPOS,
)

ZONA_CENTRO = {z["nombre"]: (z["lat"], z["lng"]) for z in ZONAS}

# Palabras que la regla de movilidad nunca deja publicar (datos del menor).
PROHIBIDO_MOVILIDAD = ("colegio ", "escuela ", "dni", "mi hijo se llama")

# --- límite de peticiones (en memoria, por IP) ------------------------------
# Igual que el backend de referencia: se pierde al reiniciar el proceso; para un
# MVP con una sola instancia es suficiente.

_RL: dict[str, list[float]] = {}
RL_RULES = {  # ruta: (máximo, ventana en segundos)
    "/api/login": (30, 60),
    "/api/registro": (12, 300),
    "/api/publicaciones": (30, 60),
    "/api/vistos": (40, 60),
    "/api/reportes": (10, 300),
}


def rate_limit(request: Request, ruta: str) -> None:
    regla = RL_RULES.get(ruta)
    if not regla:
        return
    limite, ventana = regla
    ip = request.client.host if request.client else "?"
    clave = f"{ruta}:{ip}"
    ahora = time.time()
    hits = [t for t in _RL.get(clave, []) if ahora - t < ventana]
    if len(hits) >= limite:
        raise HTTPException(429, "Demasiadas solicitudes. Espera un momento.")
    hits.append(ahora)
    _RL[clave] = hits


# --- utilidades -------------------------------------------------------------


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _unix(dt: Optional[datetime]) -> int:
    """El front formatea los timestamps con `hace()` en segundos Unix."""
    if not dt:
        return 0
    if dt.tzinfo is None:  # SQLite devuelve naive UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _digitos(valor: Optional[str]) -> str:
    d = re.sub(r"\D", "", valor or "")
    if len(d) == 11 and d.startswith("51"):
        d = d[2:]
    return d[:9] if len(d) >= 9 else ""


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 3)


def _distancia(p: Publicacion, ref: tuple[Optional[float], Optional[float]]) -> Optional[float]:
    """Distancia real (servidor) entre el sector y la publicación, si hay datos."""
    if ref[0] is None or ref[1] is None or p.lat is None:
        return None
    return _haversine(ref[0], ref[1], p.lat, p.lng if p.lng is not None else 0)


def _jitter(lat: float, lng: float) -> tuple[float, float]:
    """Desplaza 300-500 m la coordenada que se publica (privacidad del vecino)."""
    import random

    metros = random.uniform(300, 500)
    rad = random.uniform(0, 2 * math.pi)
    dlat = (metros * math.cos(rad)) / 111320.0
    dlng = (metros * math.sin(rad)) / (111320.0 * max(0.1, math.cos(math.radians(lat))))
    return round(lat + dlat, 6), round(lng + dlng, 6)


def usuario_opcional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Usuario si hay un Bearer válido; anónimo si no lo hay o es inválido."""
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(
            cabecera[7:], settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    except (JWTError, ValueError, TypeError):
        return None


def _rol(user: Optional[User]) -> str:
    return ROLES_FRONT.get(user.role, "vecino") if user else "vecino"


def perfil_dict(user: User, db: Session) -> dict:
    """`GET /api/perfil` — la forma que pinta `Perfil.jsx` y `Auth.jsx`."""
    publicaciones = (
        db.query(Publicacion)
        .filter(Publicacion.autor_id == user.id, Publicacion.deleted_at.is_(None))
        .count()
    )
    vistos = (
        db.query(PublicacionVisto)
        .join(Publicacion, Publicacion.id == PublicacionVisto.publicacion_id)
        .filter(Publicacion.autor_id == user.id)
        .count()
    )
    return {
        "id": str(user.id),
        "nombre": user.full_name,
        "email": user.email,
        "telefono": _digitos(user.phone),
        "zona": getattr(user, "zona", "") or "Piura Centro",
        "yape": getattr(user, "yape", "") or "",
        "plin": getattr(user, "plin", "") or "",
        "rol": _rol(user),
        "telefono_verificado": bool(getattr(user, "telefono_verificado", False)),
        "mostrar_contacto": bool(getattr(user, "mostrar_contacto", True)),
        "publicaciones": publicaciones,
        "vistos_recibidos": vistos,
        "tratos_cerrados": 0,
    }


def serializar(
    p: Publicacion,
    user: Optional[User],
    ref: Optional[tuple[Optional[float], Optional[float]]] = None,
    visto: bool = False,
) -> dict[str, Any]:
    """Forma de una publicación tal como la pinta el front.

    Privacidad: el contacto y la distancia solo se devuelven con sesión
    iniciada, igual que el backend de referencia.
    """
    autor = p.autor
    tel_autor = _digitos(autor.phone) if autor else ""
    wa = ""
    if p.wa:
        wa = _digitos(p.telefono_externo) or tel_autor

    es_mio = bool(user and user.id == p.autor_id)
    permite = bool(p.mostrar_contacto) or es_mio

    if user and permite:
        telefono = tel_autor or None
        whatsapp = wa or None
        yape_autor = (autor.yape or None) if autor else None
        plin_autor = (autor.plin or None) if autor else None
    else:
        telefono = whatsapp = yape_autor = plin_autor = None

    # La distancia se calcula con la coordenada exacta, que nunca sale al cliente.
    dist = None
    if user and ref and ref[0] is not None and ref[1] is not None and p.lat is not None:
        dist = _haversine(ref[0], ref[1], p.lat, p.lng if p.lng is not None else 0)

    # «Aproximada» = la coordenada es el centro del sector, no un GPS propio.
    centro = ZONA_CENTRO.get(p.zona or "")
    aproximada = bool(
        centro
        and p.lat is not None
        and p.lng is not None
        and abs(p.lat - centro[0]) < 0.0015
        and abs(p.lng - centro[1]) < 0.0015
    )

    return {
        "id": str(p.id),
        "autor_id": str(p.autor_id),
        "titulo": p.titulo,
        "tipo": p.tipo,
        "subtipo_favor": p.subtipo_favor,
        "categoria": p.categoria,
        "descripcion": p.descripcion or "",
        "precio": p.precio,
        "stock": p.stock,
        "medios_pago": p.medios_pago or "",
        "politica_pago": p.politica_pago or "",
        "zona": p.zona or "",
        "lat_publica": p.lat_publica,
        "lng_publica": p.lng_publica,
        "distancia_km": dist,
        "ubicacion_aproximada": aproximada,
        "punto_encuentro": p.punto_encuentro or "",
        "franja_horaria": p.franja_horaria or "",
        "checklist_ok": bool(p.checklist_ok),
        "es_emergencia": bool(p.es_emergencia),
        "necesidad": p.necesidad,
        "estado": p.estado,
        "vistos": p.vistos or 0,
        "fotos": p.fotos or [],
        "avaladores": p.avaladores or [],
        "contacto_visible": permite if user else False,
        "mostrar_contacto": bool(p.mostrar_contacto),
        "telefono": telefono,
        "whatsapp": whatsapp,
        "yape_autor": yape_autor,
        "plin_autor": plin_autor,
        "nombre": autor.full_name if autor else "",
        "creado": _unix(p.creado),
        "es_mio": es_mio,
        "ya_recomende": visto,
        "origen": p.origen,
        "fuente": p.fuente,
        "url_origen": p.url_origen,
        # Fase 2 (cotizaciones/tratos): el front los lee con `p?.mi_trato`.
        "mi_trato": None,
        "mi_cotizacion": None,
    }


# --- publicaciones traídas de Facebook (scraping) --------------------------
# El scraper guarda los posts en `scraped_posts`; aquí se presentan con la
# misma forma que una publicación local para que salgan en Economía Local.

CATEGORIA_POR_BUSQUEDA = {
    "carpintero": "carpintería",
    "carpinteria": "carpintería",
    "electricista": "electricidad",
    "electricidad": "electricidad",
    "gasfitero": "gasfitería",
    "gasfiter": "gasfitería",
    "plomero": "gasfitería",
    "enfermera": "otros",
    "albañil": "otros",
    "albanil": "otros",
    "clases": "clases",
    "profesor": "clases",
    "mascota": "paseo de mascotas",
}


def _categoria_scraped(post: ScrapedPost) -> str:
    buscado = (post.query_origen or "").lower()
    for clave, categoria in CATEGORIA_POR_BUSQUEDA.items():
        if clave in buscado:
            return categoria
    return "otros"


def _titulo_scraped(contenido: Optional[str]) -> str:
    texto = re.sub(r"\s+", " ", contenido or "").strip()
    if not texto:
        return "Publicación de Facebook"
    if len(texto) <= 90:
        return texto
    corte = texto[:90]
    return (corte[: corte.rfind(" ")] + "…") if " " in corte else corte + "…"


def _fotos_scraped(post: ScrapedPost) -> list[str]:
    """Imágenes locales del scraper (si el archivo existe) o las remotas de FB."""
    from pathlib import Path

    base = Path(settings.scraping_images_dir)
    fotos = []
    for ruta in post.image_files or []:
        nombre = str(ruta).replace("\\", "/").split("/")[-1]
        if nombre and (base / nombre).exists():
            fotos.append(f"/scraping-images/{nombre}")
    if not fotos:
        fotos = [u for u in (post.image_urls or []) if str(u).startswith("http")]
    return fotos[:3]


def serializar_scraped(
    post: ScrapedPost,
    user: Optional[User],
    ref: Optional[tuple[Optional[float], Optional[float]]] = None,
) -> dict[str, Any]:
    """Un post de Facebook con la forma de `Publicacion` que pinta el front.

    Si el post ya pasó por la revisión con IA, se usa su título, descripción,
    categoría, teléfono y ubicación.
    """
    telefono = _digitos((post.phones or [""])[0]) if post.phones else ""
    whatsapp = _digitos((post.whatsapp or [""])[0]) if post.whatsapp else ""
    whatsapp = whatsapp or telefono

    # Lo que extrajo la IA manda (también si el número estaba en la imagen).
    if post.ia_telefono:
        telefono = _digitos(post.ia_telefono) or telefono
        whatsapp = telefono or whatsapp

    ciudad = (post.ia_ubicacion or post.city or "").strip()
    centro = ZONA_CENTRO.get(ciudad) or ZONA_CENTRO.get("Piura Centro") or (None, None)
    dist = None
    if user and ref and ref[0] is not None and centro[0] is not None:
        dist = _haversine(ref[0], ref[1], centro[0], centro[1])

    visible = bool(user)  # misma regla de privacidad que las publicaciones locales
    return {
        "id": str(post.id),
        "autor_id": None,
        "titulo": post.ia_titulo or _titulo_scraped(post.content),
        "tipo": "servicio",
        "subtipo_favor": None,
        "categoria": post.ia_categoria or _categoria_scraped(post),
        "descripcion": post.ia_descripcion or (post.content or "")[:2000],
        "precio": None,
        "stock": None,
        "medios_pago": "",
        "politica_pago": "",
        "zona": ciudad or "Piura",
        "lat_publica": None,
        "lng_publica": None,
        "distancia_km": dist,
        "ubicacion_aproximada": True,
        "punto_encuentro": "",
        "franja_horaria": "",
        "checklist_ok": False,
        "es_emergencia": False,
        "necesidad": None,
        "estado": "activa",
        "vistos": 0,
        "fotos": _fotos_scraped(post),
        "avaladores": [],
        "contacto_visible": visible,
        "mostrar_contacto": True,
        "telefono": telefono if visible else None,
        "whatsapp": whatsapp if visible else None,
        "yape_autor": None,
        "plin_autor": None,
        "nombre": post.author or post.source_name or "Vecino de Facebook",
        "creado": _unix(post.captured_at),
        "es_mio": False,
        "ya_recomende": False,
        "origen": "scraping",
        "fuente": post.source_name or "Facebook",
        "url_origen": post.post_url or post.profile_url,
        "mi_trato": None,
        "mi_cotizacion": None,
    }


def _buscar_scraped(db: Session, publicacion_id: uuid.UUID) -> Optional[ScrapedPost]:
    return (
        db.query(ScrapedPost)
        .filter(ScrapedPost.id == publicacion_id, ScrapedPost.is_active.is_(True))
        .first()
    )


def _ref(query_lat: Optional[str], query_lng: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    try:
        return float(query_lat), float(query_lng)
    except (TypeError, ValueError):
        return None, None


def _exige_moderador(user: User) -> None:
    if user.role not in (Roles.MOD, Roles.ADMIN):
        raise HTTPException(status_code=403, detail="Solo el moderador puede hacer esto")


def _validar_cobro(valor: Optional[str], nombre: str) -> None:
    """Yape/Plin, si vienen, son un celular de 9 dígitos."""
    if valor and not re.fullmatch(r"\d{9}", valor):
        raise HTTPException(status_code=400, detail=f"El número de {nombre} debe tener 9 dígitos")


# --- cuenta y perfil -------------------------------------------------------


@router.post("/registro", status_code=status.HTTP_201_CREATED)
def registro(data: RegistroIn, request: Request, db: Session = Depends(get_db)):
    """Alta de vecino. El front, después, entra con `/api/login`."""
    rate_limit(request, "/api/registro")

    if not data.acepta_privacidad:
        raise HTTPException(status_code=400, detail="Debes aceptar el aviso de privacidad")
    if data.zona not in ZONA_CENTRO:
        raise HTTPException(status_code=400, detail="Elige una zona de la lista")
    _validar_cobro(data.yape, "Yape")
    _validar_cobro(data.plin, "Plin")
    if db.query(User).filter(User.phone == data.telefono).first():
        raise HTTPException(status_code=409, detail="El número de teléfono ya está registrado")

    # El correo es opcional: la cuenta se identifica por el celular. Si no lo
    # mandan, se guarda uno interno para no romper la restricción del modelo.
    email = data.email or f"{data.telefono}@delbarrio.local"
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="El email ya está registrado")

    username = email.split("@")[0][:50]
    base, n = username, 1
    while db.query(User).filter(User.username == username).first():
        n += 1
        username = f"{base}{n}"[:50]

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(data.password),
        full_name=data.nombre.strip(),
        # El front no pide DNI: se genera un marcador único para no romper la
        # restricción del modelo del MVP (se puede hacer opcional más adelante).
        dni=f"SN{uuid.uuid4().hex[:12]}",
        phone=data.telefono,
        zona=data.zona,
        yape=data.yape or "",
        plin=data.plin or "",
        telefono_verificado=False,
        mostrar_contacto=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"ok": True, "id": str(user.id)}


@router.post("/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    """JSON {telefono, password} -> {token, usuario}. Acepta {email} por compatibilidad."""
    rate_limit(request, "/api/login")

    ahora = _ahora()
    if data.telefono:
        user = db.query(User).filter(User.phone == data.telefono).first()
    else:
        user = db.query(User).filter(User.email == data.email).first()

    # Freno a la fuerza bruta: 5 fallos -> 15 minutos bloqueado.
    if user and user.bloqueado_hasta:
        bloqueado = user.bloqueado_hasta
        if bloqueado.tzinfo is None:  # SQLite devuelve naive UTC
            bloqueado = bloqueado.replace(tzinfo=timezone.utc)
        if bloqueado > ahora:
            restante = int((bloqueado - ahora).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Demasiados intentos. Prueba de nuevo en {restante} minutos "
                "o recupera tu contraseña.",
            )

    if not user or not verify_password(data.password, user.hashed_password):
        if user:
            user.intentos_fallidos = (user.intentos_fallidos or 0) + 1
            if user.intentos_fallidos >= 5:
                user.bloqueado_hasta = ahora + timedelta(minutes=15)
            db.commit()
        raise HTTPException(status_code=401, detail="Celular o contraseña incorrectos")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Cuenta inactiva")

    if user.intentos_fallidos or user.bloqueado_hasta:
        user.intentos_fallidos = 0
        user.bloqueado_hasta = None
        db.commit()

    token = create_access_token(data={"sub": str(user.id), "username": user.username})
    return {"token": token, "usuario": perfil_dict(user, db)}


@router.post("/logout")
def logout():
    """El JWT es stateless: el front borra el token del localStorage."""
    return {"ok": True}


@router.get("/perfil")
def leer_perfil(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return perfil_dict(user, db)


@router.put("/perfil")
def editar_perfil(
    data: PerfilIn,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if data.nombre is not None:
        user.full_name = data.nombre.strip()
    if data.zona is not None:
        if data.zona not in ZONA_CENTRO:
            raise HTTPException(status_code=400, detail="Zona inválida")
        user.zona = data.zona
    if data.yape is not None:
        _validar_cobro(data.yape, "Yape")
        user.yape = data.yape
    if data.plin is not None:
        _validar_cobro(data.plin, "Plin")
        user.plin = data.plin
    if data.mostrar_contacto is not None:
        user.mostrar_contacto = data.mostrar_contacto
    if data.telefono is not None:
        if db.query(User).filter(User.phone == data.telefono, User.id != user.id).first():
            raise HTTPException(status_code=409, detail="El número de teléfono ya está registrado")
        user.phone = data.telefono

    db.commit()
    db.refresh(user)

    # El front avisa cuántas publicaciones activas se actualizaron con la zona.
    actualizadas = 0
    if data.zona is not None:
        actualizadas = (
            db.query(Publicacion)
            .filter(
                Publicacion.autor_id == user.id,
                Publicacion.deleted_at.is_(None),
                Publicacion.estado == "activa",
            )
            .update({"zona": data.zona}, synchronize_session=False)
        )
        db.commit()
    return {"ok": True, "publicaciones_actualizadas": actualizadas}


# --- catálogos y avisos ----------------------------------------------------


@router.get("/zonas")
def listar_zonas():
    """Array plano de sectores (el front lo guarda en localStorage)."""
    return ZONAS


@router.get("/salud")
def salud():
    return {"status": "ok", "servicio": settings.app_name, "version": "0.1.0"}


@router.get("/notificaciones")
def notificaciones(user: User = Depends(get_current_active_user)):
    """Avisos en pantalla. Fase 2: llegan respuestas de cotizaciones y tratos."""
    return {"items": []}


@router.post("/notificaciones/leer")
def notificaciones_leer(user: User = Depends(get_current_active_user)):
    return {"ok": True}


# --- publicaciones ---------------------------------------------------------


@router.get("/publicaciones")
def listar_publicaciones(
    request: Request,
    tipo: Optional[str] = None,
    categoria: Optional[str] = None,
    q: Optional[str] = None,
    zona: Optional[str] = None,
    solo_favores: Optional[str] = None,
    tipo_favor: Optional[str] = None,
    emergencia: Optional[str] = None,
    orden: str = "cercania",
    limit: int = 30,
    offset: int = 0,
    lat: Optional[str] = None,
    lng: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(usuario_opcional),
):
    """Lista pública. `{items: [...]}` con los filtros que arma el front."""
    query = db.query(Publicacion).filter(
        Publicacion.deleted_at.is_(None),
        Publicacion.estado == "activa",
    ).order_by(Publicacion.creado.desc())
    if tipo:
        query = query.filter(Publicacion.tipo == tipo)
    if categoria:
        query = query.filter(Publicacion.categoria == categoria)
    if zona:
        query = query.filter(Publicacion.zona == zona)
    if tipo_favor:
        query = query.filter(Publicacion.subtipo_favor == tipo_favor)
    if solo_favores in ("true", "1"):
        query = query.filter(Publicacion.tipo.like("favor%"))
    if emergencia in ("true", "1"):
        query = query.filter(Publicacion.es_emergencia.is_(True))
    elif emergencia in ("false", "0"):
        query = query.filter(Publicacion.es_emergencia.is_(False))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Publicacion.titulo.ilike(like), Publicacion.descripcion.ilike(like)))

    # Se serializa antes de ordenar porque "cercania" depende de la distancia.
    ref = _ref(lat, lng)
    filas = [(serializar(p, user, ref), _distancia(p, ref)) for p in query.all()]

    # Contenido capturado de Facebook. No aplica a favores ni a emergencias.
    if (
        solo_favores not in ("true", "1")
        and not tipo_favor
        and emergencia not in ("true", "1")
        and tipo in (None, "", "servicio")
    ):
        scraped_query = db.query(ScrapedPost).filter(
            ScrapedPost.is_active.is_(True),
            or_(ScrapedPost.ia_estado.is_(None), ScrapedPost.ia_estado == "aprobado"),
        )
        if q:
            like = f"%{q}%"
            scraped_query = scraped_query.filter(
                or_(ScrapedPost.content.ilike(like), ScrapedPost.author.ilike(like))
            )
        if zona:
            scraped_query = scraped_query.filter(ScrapedPost.city.ilike(f"%{zona}%"))
        for sp in scraped_query.order_by(ScrapedPost.captured_at.desc()).all():
            item = serializar_scraped(sp, user, ref)
            if categoria and item["categoria"] != categoria:
                continue
            filas.append((item, item["distancia_km"]))

    if orden == "vistos":
        filas.sort(key=lambda f: -(f[0]["vistos"] or 0))
    elif orden == "reciente":
        filas.sort(key=lambda f: -f[0]["creado"])
    elif any(d is not None for _, d in filas):
        filas.sort(key=lambda f: f[1] if f[1] is not None else 1e9)
    else:
        filas.sort(key=lambda f: -f[0]["creado"])

    items = [f[0] for f in filas]
    return {"items": items[offset : offset + max(1, min(limit, 100))]}


@router.get("/publicaciones/{publicacion_id}")
def leer_publicacion(
    publicacion_id: uuid.UUID,
    lat: Optional[str] = None,
    lng: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(usuario_opcional),
):
    p = db.query(Publicacion).filter(Publicacion.id == publicacion_id).first()
    if not p or p.deleted_at is not None:
        # ¿Es una publicación capturada de Facebook?
        sp = _buscar_scraped(db, publicacion_id)
        if sp:
            ref = _ref(lat, lng)
            if ref[0] is None and user:
                ref = ZONA_CENTRO.get(getattr(user, "zona", "") or "", (None, None))
            return serializar_scraped(sp, user, ref)
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if p.estado == "borrador" and (not user or user.id != p.autor_id):
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    visto = False
    if user:
        visto = (
            db.query(PublicacionVisto)
            .filter(
                PublicacionVisto.publicacion_id == p.id,
                PublicacionVisto.usuario_id == user.id,
            )
            .first()
            is not None
        )

    # Distancia: query lat/lng o, si no, el centro del sector del vecino.
    ref = _ref(lat, lng)
    if ref[0] is None and user:
        ref = ZONA_CENTRO.get(getattr(user, "zona", "") or "", (None, None))
    return serializar(p, user, ref, visto=visto)


def _validar_publicacion(data: PublicacionIn) -> dict:
    """Reglas del backend de referencia para crear una publicación."""
    if data.tipo not in TIPOS:
        raise HTTPException(status_code=400, detail="Tipo inválido: elige producto, servicio o favor")
    if (data.categoria or "").lower() not in CATEGORIAS:
        raise HTTPException(status_code=400, detail="Categoría inválida")
    if data.tipo in {"favor_solicitado", "favor_ofrecido"}:
        if not data.subtipo_favor or data.subtipo_favor not in SUBTIPOS_FAVOR:
            raise HTTPException(status_code=400, detail="Elige un tipo de favor válido")

    titulo = (data.titulo or "").strip()
    desc = (data.descripcion or "").strip()
    if len(titulo) < 3 or len(desc) < 5:
        raise HTTPException(status_code=400, detail="El título y la descripción son obligatorios")

    medios = [m.strip() for m in (data.medios_pago or "").split(",") if m.strip()]
    if any(m not in MEDIOS_PAGO for m in medios):
        raise HTTPException(status_code=400, detail="Medio de pago inválido")
    if data.politica_pago and data.politica_pago not in POLITICAS_PAGO:
        raise HTTPException(status_code=400, detail="Política de pago inválida")

    # Movilidad solidaria: nunca datos del menor ni direcciones exactas.
    if data.subtipo_favor == "movilidad":
        texto = f"{titulo} {desc} {data.punto_encuentro or ''}".lower()
        if any(p in texto for p in PROHIBIDO_MOVILIDAD):
            raise HTTPException(
                status_code=400,
                detail="En movilidad no se puede publicar el nombre del colegio, la dirección "
                "ni datos del menor. Usa solo zona, franja horaria y punto de encuentro público.",
            )
        if not (data.franja_horaria or "").strip():
            raise HTTPException(status_code=400, detail="Indica la franja horaria (por ejemplo 7:00 a 8:00)")
        if not (data.punto_encuentro or "").strip():
            raise HTTPException(status_code=400, detail="Indica un punto de encuentro público")
        if not data.checklist_ok:
            raise HTTPException(status_code=400, detail="Confirma la lista de seguridad de movilidad")

    if data.es_emergencia and data.necesidad and data.necesidad not in NECESIDADES_72H:
        raise HTTPException(status_code=400, detail="Tipo de necesidad inválido")

    return {"titulo": titulo, "descripcion": desc, "medios": ",".join(medios)}


def _ubicar(data: PublicacionIn, user: User) -> tuple[str, float, float]:
    """Sector + coordenadas: si no hay GPS se usa el centro del sector."""
    zona = (data.zona or "").strip() or (getattr(user, "zona", "") or "")
    lat, lng = data.lat, data.lng
    if lat is None or lng is None:
        if zona in ZONA_CENTRO:
            lat, lng = ZONA_CENTRO[zona]
        else:
            raise HTTPException(
                status_code=400,
                detail="Si tu zona no está en la lista, comparte tu ubicación (GPS)",
            )
    return zona, lat, lng


@router.post("/publicaciones", status_code=status.HTTP_201_CREATED)
def crear_publicacion(
    data: PublicacionIn,
    request: Request,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rate_limit(request, "/api/publicaciones")

    if data.client_id:
        existente = (
            db.query(Publicacion)
            .filter(Publicacion.client_id == data.client_id, Publicacion.autor_id == user.id)
            .first()
        )
        if existente:  # reintento de la cola offline
            return {"ok": True, "id": str(existente.id), "duplicado": True}

    limpio = _validar_publicacion(data)
    zona, lat, lng = _ubicar(data, user)
    lat_publica, lng_publica = _jitter(lat, lng)
    fotos = [f for f in data.fotos if str(f).startswith("/fotos/")][:3]

    p = Publicacion(
        autor_id=user.id,
        tipo=data.tipo,
        subtipo_favor=data.subtipo_favor,
        categoria=(data.categoria or "otros").lower(),
        titulo=limpio["titulo"],
        descripcion=limpio["descripcion"],
        precio=data.precio,
        stock=data.stock,
        medios_pago=limpio["medios"],
        politica_pago=data.politica_pago or "",
        zona=zona,
        lat=lat,
        lng=lng,
        lat_publica=lat_publica,
        lng_publica=lng_publica,
        punto_encuentro=data.punto_encuentro or "",
        franja_horaria=data.franja_horaria or "",
        checklist_ok=data.checklist_ok,
        es_emergencia=data.es_emergencia,
        necesidad=data.necesidad,
        mostrar_contacto=data.mostrar_contacto,
        wa=data.whatsapp,
        telefono_externo=_digitos(data.telefono_whatsapp),
        fotos=fotos,
        avaladores=data.avaladores,
        client_id=data.client_id,
        estado="activa",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"ok": True, "id": str(p.id)}


@router.patch("/publicaciones/{publicacion_id}")
def editar_publicacion(
    publicacion_id: uuid.UUID,
    data: PublicacionPatch,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    p = db.query(Publicacion).filter(Publicacion.id == publicacion_id).first()
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if p.autor_id != user.id and user.role not in (Roles.MOD, Roles.ADMIN):
        raise HTTPException(status_code=403, detail="Sin permisos para editar")
    if p.estado == "cerrada":
        raise HTTPException(status_code=400, detail="Esta publicación ya está cerrada")
    if data.version is not None and data.version != p.version:
        raise HTTPException(
            status_code=409,
            detail="Otro cambio se guardó antes. Recarga para ver la versión actual.",
        )

    cambios = data.model_dump(exclude_unset=True, exclude={"version"})

    if "zona" in cambios and cambios["zona"] not in ZONA_CENTRO:
        raise HTTPException(status_code=400, detail="Zona inválida")
    if "titulo" in cambios and len((cambios["titulo"] or "").strip()) < 3:
        raise HTTPException(status_code=400, detail="El título es obligatorio")
    if "descripcion" in cambios and len((cambios["descripcion"] or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="La descripción es obligatoria")
    if "categoria" in cambios and (cambios["categoria"] or "").lower() not in CATEGORIAS:
        raise HTTPException(status_code=400, detail="Categoría inválida")
    if "medios_pago" in cambios:
        medios = [m.strip() for m in (cambios["medios_pago"] or "").split(",") if m.strip()]
        if any(m not in MEDIOS_PAGO for m in medios):
            raise HTTPException(status_code=400, detail="Medio de pago inválido")
        cambios["medios_pago"] = ",".join(medios)
    if "politica_pago" in cambios and cambios["politica_pago"] not in POLITICAS_PAGO:
        raise HTTPException(status_code=400, detail="Política de pago inválida")
    if cambios.get("subtipo_favor") and cambios["subtipo_favor"] not in SUBTIPOS_FAVOR:
        raise HTTPException(status_code=400, detail="Elige un tipo de favor válido")
    if "necesidad" in cambios and cambios["necesidad"] and cambios["necesidad"] not in NECESIDADES_72H:
        raise HTTPException(status_code=400, detail="Tipo de necesidad inválido")
    if "fotos" in cambios:
        cambios["fotos"] = [f for f in (cambios["fotos"] or []) if str(f).startswith("/fotos/")][:3]

    # Campos que no se llaman igual en el modelo
    whatsapp = cambios.pop("whatsapp", None)
    telefono_wa = cambios.pop("telefono_whatsapp", None)
    if whatsapp is not None:
        p.wa = bool(whatsapp)
    if telefono_wa is not None:
        p.telefono_externo = _digitos(telefono_wa)

    for campo, valor in cambios.items():
        setattr(p, campo, valor)
    if cambios or whatsapp is not None or telefono_wa is not None:
        p.version = (p.version or 1) + 1
        p.actualizado = _ahora()
    db.commit()
    return {"ok": True}


@router.delete("/publicaciones/{publicacion_id}")
def borrar_publicacion(
    publicacion_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    p = db.query(Publicacion).filter(Publicacion.id == publicacion_id).first()
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if p.autor_id != user.id and user.role not in (Roles.MOD, Roles.ADMIN):
        raise HTTPException(status_code=403, detail="Sin permisos para eliminar")

    p.deleted_at = _ahora()
    p.estado = "cerrada"
    db.commit()
    return {"ok": True}


@router.get("/mis-publicaciones")
def mis_publicaciones(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Array plano (no `{items}`) con conteos de vistos y cotizaciones."""
    filas = (
        db.query(Publicacion)
        .filter(Publicacion.autor_id == user.id, Publicacion.deleted_at.is_(None))
        .order_by(Publicacion.creado.desc())
        .all()
    )
    items = []
    for p in filas:
        item = serializar(p, user, None)
        item["cotizaciones"] = 0  # fase 2
        items.append(item)
    return items


# --- fotos -----------------------------------------------------------------


@router.post("/fotos")
def subir_foto(
    data: dict,
    user: User = Depends(get_current_active_user),
):
    """Recibe un data URL JPEG/PNG (≤4 MB) y devuelve `/fotos/<hex>.jpg`."""
    crudo = str(data.get("data") or "")
    if not crudo.startswith("data:image/") or "," not in crudo:
        raise HTTPException(status_code=400, detail="formato")
    cabecera, b64 = crudo.split(",", 1)
    try:
        binario = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="formato")
    if len(binario) > 4 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="La imagen supera 4 MB")

    ext = "png" if "png" in cabecera else "jpg"
    nombre = f"{uuid.uuid4().hex}.{ext}"
    from pathlib import Path

    destino = Path(settings.fotos_dir)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / nombre).write_bytes(binario)
    return {"ok": True, "url": f"/fotos/{nombre}"}


# --- acciones del detalle --------------------------------------------------


@router.post("/vistos")
def recomendar(
    data: VistoIn,
    request: Request,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rate_limit(request, "/api/vistos")

    p = db.query(Publicacion).filter(Publicacion.id == data.publicacion_id).first()
    if not p or p.deleted_at is not None:
        if _buscar_scraped(db, data.publicacion_id):
            raise HTTPException(
                status_code=400,
                detail="Esta publicación viene de Facebook: ábrela allí para recomendar.",
            )
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if p.autor_id == user.id:
        raise HTTPException(status_code=400, detail="No puedes recomendar tu propia publicación")
    if p.estado not in {"activa", "resuelta"}:
        raise HTTPException(
            status_code=400, detail="Solo se puede recomendar publicaciones activas o cerradas"
        )

    ya = (
        db.query(PublicacionVisto)
        .filter(
            PublicacionVisto.publicacion_id == p.id,
            PublicacionVisto.usuario_id == user.id,
        )
        .first()
    )
    if ya:
        return {"ok": True, "vistos": p.vistos, "ya_recomende": True}

    # Freno al «visto bueno en manada»: máximo 5 al día por persona.
    desde = _unix(_ahora() - timedelta(days=1))
    hoy = sum(
        1
        for v in db.query(PublicacionVisto)
        .filter(PublicacionVisto.usuario_id == user.id)
        .all()
        if v.creado and _unix(v.creado) > desde
    )
    if hoy >= 5:
        raise HTTPException(
            status_code=429, detail="Diste 5 vistos buenos hoy. Mañana podrás dar más."
        )

    db.add(
        PublicacionVisto(
            publicacion_id=p.id, usuario_id=user.id, comentario=data.comentario or ""
        )
    )
    p.vistos = (p.vistos or 0) + 1
    db.commit()
    return {"ok": True, "vistos": p.vistos, "ya_recomende": True}


@router.delete("/vistos")
def quitar_visto(
    publicacion_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Quita el visto bueno del vecino (para el toggle del botón Recomendar)."""
    p = db.query(Publicacion).filter(Publicacion.id == publicacion_id).first()
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")

    fila = (
        db.query(PublicacionVisto)
        .filter(
            PublicacionVisto.publicacion_id == p.id,
            PublicacionVisto.usuario_id == user.id,
        )
        .first()
    )
    if fila:
        db.delete(fila)
        p.vistos = max(0, (p.vistos or 1) - 1)
        db.commit()
    return {"ok": True, "vistos": p.vistos or 0, "ya_recomende": False}


@router.post("/reportes")
def reportar(
    data: ReporteIn,
    request: Request,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rate_limit(request, "/api/reportes")

    p = db.query(Publicacion).filter(Publicacion.id == data.publicacion_id).first()
    if not p or p.deleted_at is not None:
        if _buscar_scraped(db, data.publicacion_id):
            raise HTTPException(
                status_code=400,
                detail="Esta publicación viene de Facebook: repórtala allí.",
            )
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if p.autor_id == user.id:
        raise HTTPException(status_code=400, detail="No puedes reportar tu propia publicación")
    if (
        db.query(Reporte)
        .filter(Reporte.publicacion_id == p.id, Reporte.usuario_id == user.id)
        .first()
    ):
        return {"ok": True, "mensaje": "Ya habías reportado esta publicación."}

    db.add(Reporte(publicacion_id=p.id, usuario_id=user.id, motivo=data.motivo[:300]))
    db.commit()
    return {"ok": True, "mensaje": "Reporte enviado. Un moderador lo revisará."}


@router.get("/mis-accesos")
def mis_accesos(user: User = Depends(get_current_active_user)):
    """Quién abrió tu ficha de contacto. Fase 2 (tabla `accesos_contacto`)."""
    return {"total": 0, "items": []}


# --- tablero de emergencia -------------------------------------------------


def _ajuste(db: Session, clave: str, por_defecto: str = "") -> str:
    fila = db.query(Ajuste).filter(Ajuste.clave == clave).first()
    return fila.valor if fila else por_defecto


def _guardar_ajuste(db: Session, clave: str, valor: str) -> None:
    fila = db.query(Ajuste).filter(Ajuste.clave == clave).first()
    if fila:
        fila.valor = valor
        fila.actualizado = _ahora()
    else:
        db.add(Ajuste(clave=clave, valor=valor, actualizado=_ahora()))
    db.commit()


@router.get("/emergencia")
def estado_emergencia(db: Session = Depends(get_db)):
    return {
        "activo": _ajuste(db, "emergencia_activo", "0") == "1",
        "motivo": _ajuste(db, "emergencia_motivo", ""),
    }


@router.get("/emergencia/directorio")
def directorio_emergencia():
    return {"items": DIRECTORIO}


@router.post("/emergencia/activar")
def activar_emergencia(
    data: EmergenciaIn,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _exige_moderador(user)
    _guardar_ajuste(db, "emergencia_activo", "1" if data.activo else "0")
    _guardar_ajuste(db, "emergencia_motivo", data.motivo or "")
    return {"ok": True, "activo": data.activo}


# --- revisión de publicaciones de Facebook con IA ---------------------------


@router.get("/ia/config")
def ia_config(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Si hay API key configurada (nunca se devuelve la clave) y el avance."""
    api_key, modelo = ia_service.obtener_config(db)
    return {
        "configurada": bool(api_key),
        "modelo": modelo,
        "estado": ia_service.estado(db),
        "auto": scheduler.estado(db),
    }


@router.put("/ia/config")
def ia_configurar(
    data: IaConfigIn,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ia_service.configurar(db, data.api_key, data.modelo)
    api_key, modelo = ia_service.obtener_config(db)
    return {"ok": True, "configurada": bool(api_key), "modelo": modelo}


@router.post("/ia/revisar")
def ia_revisar(
    data: IaRevisarIn,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Revisa un lote de posts sin revisar (texto + imagen) y los clasifica."""
    try:
        resumen = ia_service.revisar_pendientes(db, data.limite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ia_service.IaError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"ok": True, **resumen, "estado": ia_service.estado(db)}


@router.post("/ia/scrape")
def ia_scrape(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Ejecuta el scraper de Facebook ahora (sin esperar al planificador).

    Requiere sesión de Facebook y Chromium instalado (build con Playwright).
    """
    from app.api.schemas.scraped_post import ScrapingRunRequest
    from app.services import scraping_service

    try:
        resultado = scraping_service.run(db, ScrapingRunRequest())
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Scraper: {exc}")

    scheduler.marcar_scrape(db)
    return {"ok": True, **resultado, "auto": scheduler.estado(db)}
