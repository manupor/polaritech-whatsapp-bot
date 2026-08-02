from __future__ import annotations

"""
Loads the Polaritech knowledge base from local data files.

Primary source : polaritech_faq.json   (structured FAQ + company + products …)
Fallback source: polaritech_base_conocimiento.md  (free-text context)

The JSON is parsed into a KnowledgeBase model.  The markdown is parsed into
KBArticle objects (section-based) used as fallback context when the FAQ has
no direct match.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from src.kb.models import (
    PENDING,
    CompanyInfo,
    FAQEntry,
    KBArticle,
    KnowledgeBase,
    Policies,
    Product,
    ProductTechData,
    SpecialCase,
)

logger = logging.getLogger(__name__)

KB_DATA_DIR = Path(__file__).resolve().parent / "data"
FAQ_JSON = KB_DATA_DIR / "polaritech_faq.json"
BASE_MD = KB_DATA_DIR / "polaritech_base_conocimiento.md"


# ── JSON loader ──────────────────────────────────────────────────────────────

def _parse_product(raw: dict) -> Product:
    datos_raw = raw.get("datos", {})
    datos = ProductTechData(
        vlt=datos_raw.get("VLT", PENDING),
        uv=datos_raw.get("UV", PENDING),
        irr=datos_raw.get("IRR", PENDING),
        tser=datos_raw.get("TSER", PENDING),
        espesor=datos_raw.get("Espesor", PENDING),
        garantia=datos_raw.get("Garantía", datos_raw.get("Garantia", PENDING)),
        especificaciones=datos_raw.get("Especificaciones", PENDING),
    )
    return Product(
        nombre=raw.get("nombre", ""),
        descripcion=raw.get("descripcion", ""),
        beneficios=raw.get("beneficios", []),
        vlt_presentacion=raw.get("vlt", PENDING),
        datos=datos,
        recomendada=raw.get("recomendada", ""),
    )


def _parse_policies(raw: dict) -> Policies:
    return Policies(
        garantia=raw.get("Garantía", raw.get("Garantia", [])),
        limpieza_mantenimiento=raw.get("Limpieza y mantenimiento", []),
        cotizacion=raw.get("Cotización", raw.get("Cotizacion", [])),
        reserva_pagos=raw.get("Reserva y pagos", []),
        devoluciones_cancelaciones=raw.get("Devoluciones y cancelaciones", []),
    )


def _parse_company(raw: dict) -> CompanyInfo:
    return CompanyInfo(
        nombre_comercial=raw.get("Nombre comercial", ""),
        actividad=raw.get("Actividad", ""),
        historia=raw.get("Historia", ""),
        mision=raw.get("Misión", raw.get("Mision", "")),
        vision=raw.get("Visión", raw.get("Vision", "")),
        valores=raw.get("Valores", ""),
        ubicacion=raw.get("Ubicación", raw.get("Ubicacion", "")),
        sitio_web=raw.get("Sitio web", ""),
        cobertura=raw.get("Cobertura", ""),
        horario=raw.get("Horario", PENDING),
        telefono_whatsapp=raw.get("Teléfono / WhatsApp", PENDING),
        correo=raw.get("Correo", PENDING),
        redes_sociales=raw.get("Redes sociales", PENDING),
    )


def _collect_pending(kb: KnowledgeBase) -> List[str]:
    """Walk the KB and collect fields whose value is 'Información pendiente de confirmar'."""
    pending: List[str] = []

    # Company
    for field_name, value in kb.company.model_dump().items():
        if isinstance(value, str) and PENDING.lower() in value.lower():
            pending.append(f"company.{field_name}")

    # Products
    for prod in kb.products:
        for field_name, value in prod.datos.model_dump().items():
            if isinstance(value, str) and PENDING.lower() in value.lower():
                pending.append(f"products.{prod.nombre}.datos.{field_name}")
        if isinstance(prod.vlt_presentacion, str) and PENDING.lower() in prod.vlt_presentacion.lower():
            pending.append(f"products.{prod.nombre}.vlt_presentacion")

    # Pricing rules
    for i, rule in enumerate(kb.pricing_rules):
        if PENDING.lower() in rule.lower():
            pending.append(f"pricing_rules[{i}]")

    # Technical visits
    for i, rule in enumerate(kb.technical_visits):
        if PENDING.lower() in rule.lower():
            pending.append(f"technical_visits[{i}]")

    # Policies
    for field_name, items in kb.policies.model_dump().items():
        if isinstance(items, list):
            for i, item in enumerate(items):
                if isinstance(item, str) and PENDING.lower() in item.lower():
                    pending.append(f"policies.{field_name}[{i}]")

    return pending


def load_faq_json() -> KnowledgeBase:
    if not FAQ_JSON.exists():
        logger.warning("FAQ JSON not found at %s", FAQ_JSON)
        return KnowledgeBase()

    raw = json.loads(FAQ_JSON.read_text(encoding="utf-8"))

    kb = KnowledgeBase(
        integrity_rule=raw.get("integrity_rule", ""),
        company=_parse_company(raw.get("company", {})),
        products=[_parse_product(p) for p in raw.get("products", [])],
        pricing_rules=raw.get("pricing_rules", []),
        installation_rules=raw.get("installation_rules", []),
        technical_visits=raw.get("technical_visits", []),
        faq=[FAQEntry(**f) for f in raw.get("faq", [])],
        policies=_parse_policies(raw.get("policies", {})),
        special_cases=[SpecialCase(**s) for s in raw.get("special_cases", [])],
        chatbot_rules=raw.get("bot_rules", []),
    )

    kb.pending_information = _collect_pending(kb)

    logger.info(
        "FAQ JSON loaded: %d products, %d FAQs, %d pending fields",
        len(kb.products), len(kb.faq), len(kb.pending_information),
    )
    return kb


# ── Markdown fallback loader ────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


# Headings that contain internal instructions (not user-facing answers)
_INTERNAL_HEADINGS = frozenset({
    "reglas del chatbot",
    "base de conocimiento para chatbot",
})

# Body content that starts with an instruction pattern (not a user-facing answer)
_INSTRUCTION_PREFIXES = (
    "no inventar",
    "escalar",
    "responder con respeto",
    "explicar que",
    "revisar si existe",
    "aclarar que",
    "indicar que",
)


def _is_internal_section(heading: str, body: str) -> bool:
    """Return True if a section contains bot instructions, not user-facing content."""
    h_lower = heading.lower()
    if any(internal in h_lower for internal in _INTERNAL_HEADINGS):
        return True
    # Numbered section headers like "9. Reglas del chatbot"
    if "reglas" in h_lower and "chatbot" in h_lower:
        return True
    # Body that starts with an instruction verb
    b_lower = body.lower().strip()
    if any(b_lower.startswith(prefix) for prefix in _INSTRUCTION_PREFIXES):
        return True
    # Lists of rules (body is only bullet points starting with "- ")
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    if lines and all(l.startswith("- ") for l in lines):
        return True
    return False


def load_md_articles() -> List[KBArticle]:
    """Parse the markdown file into section-based KBArticle objects."""
    articles: List[KBArticle] = []

    if not BASE_MD.exists():
        logger.warning("Base MD not found at %s", BASE_MD)
        return articles

    text = BASE_MD.read_text(encoding="utf-8")
    sections = _HEADING_RE.split(text)

    # sections alternates: [preamble, heading1, body1, heading2, body2, …]
    i = 1
    while i < len(sections) - 1:
        heading = sections[i].strip()
        body = sections[i + 1].strip()
        if body and not _is_internal_section(heading, body):
            keywords = [w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{4,}", heading)]
            articles.append(KBArticle(topic=heading, content=body, keywords=keywords))
        i += 2

    logger.info("MD fallback loaded: %d sections", len(articles))
    return articles


# ── Module-level caches ─────────────────────────────────────────────────────

_kb: Optional[KnowledgeBase] = None
_md_articles: Optional[List[KBArticle]] = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = load_faq_json()
    return _kb


def get_md_articles() -> List[KBArticle]:
    global _md_articles
    if _md_articles is None:
        _md_articles = load_md_articles()
    return _md_articles


def get_articles() -> List[KBArticle]:
    """Backward-compat: return MD fallback articles."""
    return get_md_articles()


def reload() -> KnowledgeBase:
    """Force-reload all data from disk."""
    global _kb, _md_articles
    _kb = load_faq_json()
    _md_articles = load_md_articles()
    return _kb
