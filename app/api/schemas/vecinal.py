from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# --- Cuenta / perfil -------------------------------------------------------


class RegistroIn(BaseModel):
    """POST /api/registro — alta con celular y contraseña numérica.

    El correo es opcional: la cuenta se identifica por el celular.
    """

    nombre: str = Field(..., min_length=3, max_length=150)
    telefono: str = Field(..., pattern=r"^\d{9}$")
    password: str = Field(..., pattern=r"^\d{6,}$")
    zona: str = Field(default="Piura Centro", max_length=80)
    yape: str = Field(default="", max_length=40)
    plin: str = Field(default="", max_length=40)
    acepta_privacidad: bool = False
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def minusculas(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Email inválido")
        return v


class LoginIn(BaseModel):
    """POST /api/login — con celular (lo normal) o correo (compatibilidad)."""

    password: str
    telefono: Optional[str] = Field(default=None, pattern=r"^\d{9}$")
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def minusculas(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else None

    @model_validator(mode="after")
    def identificador(self):
        if not self.telefono and not self.email:
            raise ValueError("Envía tu celular o tu correo")
        return self


class PerfilIn(BaseModel):
    """PUT /api/perfil — el front manda solo los campos del formulario."""

    nombre: Optional[str] = Field(default=None, min_length=3, max_length=150)
    telefono: Optional[str] = Field(default=None, pattern=r"^\d{9}$")
    zona: Optional[str] = Field(default=None, max_length=80)
    yape: Optional[str] = Field(default=None, max_length=40)
    plin: Optional[str] = Field(default=None, max_length=40)
    mostrar_contacto: Optional[bool] = None


# --- Publicaciones ---------------------------------------------------------


class PublicacionIn(BaseModel):
    """POST /api/publicaciones — campos del formulario unificado del front."""

    tipo: str = Field(..., pattern=r"^(servicio|producto|favor_solicitado|favor_ofrecido)$")
    categoria: str = Field(default="otros", max_length=60)
    subtipo_favor: Optional[str] = Field(default=None, max_length=40)
    titulo: str = Field(..., min_length=3, max_length=200)
    descripcion: str = Field(default="", max_length=2000)
    precio: Optional[str] = Field(default=None, max_length=60)
    stock: Optional[int] = Field(default=None, ge=0)
    medios_pago: str = Field(default="", max_length=160)
    politica_pago: str = Field(default="", max_length=60)
    zona: str = Field(default="", max_length=80)
    lat: Optional[float] = None
    lng: Optional[float] = None
    punto_encuentro: str = Field(default="", max_length=160)
    franja_horaria: str = Field(default="", max_length=80)
    checklist_ok: bool = False
    es_emergencia: bool = False
    necesidad: Optional[str] = Field(default=None, max_length=40)
    mostrar_contacto: bool = True
    whatsapp: bool = True
    telefono_whatsapp: str = Field(default="", max_length=20)
    fotos: list[str] = Field(default_factory=list)
    avaladores: list[dict[str, Any]] = Field(default_factory=list)
    client_id: Optional[str] = Field(default=None, max_length=64)


class PublicacionPatch(BaseModel):
    """PATCH /api/publicaciones/{id} — edición o cambio de estado."""

    titulo: Optional[str] = Field(default=None, max_length=200)
    descripcion: Optional[str] = Field(default=None, max_length=2000)
    precio: Optional[str] = Field(default=None, max_length=60)
    categoria: Optional[str] = Field(default=None, max_length=60)
    zona: Optional[str] = Field(default=None, max_length=80)
    stock: Optional[int] = Field(default=None, ge=0)
    medios_pago: Optional[str] = Field(default=None, max_length=160)
    politica_pago: Optional[str] = Field(default=None, max_length=60)
    subtipo_favor: Optional[str] = Field(default=None, max_length=40)
    franja_horaria: Optional[str] = Field(default=None, max_length=80)
    punto_encuentro: Optional[str] = Field(default=None, max_length=160)
    checklist_ok: Optional[bool] = None
    necesidad: Optional[str] = Field(default=None, max_length=40)
    fotos: Optional[list[str]] = None
    whatsapp: Optional[bool] = None
    telefono_whatsapp: Optional[str] = Field(default=None, max_length=20)
    mostrar_contacto: Optional[bool] = None
    estado: Optional[str] = Field(
        default=None, pattern=r"^(borrador|activa|pausada|resuelta|cerrada|vencida)$"
    )
    version: Optional[int] = Field(default=None, ge=1)


# --- Acciones del detalle --------------------------------------------------


class ReporteIn(BaseModel):
    publicacion_id: UUID
    motivo: str = Field(..., max_length=300)


class VistoIn(BaseModel):
    publicacion_id: UUID
    comentario: str = Field(default="", max_length=200)


class EmergenciaIn(BaseModel):
    activo: bool
    motivo: str = Field(default="", max_length=200)


class IaConfigIn(BaseModel):
    """API key de OpenRouter y modelo de visión."""

    api_key: Optional[str] = Field(default=None, max_length=300)
    modelo: Optional[str] = Field(default=None, max_length=120)


class IaRevisarIn(BaseModel):
    limite: int = Field(default=5, ge=1, le=15)
