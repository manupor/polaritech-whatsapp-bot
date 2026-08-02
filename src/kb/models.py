from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


PENDING = "Información pendiente de confirmar"


def is_pending(value: Any) -> bool:
    """Return True if a value is marked as unconfirmed in the source docs."""
    if isinstance(value, str):
        return PENDING.lower() in value.lower()
    return False


# ── Company ──────────────────────────────────────────────────────────────────

class CompanyInfo(BaseModel):
    nombre_comercial: str = ""
    actividad: str = ""
    historia: str = ""
    mision: str = ""
    vision: str = ""
    valores: str = ""
    ubicacion: str = ""
    sitio_web: str = ""
    cobertura: str = ""
    horario: str = PENDING
    telefono_whatsapp: str = PENDING
    correo: str = PENDING
    redes_sociales: str = PENDING


# ── Products ─────────────────────────────────────────────────────────────────

class ProductTechData(BaseModel):
    vlt: str = PENDING
    uv: str = PENDING
    irr: str = PENDING
    tser: str = PENDING
    espesor: str = PENDING
    garantia: str = PENDING
    shgc: str = PENDING
    especificaciones: str = PENDING


class Product(BaseModel):
    nombre: str
    descripcion: str = ""
    beneficios: List[str] = []
    vlt_presentacion: str = PENDING
    datos: ProductTechData = ProductTechData()
    recomendada: str = ""

    def has_pending_specs(self) -> bool:
        return any(is_pending(v) for v in self.datos.model_dump().values())


# ── FAQ ──────────────────────────────────────────────────────────────────────

class FAQEntry(BaseModel):
    id: int
    question: str
    answer: str


# ── Policies ─────────────────────────────────────────────────────────────────

class Policies(BaseModel):
    garantia: List[str] = []
    limpieza_mantenimiento: List[str] = []
    cotizacion: List[str] = []
    reserva_pagos: List[str] = []
    devoluciones_cancelaciones: List[str] = []


# ── Special cases ────────────────────────────────────────────────────────────

class SpecialCase(BaseModel):
    case: str
    response: str


# ── Top-level knowledge base ────────────────────────────────────────────────

class KnowledgeBase(BaseModel):
    integrity_rule: str = ""
    company: CompanyInfo = CompanyInfo()
    products: List[Product] = []
    pricing_rules: List[str] = []
    installation_rules: List[str] = []
    technical_visits: List[str] = []
    faq: List[FAQEntry] = []
    policies: Policies = Policies()
    special_cases: List[SpecialCase] = []
    chatbot_rules: List[str] = []
    pending_information: List[str] = []

    def get_product_by_name(self, name: str) -> Optional[Product]:
        name_lower = name.lower()
        for p in self.products:
            if name_lower in p.nombre.lower():
                return p
        return None


# ── Backward-compat wrapper used by faq_service ────────────────────────────

class KBArticle(BaseModel):
    """Lightweight wrapper kept for fallback markdown search."""
    topic: str
    content: str
    keywords: List[str]

    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.keywords)
