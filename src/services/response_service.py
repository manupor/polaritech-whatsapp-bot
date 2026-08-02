"""
Orchestrates intent classification, KB lookup, escalation checks,
flow-based field collection, and returns a final BotResponse.

Handlers:
  1. FAQ            – direct KB answer
  2. Product info   – recommendation by need or name
  3. Quote request  – progressive field collection → handoff
  4. Technical visit – collect info → escalate
  5. Warranty/claim – collect evidence → escalate (high priority)
  6. Competitor     – respectful, neutral comparison
  7. Discount       – no promises, offer budget review
  8. Pending query  – exact pending phrase + escalation note
"""

import logging
import re
from typing import List, Optional

from src.core.constants import (
    FIELD_LABELS,
    Intent,
    PENDING_PHRASE,
    TEMPLATES,
)
from src.schemas.chatbot import BotResponse, EscalationPayload, IncomingMessage
from src.services.escalation_service import build_escalation_payload, should_escalate
from src.services.faq_service import find_answer
from src.services.intent_service import classify_intent
from src.state.conversation_store import FlowState, conversation_store

logger = logging.getLogger(__name__)


# ── Field extraction helpers ─────────────────────────────────────────────────

_PROVINCES = [
    "san josé", "san jose", "alajuela", "cartago", "heredia",
    "guanacaste", "puntarenas", "limón", "limon",
]

_NO_MEASUREMENT_PHRASES = [
    "no tengo medidas", "sin medidas", "solo fotos", "solo tengo fotos",
    "no sé las medidas", "no se las medidas",
]


def _extract_fields_from_text(text: str) -> dict:
    """Best-effort extraction of quote/warranty/visit fields from free text."""
    t = text.lower()
    fields: dict = {}

    # Province
    for prov in _PROVINCES:
        if prov in t:
            fields["provincia"] = prov.title()
            break

    # Zone / neighbourhood (look for common patterns: "en <place>", "zona de <place>")
    zone_match = re.search(r"(?:en|zona\s+de?|de)\s+([A-ZÁÉÍÓÚa-záéíóúñ]{3,}(?:\s+[A-ZÁÉÍÓÚa-záéíóúñ]+)*)", text)
    if zone_match and zone_match.group(1).lower() not in {p.split()[-1] for p in _PROVINCES}:
        fields["zona"] = zone_match.group(1).strip()

    # Number of windows / measurements
    ventanas_match = re.search(r"(\d+)\s*ventanas?", t)
    if ventanas_match:
        fields["medidas"] = f"{ventanas_match.group(1)} ventanas (pendiente medidas exactas)"

    m2_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m[²2]", t)
    if m2_match:
        fields["medidas"] = f"{m2_match.group(1)} m²"

    dim_match = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×X]\s*(\d+(?:[.,]\d+)?)", t)
    if dim_match:
        fields["medidas"] = f"{dim_match.group(1)} × {dim_match.group(2)}"

    # Need
    needs_map = {
        "calor": "control solar / calor",
        "privacidad": "privacidad",
        "seguridad": "seguridad",
        "decoración": "decoración",
        "decoracion": "decoración",
    }
    for keyword, label in needs_map.items():
        if keyword in t:
            fields["necesidad"] = label
            break

    return fields


def _detect_no_measurements(text: str) -> bool:
    t = text.lower()
    return any(phrase in t for phrase in _NO_MEASUREMENT_PHRASES)


def _format_missing_fields(missing: List[str]) -> str:
    """Build a numbered list of missing fields with their labels."""
    lines = []
    for i, field_key in enumerate(missing, 1):
        label = FIELD_LABELS.get(field_key, field_key)
        lines.append(f"{i}. {label}")
    return "\n".join(lines)


def _detect_night_privacy(text: str) -> bool:
    t = text.lower()
    return ("noche" in t or "oscur" in t or "24" in t) and "privacidad" in t


# ── Handlers ─────────────────────────────────────────────────────────────────

def _handle_greeting(phone: str) -> BotResponse:
    reply = TEMPLATES["greeting"]
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.GREETING)


def _handle_faq(phone: str, text: str) -> Optional[BotResponse]:
    """Try to answer from the FAQ/KB. Returns None if no match."""
    answer = find_answer(text)
    if answer:
        conversation_store.add_turn(phone, "bot", answer)
        return BotResponse(phone_number=phone, reply_text=answer, intent=Intent.FAQ)
    return None


def _handle_product_info(phone: str, text: str) -> BotResponse:
    # Night privacy special case
    if _detect_night_privacy(text):
        reply = TEMPLATES["night_privacy"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.PRODUCT_INFO)

    answer = find_answer(text)
    reply = answer if answer else TEMPLATES["fallback_no_match"].format(pending=PENDING_PHRASE)
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.PRODUCT_INFO)


def _handle_quote(phone: str, text: str) -> BotResponse:
    flow = conversation_store.set_flow(phone, "quote")
    extracted = _extract_fields_from_text(text)

    # Detect "no measurements" intent
    if _detect_no_measurements(text):
        flow.no_measurements = True
        extracted.pop("medidas", None)

    flow.merge(extracted)

    # Check if asking about price per meter
    t_lower = text.lower()
    if "metro" in t_lower and ("cuánto" in t_lower or "cuanto" in t_lower or "vale" in t_lower or "cuesta" in t_lower):
        reply = TEMPLATES["price_per_meter"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.QUOTE_REQUEST)

    # If first interaction in quote flow and nothing collected yet, give full intro
    if not flow.collected:
        reply = TEMPLATES["quote_initial"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.QUOTE_REQUEST)

    # If no measurements explicitly
    if flow.no_measurements and "medidas" not in flow.collected:
        # Acknowledge and continue collecting other fields
        pass

    # Check readiness
    if flow.quote_ready():
        reply = TEMPLATES["quote_handoff"]
        escalation = build_escalation_payload(
            Intent.QUOTE_REQUEST, flow, summary="Cotización lista para seguimiento",
        )
        conversation_store.clear_flow(phone)
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.QUOTE_REQUEST,
            escalated=True, escalation=escalation,
        )

    # Ask only for missing fields
    missing = flow.quote_missing()
    missing_text = _format_missing_fields(missing)

    parts = ["Gracias por la información."]
    if flow.no_measurements:
        parts.append(TEMPLATES["quote_no_measurements"])
    parts.append(f"Para continuar, aún necesito:\n{missing_text}")
    reply = "\n\n".join(parts)

    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.QUOTE_REQUEST)


def _handle_warranty(phone: str, text: str) -> BotResponse:
    flow = conversation_store.set_flow(phone, "warranty")
    extracted = _extract_fields_from_text(text)

    # Try to extract warranty-specific fields
    t = text.lower()
    if "despeg" in t or "decolor" in t or "arruga" in t or "burbuja" in t:
        extracted.setdefault("descripcion", text.strip())

    flow.merge(extracted)

    escalation = build_escalation_payload(
        Intent.WARRANTY_CLAIM, flow,
        summary="Reclamo de garantía — requiere atención",
    )

    if flow.warranty_ready():
        reply = (
            "Gracias por compartir toda la información. Un asesor de Polaritech "
            "revisará su caso y se comunicará con usted a la brevedad."
        )
        conversation_store.clear_flow(phone)
    else:
        missing = flow.warranty_missing()
        missing_text = _format_missing_fields(missing)
        reply = (
            f"{TEMPLATES['warranty_claim']}\n\n"
            f"Aún necesitamos:\n{missing_text}"
        )

    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.WARRANTY_CLAIM,
        escalated=True, escalation=escalation,
    )


def _handle_technical_visit(phone: str, text: str) -> BotResponse:
    flow = conversation_store.set_flow(phone, "visit")
    extracted = _extract_fields_from_text(text)
    flow.merge(extracted)

    escalation = build_escalation_payload(
        Intent.TECHNICAL_VISIT, flow,
        summary="Solicitud de visita técnica",
    )

    reply = TEMPLATES["technical_visit"]
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.TECHNICAL_VISIT,
        escalated=True, escalation=escalation,
    )


def _handle_competitor(phone: str, text: str) -> BotResponse:
    t = text.lower()
    if "3m" in t:
        reply = TEMPLATES["competitor_3m"]
    elif "barato" in t:
        reply = TEMPLATES["competitor_cheaper"]
    else:
        reply = TEMPLATES["competitor_cheaper"]

    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.COMPETITOR)


def _handle_discount(phone: str) -> BotResponse:
    reply = TEMPLATES["discount"]
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.DISCOUNT)


def _handle_pending_query(phone: str, text: str) -> BotResponse:
    # Pending-query intent means the topic is explicitly unconfirmed.
    # Always use the exact pending phrase — never fall back to FAQ matches
    # which could return unrelated answers.
    reply = TEMPLATES["pending_generic"].format(pending=PENDING_PHRASE)
    escalation = build_escalation_payload(
        Intent.PENDING_QUERY,
        conversation_store.get_flow(phone),
        summary=f"Consulta pendiente: {text[:80]}",
    )
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.PENDING_QUERY,
        escalated=True, escalation=escalation,
    )


def _handle_explicit_escalation(phone: str) -> BotResponse:
    flow = conversation_store.get_flow(phone)
    escalation = build_escalation_payload(
        Intent.ESCALATE, flow, summary="Solicitud directa de asesor",
    )
    reply = TEMPLATES["escalation"]
    conversation_store.clear(phone)
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.ESCALATE,
        escalated=True, escalation=escalation,
    )


def _handle_unknown(phone: str, text: str) -> BotResponse:
    # Try KB as a last resort
    kb_answer = find_answer(text)
    if kb_answer:
        conversation_store.add_turn(phone, "bot", kb_answer)
        return BotResponse(phone_number=phone, reply_text=kb_answer, intent=Intent.FAQ)

    reply = TEMPLATES["unknown"]
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.UNKNOWN)


# ── Main orchestrator ────────────────────────────────────────────────────────

def handle_message(msg: IncomingMessage) -> BotResponse:
    phone = msg.phone_number
    text = msg.text

    conversation_store.add_turn(phone, role="user", text=text)

    # Check if user is in an active quote flow and sends data (not a new intent)
    current_flow = conversation_store.get_flow(phone)
    if current_flow.flow_type == "quote":
        intent = classify_intent(text)
        # If the user isn't switching to a completely different intent, treat as
        # continued quote data
        if intent in (Intent.UNKNOWN, Intent.QUOTE_REQUEST, Intent.PRODUCT_INFO):
            extracted = _extract_fields_from_text(text)
            if _detect_no_measurements(text):
                current_flow.no_measurements = True
            if extracted or _detect_no_measurements(text):
                return _handle_quote(phone, text)

    intent = classify_intent(text)
    logger.info("Intent for %s: %s", phone, intent)

    if intent == Intent.ESCALATE:
        return _handle_explicit_escalation(phone)

    if intent == Intent.WARRANTY_CLAIM:
        return _handle_warranty(phone, text)

    if intent == Intent.TECHNICAL_VISIT:
        return _handle_technical_visit(phone, text)

    if intent == Intent.DISCOUNT:
        return _handle_discount(phone)

    if intent == Intent.COMPETITOR:
        return _handle_competitor(phone, text)

    if intent == Intent.PENDING_QUERY:
        return _handle_pending_query(phone, text)

    if intent == Intent.GREETING:
        return _handle_greeting(phone)

    if intent == Intent.QUOTE_REQUEST:
        return _handle_quote(phone, text)

    if intent == Intent.APPOINTMENT:
        reply = TEMPLATES["appointment"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(phone_number=phone, reply_text=reply, intent=Intent.APPOINTMENT)

    if intent == Intent.PRODUCT_INFO:
        # Try FAQ first for product questions
        faq_resp = _handle_faq(phone, text)
        if faq_resp:
            faq_resp.intent = Intent.PRODUCT_INFO
            return faq_resp
        return _handle_product_info(phone, text)

    # UNKNOWN — last resort
    return _handle_unknown(phone, text)
