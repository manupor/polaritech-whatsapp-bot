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

        # Require at least 40% of keywords to match and a minimum of 2 hits
        # (or 1 hit if the question only has 1-2 meaningful words)
        min_hits = min(2, len(question_words))
        if hits >= min_hits and score > best_score:
            best_score = score
            best_entry = entry

    # Only return if we have a reasonable match (≥40% overlap)
    if best_entry and best_score >= 0.4:
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
    Main entry point: search FAQ JSON → products → MD fallback.
    Returns None only when no source has a match.
    """
    kb = get_kb()

    # 1. FAQ JSON direct match
    faq_answer = _faq_match(query, kb.faq)
    if faq_answer:
        return faq_answer

    # 2. Product match
    product_answer = _product_match(query, kb)
    if product_answer:
        return product_answer

    # 3. MD fallback
    md_answer = _md_fallback(query)
    if md_answer:
        return md_answer

    return None
