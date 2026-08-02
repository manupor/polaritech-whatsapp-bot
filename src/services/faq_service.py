from __future__ import annotations

"""
Searches the Polaritech knowledge base for an answer.

Priority:
  1. FAQ JSON — exact question/keyword match against the 50 FAQ entries
  2. Product data — if the query mentions a product name
  3. MD fallback — section-based keyword match against the base conocimiento
"""

import unicodedata
from typing import List, Optional

from src.core.constants import NEED_TO_PRODUCT, PENDING_PHRASE
from src.kb.loader import get_kb, get_md_articles
from src.kb.models import FAQEntry, KBArticle, KnowledgeBase, is_pending


# Fields that require explicit "pending confirmation" response
PENDING_CONFIRMATION_FIELDS = [
    "horario",
    "telefono",
    "whatsapp",
    "correo",
    "email",
    "redes sociales",
    "red social",
    "instagram",
    "facebook",
    "financiamiento",
    "credito",
    "cuotas",
    "costo de visita",
    "precio de visita",
    "visita tecnica",
    "costo visita tecnica",  # Add combined form
    "devolucion",
    "cancelacion",
    "reembolso",
    "exclusion de garantia",
    "exclusiones garantia",
    "ficha tecnica seguridad",
    "ficha tecnica sand blasting",
    "ficha tecnica white out",
    "ficha tecnica black out",
    "garantia silver espejo",
    "garantia silver grey",
]

# Hardcoded intent buckets for frequent questions with canonical answers
CANONICAL_INTENTS = {
    "calor": 2,  # FAQ id 2: "¿Cuál recomiendan si hace mucho calor?"
    "hace mucho calor": 2,  # More specific for FAQ id 2
    "privacidad diurna": 4,  # FAQ id 4: "¿Cuál recomiendan para privacidad?"
    "privacidad 24/7": 5,  # FAQ id 5: "¿La privacidad funciona de día y de noche?"
    "dia y noche": 5,  # Alternative for FAQ id 5
    "nano ceramica transparente": 3,  # FAQ id 3: "¿La Nano Cerámica transparente reduce menos calor?"
    "efecto espejo": 9,  # FAQ id 9
    "precio por metro cuadrado": 20,  # FAQ id 20
    "no tengo medidas": 19,  # FAQ id 19
    "minimo de instalacion": 21,  # FAQ id 21
    "instalacion por dentro o por fuera": 32,  # FAQ id 32
    "limpieza": 26,  # FAQ id 26
    "garantia general": 37,  # FAQ id 37
    "formas de pago": 39,  # FAQ id 39
    "trabajan con 3m": 46,  # FAQ id 46
    "afecta wifi": 31,  # FAQ id 31
    "afecta celular": 31,  # FAQ id 31
    "policarbonato": 36,  # FAQ id 36
    "vidrio laminado": 35,  # FAQ id 35
    "vidrio temperado": 35,  # FAQ id 35
}


def _check_pending_confirmation(query: str) -> Optional[str]:
    """Check if query asks for a field that requires pending confirmation response.
    Prioritizes longer, more specific fields over shorter ones."""
    q_norm = _normalize(query)
    
    # Sort by field length (descending) to match more specific fields first
    sorted_fields = sorted(PENDING_CONFIRMATION_FIELDS, key=len, reverse=True)
    
    for field in sorted_fields:
        if field in q_norm:
            return f"{PENDING_PHRASE}. Un asesor puede ayudarle con ese dato."
    return None


def _check_canonical_intent(query: str, faq_entries: List[FAQEntry]) -> Optional[str]:
    """Check if query matches a canonical intent bucket and return canonical answer.
    Prioritizes longer, more specific keys over shorter ones."""
    q_norm = _normalize(query)
    
    # Sort by key length (descending) to match more specific intents first
    sorted_intents = sorted(CANONICAL_INTENTS.items(), key=lambda x: len(x[0]), reverse=True)
    
    for intent_key, faq_id in sorted_intents:
        if intent_key in q_norm:
            # Find the FAQ entry by ID
            for entry in faq_entries:
                if entry.id == faq_id:
                    return entry.answer
    return None


def _check_silver_espejo_warranty(query: str) -> Optional[str]:
    """Protect against definitive Silver Espejo warranty answers."""
    q_norm = _normalize(query)
    if "silver espejo" in q_norm and "garantia" in q_norm:
        return "La garantía de Silver Espejo debe confirmarse la versión vigente. Un asesor puede verificar este dato."
    return None


def _normalize(text: str) -> str:
    """Lowercase, strip accents, and remove punctuation for fuzzy comparison."""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    # Keep only non-combining, non-punctuation characters (letters, digits, spaces)
    return "".join(
        c for c in nfkd
        if not unicodedata.combining(c)
        and (c.isalnum() or c.isspace())
    )


_STOP_WORDS = frozenset({
    "como", "cual", "cuando", "donde", "esta", "este", "esto",
    "hace", "para", "pero", "puede", "quien", "sera", "sido",
    "sobre", "solo", "tiene", "todo", "tipo", "tipos", "mucho",
    "cual", "cuanto", "porque",
})


def _faq_match(query: str, faq_entries: List[FAQEntry]) -> Optional[str]:
    """Return the answer from the first FAQ whose question overlaps the query."""
    q_norm = _normalize(query)

    best_entry = None
    best_score = 0.0

    for entry in faq_entries:
        question_words = [
            w for w in _normalize(entry.question).split()
            if len(w) >= 5 and w not in _STOP_WORDS
        ]
        if not question_words:
            continue

        hits = sum(1 for w in question_words if w in q_norm)
        if hits == 0:
            continue

        # Score = proportion of question keywords found in query
        score = hits / len(question_words)

        # Require at least 50% of keywords to match and a minimum of 2 hits
        # (or 1 hit if the question only has 1-2 meaningful words)
        min_hits = min(2, len(question_words))
        if hits >= min_hits and score > best_score:
            best_score = score
            best_entry = entry

    # Only return if we have a reasonable match (≥50% overlap for high confidence)
    if best_entry and best_score >= 0.5:
        return best_entry.answer

    return None


def _product_match(query: str, kb: KnowledgeBase) -> Optional[str]:
    """Try to match by product name and return a formatted summary."""
    q_norm = _normalize(query)

    # Direct product name search
    for product in kb.products:
        for name_part in product.nombre.split("/"):
            if _normalize(name_part.strip()) in q_norm:
                return _format_product(product)

    # Need-to-product mapping
    for need, product_name in NEED_TO_PRODUCT.items():
        if _normalize(need) in q_norm:
            product = kb.get_product_by_name(product_name)
            if product:
                return _format_product(product)

    return None


def _format_product(product) -> str:
    """Format a Product model into a WhatsApp-friendly text block."""
    lines = [f"*{product.nombre}*", product.descripcion, ""]

    if product.beneficios:
        for b in product.beneficios:
            lines.append(f"• {b}")
        lines.append("")

    datos = product.datos
    specs = []
    if not is_pending(datos.vlt):
        specs.append(f"VLT: {datos.vlt}")
    if not is_pending(datos.uv):
        specs.append(f"UV: {datos.uv}")
    if not is_pending(datos.irr):
        specs.append(f"IRR: {datos.irr}")
    if not is_pending(datos.tser):
        specs.append(f"TSER: {datos.tser}")
    if not is_pending(datos.espesor):
        specs.append(f"Espesor: {datos.espesor}")
    if not is_pending(datos.garantia):
        specs.append(f"Garantía: {datos.garantia}")
    else:
        specs.append(f"Garantía: {PENDING_PHRASE}")

    if specs:
        lines.append("📊 Datos técnicos:")
        for s in specs:
            lines.append(f"  {s}")
        lines.append("")

    if product.recomendada:
        lines.append(f"✅ Recomendada para: {product.recomendada}")

    return "\n".join(lines)


def _md_fallback(query: str) -> Optional[str]:
    """Search the markdown KB articles as a last resort."""
    articles: List[KBArticle] = get_md_articles()
    for article in articles:
        if article.matches(query):
            return article.content
    return None


def find_answer(query: str) -> str | None:
    """
    Main entry point with new resolution order:
    1. Pending confirmation fields (horario, telefono, etc.)
    2. Silver Espejo warranty protection
    3. Canonical intent buckets (calor, privacidad, etc.)
    4. Exact FAQ match (high confidence ≥50%)
    5. Product match
    6. MD fallback
    Returns None only when no source has a match.
    """
    kb = get_kb()
    
    # 1. Check for pending confirmation fields first (highest priority)
    pending_answer = _check_pending_confirmation(query)
    if pending_answer:
        return pending_answer
    
    # 2. Protect against definitive Silver Espejo warranty answers
    silver_answer = _check_silver_espejo_warranty(query)
    if silver_answer:
        return silver_answer
    
    # 3. Check canonical intent buckets for frequent questions
    canonical_answer = _check_canonical_intent(query, kb.faq)
    if canonical_answer:
        return canonical_answer

    # 4. FAQ JSON high-confidence match (≥50% overlap)
    faq_answer = _faq_match(query, kb.faq)
    if faq_answer:
        return faq_answer

    # 5. Product match
    product_answer = _product_match(query, kb)
    if product_answer:
        return product_answer

    # 6. MD fallback
    md_answer = _md_fallback(query)
    if md_answer:
        return md_answer

    return None
