"""Catálogos compartidos por el contrato del front y la revisión con IA."""

TIPOS = {"servicio", "producto", "favor_solicitado", "favor_ofrecido"}

SUBTIPOS_FAVOR = {
    "prestamo",
    "ayuda_temporal",
    "donacion",
    "intercambio_habilidades",
    "movilidad",
}

CATEGORIAS = {
    "gasfitería",
    "carpintería",
    "electricidad",
    "cerrajería",
    "clases",
    "alimentos",
    "paseo de mascotas",
    "herramientas",
    "movilidad",
    "préstamo",
    "otros",
}

MEDIOS_PAGO = {"yape", "plin", "efectivo", "transferencia", "intercambio"}

POLITICAS_PAGO = {"contra_entrega", "mitad_mitad", "al_terminar"}

NECESIDADES_72H = {
    "agua_potable",
    "alimentos",
    "abrigo",
    "techo",
    "higiene",
    "salud",
    "balde_bidon",
    "herramientas",
    "movilidad",
    "alojamiento",
    "energia",
    "otro",
}

ESTADOS_PUB = {"borrador", "activa", "pausada", "resuelta", "cerrada", "vencida"}
