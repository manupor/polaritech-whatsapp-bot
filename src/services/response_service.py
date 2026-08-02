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
from typing import Dict, List, Optional

from src.core.constants import (
    BUTTONS_FOLLOWUP_PROMPT,
    BUTTON_ID_TO_INTENT,
    FIELD_LABELS,
    FLOW_BUTTON_IDS,
    FLOW_TEXT_ALIASES,
    INTENT_BUTTONS,
    INTERACTIVE_BODY_LIMIT,
    Intent,
    INTENT_KEYWORDS,
    NEED_TO_PRODUCT,
    normalize_text,
    PENDING_PHRASE,
    QUOTE_NO_MEASUREMENTS,
    TEMPLATES,
    TEXT_ALIASES,
)
from src.schemas.chatbot import BotResponse, EscalationPayload, IncomingMessage
from src.services.escalation_service import build_escalation_payload, should_escalate
from src.services.faq_service import find_answer
from src.services.intent_service import classify_intent
from src.services.llm_intent_service import classify_intent_with_llm
from src.services.llm_rag_service import rewrite_response_with_llm
from src.state.conversation_store import FlowState, conversation_store

logger = logging.getLogger(__name__)


def _get_buttons_for_intent(intent: Intent) -> List[dict]:
    """Return quick-reply buttons for a given intent."""
    return INTENT_BUTTONS.get(intent, [])


def _get_post_closure_buttons(flow_type: str) -> List[dict]:
    """Return buttons shown after a flow completes (no collection buttons)."""
    return [
        {"id": "go_main_menu", "title": "🏠 Menú principal"},
        {"id": "start_visit_flow", "title": "📅 Agendar visita"},
        {"id": "human_help", "title": "👤 Hablar con asesor"},
    ]


def _get_intent_source(intent: Intent, button_id: Optional[str], normalized_text: str) -> str:
    """Return a string indicating how the intent was resolved."""
    if button_id and button_id in BUTTON_ID_TO_INTENT:
        return "button_id"
    if normalized_text in TEXT_ALIASES:
        return "text_alias"
    if intent != Intent.UNKNOWN:
        return "classifier"
    return "fallback"


def _resolve_intent_unified(
    text: str,
    button_id: Optional[str] = None,
    active_flow: Optional[str] = None,
) -> Intent:
    """
    Unified intent resolver with priority:
    1. button_id (interactive message) - direct mapping
    2. normalized text aliases - direct mapping
    3. LLM classification
    4. Keyword classification (fallback)
    """
    normalized = normalize_text(text)
    
    # Priority 1: button_id direct mapping
    if button_id and button_id in BUTTON_ID_TO_INTENT:
        logger.info(
            "intent_from_button_id  button_id=%s  intent=%s",
            button_id, BUTTON_ID_TO_INTENT[button_id].value,
        )
        return BUTTON_ID_TO_INTENT[button_id]
    
    # Priority 2: normalized text aliases
    if normalized in TEXT_ALIASES:
        logger.info(
            "intent_from_text_alias  normalized=%s  intent=%s",
            normalized, TEXT_ALIASES[normalized].value,
        )
        return TEXT_ALIASES[normalized]
    
    # Priority 3: LLM classification
    llm_intent = classify_intent_with_llm(text)
    if llm_intent:
        logger.info("intent_from_llm  intent=%s", llm_intent.value)
        return llm_intent
    
    # Priority 4: Keyword classification (fallback)
    keyword_intent = classify_intent(text)
    logger.info("intent_from_keywords  intent=%s", keyword_intent.value)
    return keyword_intent


def _classify_intent_hybrid(text: str) -> Intent:
    """
    Classify intent using LLM with fallback to keyword-based classification.
    LLM is tried first if configured, otherwise falls back to keywords.
    Deprecated: Use _resolve_intent_unified instead.
    """
    # Try LLM classification first
    llm_intent = classify_intent_with_llm(text)
    if llm_intent:
        logger.info(f"LLM classified intent as: {llm_intent.value}")
        return llm_intent

    # Fallback to keyword-based classification
    keyword_intent = classify_intent(text)
    logger.info(f"Keyword-based classified intent as: {keyword_intent.value}")
    return keyword_intent


# ── Field extraction helpers ─────────────────────────────────────────────────

_PROVINCES = [
    "san josé", "san jose", "alajuela", "cartago", "heredia",
    "guanacaste", "puntarenas", "limón", "limon",
]

_NO_MEASUREMENT_PHRASES = [
    "no tengo medidas", "sin medidas", "solo fotos", "solo tengo fotos",
    "no sé las medidas", "no se las medidas",
]

_NO_PHOTOS_PHRASES = [
    "no tengo fotos", "sin fotos", "no tengo fotografías", "sin fotografías",
    "no tengo fotografias", "sin fotografias",
]


def _detect_no_photos(text: str) -> bool:
    """Detect if user indicates they don't have photos."""
    t = text.lower()
    return any(phrase in t for phrase in _NO_PHOTOS_PHRASES)


def _detect_main_need(text: str) -> Optional[str]:
    """Detect main need from free text with various forms.
    Returns: 'calor', 'privacidad', 'seguridad', 'decoracion' or None.
    If multiple needs are present, returns the first one found."""
    t = normalize_text(text)
    
    # Patterns for each need - check in priority order
    if "calor" in t:
        return "calor"
    elif "privacidad" in t:
        return "privacidad"
    elif "seguridad" in t:
        return "seguridad"
    elif "decoracion" in t or "decoracion" in t:
        return "decoracion"
    
    return None


def _detect_multiple_needs(text: str) -> List[str]:
    """Detect multiple needs from free text.
    Returns list of needs found: ['calor', 'privacidad', 'seguridad', 'decoracion']."""
    t = normalize_text(text)
    needs = []
    
    if "calor" in t:
        needs.append("calor")
    if "privacidad" in t:
        needs.append("privacidad")
    if "seguridad" in t:
        needs.append("seguridad")
    if "decoracion" in t or "decoracion" in t:
        needs.append("decoracion")
    
    return needs


def _get_need_recommendation(need: str) -> str:
    """Generate contextual recommendation based on detected need."""
    recommendations = {
        "calor": "Perfecto, si su prioridad es reducir calor, la línea que normalmente se recomienda es Nano Cerámica, porque está diseñada para reducir significativamente la sensación térmica.",
        "privacidad": "Perfecto. Para privacidad diurna normalmente se recomienda Económica o Silver Espejo. Para privacidad permanente en ambos sentidos, Sand Blasting.",
        "seguridad": "Perfecto. Para seguridad, la opción indicada es la Película de Seguridad, diseñada para ayudar a retener fragmentos en caso de rotura.",
        "decoracion": "Perfecto. Para decoración o privacidad tipo vidrio esmerilado, Sand Blasting suele ser una opción recomendada.",
    }
    return recommendations.get(need, "")


def _has_quote_semantics(text: str) -> bool:
    """Check if text contains quote-related semantics.
    Returns True if text contains: province/zone, no photos, no measurements,
    measurements (2x1, 3 m2, 4 ventanas), or needs (calor, privacidad, seguridad, decoracion)."""
    t = text.lower()
    
    # Check for province
    for prov in _PROVINCES:
        if prov in t:
            return True
    
    # Check for no photos / no measurements
    if _detect_no_photos(text) or _detect_no_measurements(text):
        return True
    
    # Check for measurements patterns
    if re.search(r"(\d+)\s*ventanas?", t):
        return True
    if re.search(r"(\d+(?:[.,]\d+)?)\s*m[²2]", t):
        return True
    if re.search(r"(\d+(?:[.,]\d+)?)\s*[x×X]\s*(\d+(?:[.,]\d+)?)", t):
        return True
    
    # Check for needs
    if any(k in t for k in ["calor", "privacidad", "seguridad", "decoracion", "decoración"]):
        return True
    
    return False


def _extract_fields_from_text(text: str) -> Dict[str, str]:
    """Best-effort extraction of quote/warranty/visit fields from free text."""
    t = text.lower()
    fields: dict = {}

    # Province - handle "San José, Curridabat" and "Curridabat, San José" patterns
    for prov in _PROVINCES:
        if prov in t:
            fields["provincia"] = prov.title()
            break

    # Zone / neighbourhood - more flexible patterns
    # Try patterns: "en <place>", "zona de <place>", "de <place>", ", <place>"
    zone_match = re.search(r"(?:en|zona\s+de?|de|,)\s+([A-ZÁÉÍÓÚa-záéíóúñ]{3,}(?:\s+[A-ZÁÉÍÓÚa-záéíóúñ]+)*)", text)
    if zone_match:
        zone_candidate = zone_match.group(1).strip()
        # Don't capture if it's just a province name without context
        if zone_candidate.lower() not in {p.lower() for p in _PROVINCES}:
            fields["zona"] = zone_candidate
    else:
        # Fallback: numbered lists like "1- privacidad 2- San José"
        numbered_items = re.findall(r"(?:\d+[\.\-]\s*)([A-ZÁÉÍÓÚa-záéíóúñ\s]+)", text)
        for item in numbered_items:
            item_clean = item.strip()
            item_lower = item_clean.lower()
            # Skip if already captured as need
            if any(k in item_lower for k in ["privacidad", "calor", "seguridad", "decoración"]):
                continue
            # If it's a place name (3+ chars), capture as zone
            # Even if it's a province name (San José can be both province and zone)
            if len(item_clean) >= 3 and item_clean not in fields.values():
                fields["zona"] = item_clean
                break

    # If no zone found but province is mentioned, use province as zone
    # (flexible for Costa Rica where San José is both province and cantón)
    if "zona" not in fields and "provincia" in fields:
        fields["zona"] = fields["provincia"]

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
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.GREETING,
        buttons=_get_buttons_for_intent(Intent.GREETING),
    )


def _handle_faq(phone: str, text: str) -> Optional[BotResponse]:
    """Try to answer from the FAQ/KB. Returns None if no match."""
    answer = find_answer(text)
    if answer:
        conversation_store.add_turn(phone, "bot", answer)
        return BotResponse(
            phone_number=phone, reply_text=answer, intent=Intent.FAQ,
            buttons=_get_buttons_for_intent(Intent.FAQ),
        )
    return None


def _is_generic_product_request(text: str) -> bool:
    """Detect vague 'info de productos' requests that should show the full catalog."""
    t = text.lower().strip()
    generic_phrases = [
        "información de productos",
        "info de productos",
        "información sobre productos",
        "productos",
        "que productos tienen",
        "qué productos tienen",
        "que ofrecen",
        "qué ofrecen",
        "catálogo",
        "catalogo",
    ]
    return any(phrase in t for phrase in generic_phrases)


def _handle_product_info(phone: str, text: str) -> BotResponse:
    # Night privacy special case
    if _detect_night_privacy(text):
        reply = TEMPLATES["night_privacy"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.PRODUCT_INFO,
            buttons=_get_buttons_for_intent(Intent.PRODUCT_INFO),
        )

    # Generic "info de productos" → show full catalog
    if _is_generic_product_request(text):
        reply = TEMPLATES["product_catalog"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.PRODUCT_INFO,
            buttons=_get_buttons_for_intent(Intent.PRODUCT_INFO),
        )

    answer = find_answer(text)
    reply = answer if answer else TEMPLATES["fallback_no_match"].format(pending=PENDING_PHRASE)
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.PRODUCT_INFO,
        buttons=_get_buttons_for_intent(Intent.PRODUCT_INFO),
    )


def _handle_quote(phone: str, text: str) -> BotResponse:
    flow = conversation_store.set_flow(phone, "quote")
    extracted = _extract_fields_from_text(text)

    # Detect "no measurements" intent
    if _detect_no_measurements(text):
        flow.no_measurements = True
        extracted.pop("medidas", None)

    # Detect "no photos" intent
    if _detect_no_photos(text):
        extracted["fotografias"] = "missing"

    # Detect needs - prioritize multiple needs over single need
    multiple_needs = _detect_multiple_needs(text)
    if multiple_needs:
        # Save as combined string
        extracted["necesidad"] = ", ".join(multiple_needs)
    else:
        # Fall back to single need detection
        main_need = _detect_main_need(text)
        if main_need:
            extracted["necesidad"] = main_need

    flow.merge(extracted)

    # Check if asking about price per meter
    t_lower = text.lower()
    if "metro" in t_lower and ("cuánto" in t_lower or "cuanto" in t_lower or "vale" in t_lower or "cuesta" in t_lower):
        reply = TEMPLATES["price_per_meter"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.QUOTE_REQUEST,
            buttons=_get_buttons_for_intent(Intent.QUOTE_REQUEST),
        )

    # If first interaction in quote flow and nothing collected yet, give full intro
    if not flow.collected:
        reply = TEMPLATES["quote_initial"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.QUOTE_REQUEST,
            buttons=_get_buttons_for_intent(Intent.QUOTE_REQUEST),
        )

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
        conversation_store.add_turn(phone, "bot", reply)
        # Mark flow as completed by clearing it - will be persisted then cleared in webhook
        conversation_store.clear_flow(phone)
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.QUOTE_REQUEST,
            escalated=True, escalation=escalation,
            buttons=_get_post_closure_buttons("quote"),
        )

    # Build response with contextual recommendation if need was just provided
    parts = []
    
    # Re-detect needs for recommendation generation
    multiple_needs = _detect_multiple_needs(text)
    if multiple_needs:
        # Handle multiple needs with combined recommendations
        for need in multiple_needs:
            recommendation = _get_need_recommendation(need)
            if recommendation:
                parts.append(recommendation)
    else:
        # Fall back to single need
        main_need = _detect_main_need(text)
        if main_need:
            recommendation = _get_need_recommendation(main_need)
            if recommendation:
                parts.append(recommendation)
        else:
            parts.append("Gracias por la información.")
    
    if flow.no_measurements:
        parts.append(TEMPLATES["quote_no_measurements"])
    
    # Ask only for missing fields
    missing = flow.quote_missing()
    if missing:
        missing_text = _format_missing_fields(missing)
        parts.append(f"Para ayudarle con la cotización, ahora solo necesito:\n{missing_text}")
    
    reply = "\n\n".join(parts)

    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.QUOTE_REQUEST,
        buttons=_get_buttons_for_intent(Intent.QUOTE_REQUEST),
    )


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
        conversation_store.add_turn(phone, "bot", reply)
        # Mark flow as completed by clearing it
        conversation_store.clear_flow(phone)
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.WARRANTY_CLAIM,
            escalated=True, escalation=escalation,
            buttons=_get_post_closure_buttons("warranty"),
        )
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
        buttons=_get_buttons_for_intent(Intent.WARRANTY_CLAIM),
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
        buttons=_get_buttons_for_intent(Intent.TECHNICAL_VISIT),
    )


def _handle_competitor(phone: str, text: str) -> BotResponse:
    # First check if this matches a brand intent (brand_3m, brand_general, competitor_cheaper_3m)
    brand_answer = find_answer(text)
    if brand_answer:
        # If it's a brand intent, use that answer instead of generic competitor response
        conversation_store.add_turn(phone, "bot", brand_answer)
        return BotResponse(
            phone_number=phone, reply_text=brand_answer, intent=Intent.COMPETITOR,
            buttons=_get_buttons_for_intent(Intent.COMPETITOR),
        )
    
    # Fallback to original competitor logic
    t = text.lower()
    if "3m" in t:
        reply = TEMPLATES["competitor_3m"]
    elif "barato" in t:
        reply = TEMPLATES["competitor_cheaper"]
    else:
        reply = TEMPLATES["competitor_cheaper"]

    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.COMPETITOR,
        buttons=_get_buttons_for_intent(Intent.COMPETITOR),
    )


def _handle_discount(phone: str) -> BotResponse:
    reply = TEMPLATES["discount"]
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.DISCOUNT,
        buttons=_get_buttons_for_intent(Intent.DISCOUNT),
    )


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
        buttons=_get_buttons_for_intent(Intent.PENDING_QUERY),
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
        buttons=_get_buttons_for_intent(Intent.ESCALATE),
    )


def _handle_unknown(phone: str, text: str) -> BotResponse:
    # Try KB as a last resort
    kb_answer = find_answer(text)
    if kb_answer:
        conversation_store.add_turn(phone, "bot", kb_answer)
        return BotResponse(
            phone_number=phone, reply_text=kb_answer, intent=Intent.FAQ,
            buttons=_get_buttons_for_intent(Intent.FAQ),
        )

    reply = TEMPLATES["unknown"]
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.UNKNOWN,
        buttons=_get_buttons_for_intent(Intent.UNKNOWN),
    )


# ── Image analysis integration ───────────────────────────────────────────────

_FLOW_INTENTS = {
    "quote": Intent.QUOTE_REQUEST,
    "warranty": Intent.WARRANTY_CLAIM,
    "visit": Intent.TECHNICAL_VISIT,
}


def register_image_analysis(phone: str, description: str) -> BotResponse:
    """
    Record a photo (and its vision analysis) in the caller's active flow.

    Photos are a required field for the quote, warranty and visit flows, so the
    image counts as `fotografias` and any measurements the model found are merged
    in. The reply then continues the flow instead of restarting the conversation.
    """
    flow = conversation_store.get_flow(phone)
    if not flow.flow_type:
        flow = conversation_store.set_flow(phone, "quote")

    conversation_store.add_turn(phone, "user", "[imagen enviada]")

    updates = {"fotografias": "recibidas"}
    extracted = _extract_fields_from_text(description)
    if "medidas" in extracted:
        updates["medidas"] = extracted["medidas"]
    flow.merge(updates)

    intent = _FLOW_INTENTS.get(flow.flow_type, Intent.QUOTE_REQUEST)

    parts = [f"Gracias por la imagen. Esto es lo que detecté:\n\n{description}"]

    if flow.flow_type == "quote":
        missing = flow.quote_missing()
    elif flow.flow_type == "warranty":
        missing = flow.warranty_missing()
    else:
        missing = flow.visit_missing()

    if missing:
        parts.append(
            f"Para continuar con su solicitud, aún necesito:\n"
            f"{_format_missing_fields(missing)}"
        )
    else:
        parts.append(
            "Con esto tengo la información necesaria. "
            "Un asesor le contactará para confirmar los detalles."
        )

    reply = "\n\n".join(parts)
    conversation_store.add_turn(phone, "bot", reply)

    return BotResponse(
        phone_number=phone,
        reply_text=reply,
        intent=intent,
        buttons=_get_buttons_for_intent(intent),
    )


def _handle_flow_button(phone: str, button_id: str, flow: FlowState) -> BotResponse:
    """Handle flow-specific button clicks within active flows."""
    if button_id == QUOTE_NO_MEASUREMENTS:
        flow.no_measurements = True
        logger.info(
            "quote_no_measurements_set  phone=%s  no_measurements=True",
            phone,
        )
        return _handle_quote(phone, "")
    elif button_id == QUOTE_SCHEDULE_VISIT:
        # Switch to technical visit flow
        conversation_store.clear_flow(phone)
        return _handle_technical_visit(phone, "")
    elif button_id == QUOTE_HUMAN_HELP:
        return _handle_explicit_escalation(phone)
    
    # Unknown flow button - treat as unknown
    reply = TEMPLATES["unknown"]
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.UNKNOWN,
        buttons=_get_buttons_for_intent(Intent.UNKNOWN),
    )


def _handle_button_click(phone: str, button_id: str) -> BotResponse:
    """Handle button clicks including menu buttons and post-closure buttons."""
    # Handle menu buttons using direct mapping
    if button_id in BUTTON_ID_TO_INTENT:
        intent = BUTTON_ID_TO_INTENT[button_id]
        if intent == Intent.PRODUCT_INFO:
            return _handle_product_info(phone, "")
        elif intent == Intent.QUOTE_REQUEST:
            return _handle_quote(phone, "")
        elif intent == Intent.TECHNICAL_VISIT:
            return _handle_technical_visit(phone, "")
        elif intent == Intent.ESCALATE:
            return _handle_explicit_escalation(phone)
    
    # Handle post-closure buttons
    if button_id == "go_main_menu":
        reply = TEMPLATES["greeting"]
        conversation_store.add_turn(phone, "bot", reply)
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.GREETING,
            buttons=_get_buttons_for_intent(Intent.GREETING),
        )
    elif button_id == "start_visit_flow":
        return _handle_technical_visit(phone, "")
    elif button_id == "human_help":
        return _handle_explicit_escalation(phone)
    
    # Unknown button - treat as unknown intent
    reply = TEMPLATES["unknown"]
    conversation_store.add_turn(phone, "bot", reply)
    return BotResponse(
        phone_number=phone, reply_text=reply, intent=Intent.UNKNOWN,
        buttons=_get_buttons_for_intent(Intent.UNKNOWN),
    )


# ── Main orchestrator ────────────────────────────────────────────────────────

def handle_message(msg: IncomingMessage) -> BotResponse:
    phone = msg.phone_number
    text = msg.text
    button_id = getattr(msg, 'button_id', None)
    button_title = getattr(msg, 'button_title', None)

    conversation_store.add_turn(phone, role="user", text=text)

    current_flow = conversation_store.get_flow(phone)
    normalized_text = normalize_text(text)
    
    # Log initial state
    logger.info(
        "message_received  phone=%s  raw_text=%s  normalized_text=%s  button_id=%s  button_title=%s  active_flow=%s  pending_fields_before=%d",
        phone, text[:80], normalized_text[:80], button_id or 'n/a', button_title or 'n/a',
        current_flow.flow_type or 'idle', len(current_flow.quote_missing()) if current_flow.flow_type == 'quote' else 0,
    )
    
    # Priority 1: Check for flow-specific button IDs (handle within active flow)
    if button_id and button_id in FLOW_BUTTON_IDS:
        flow_type = FLOW_BUTTON_IDS[button_id]
        if current_flow.flow_type == flow_type:
            logger.info(
                "flow_button_handled  phone=%s  button_id=%s  flow=%s",
                phone, button_id, flow_type,
            )
            return _handle_flow_button(phone, button_id, current_flow)
    
    # Priority 2: Check for flow-specific text aliases (handle within active flow)
    if normalized_text in FLOW_TEXT_ALIASES:
        action = FLOW_TEXT_ALIASES[normalized_text]
        if current_flow.flow_type == "quote" and action == "no_measurements":
            logger.info(
                "flow_text_alias_handled  phone=%s  action=%s  flow=quote",
                phone, action,
            )
            current_flow.no_measurements = True
            return _handle_quote(phone, text)
    
    # Priority 3: Check for menu button IDs (global navigation)
    if button_id and button_id in BUTTON_ID_TO_INTENT:
        logger.info(
            "menu_button_handled  phone=%s  button_id=%s  intent=%s",
            phone, button_id, BUTTON_ID_TO_INTENT[button_id].value,
        )
        return _handle_button_click(phone, button_id)
    
    # Priority 3.5: Check for post-closure buttons (go_main_menu, start_visit_flow, human_help)
    if button_id and button_id in ("go_main_menu", "start_visit_flow", "human_help"):
        logger.info(
            "post_closure_button_handled  phone=%s  button_id=%s",
            phone, button_id,
        )
        return _handle_button_click(phone, button_id)
    
    # Priority 4: Active flow data collection
    if current_flow.flow_type == "quote":
        # Short-circuit: if message has quote semantics, handle directly without LLM classification
        if _has_quote_semantics(text):
            extracted = _extract_fields_from_text(text)
            if _detect_no_measurements(text):
                current_flow.no_measurements = True
            if _detect_no_photos(text):
                extracted["fotografias"] = "missing"
            if extracted or _detect_no_measurements(text) or _detect_no_photos(text):
                logger.info(
                    "quote_short_circuit  phone=%s  extracted=%d  no_measurements=%s  no_photos=%s",
                    phone, len(extracted), current_flow.no_measurements, _detect_no_photos(text),
                )
                return _handle_quote(phone, text)
        
        # Otherwise, proceed with intent resolution
        intent = _resolve_intent_unified(text, button_id, current_flow.flow_type)
        # Prevent technical_visit promotion from active quote flow with common text
        if intent == Intent.TECHNICAL_VISIT:
            # Only allow technical_visit if explicit visit language is present
            t_lower = text.lower()
            visit_keywords = ["visita técnica", "visita tecnica", "agendar visita", "programar visita",
                           "inspección", "inspeccion", "revisar el lugar", "ir a ver",
                           "necesito que revisen en sitio", "quiero programar visita", "pueden venir a ver"]
            if not any(kw in t_lower for kw in visit_keywords):
                # Not explicit visit language, treat as quote data
                intent = Intent.QUOTE_REQUEST
        
        if intent in (Intent.UNKNOWN, Intent.QUOTE_REQUEST, Intent.PRODUCT_INFO):
            extracted = _extract_fields_from_text(text)
            if _detect_no_measurements(text):
                current_flow.no_measurements = True
            if extracted or _detect_no_measurements(text):
                logger.info(
                    "quote_data_collected  phone=%s  extracted=%d  no_measurements=%s",
                    phone, len(extracted), current_flow.no_measurements,
                )
                return _handle_quote(phone, text)
    
    if current_flow.flow_type == "visit":
        # If the user isn't switching to a completely different intent, treat as
        # continued visit data
        intent = _resolve_intent_unified(text, button_id, current_flow.flow_type)
        if intent in (Intent.UNKNOWN, Intent.TECHNICAL_VISIT, Intent.PRODUCT_INFO):
            extracted = _extract_fields_from_text(text)
            if extracted:
                logger.info(
                    "visit_data_collected  phone=%s  extracted=%d",
                    phone, len(extracted),
                )
                return _handle_technical_visit(phone, text)
    
    # Priority 5: General intent resolution (FAQ, etc.)
    intent = _resolve_intent_unified(text, button_id, current_flow.flow_type)
    
    logger.info(
        "resolved_intent  phone=%s  intent=%s  source=%s",
        phone, intent.value, _get_intent_source(intent, button_id, normalized_text),
    )

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
        return BotResponse(
            phone_number=phone, reply_text=reply, intent=Intent.APPOINTMENT,
            buttons=_get_buttons_for_intent(Intent.APPOINTMENT),
        )

    if intent == Intent.PRODUCT_INFO:
        # Try FAQ first for product questions
        faq_resp = _handle_faq(phone, text)
        if faq_resp:
            faq_resp.intent = Intent.PRODUCT_INFO
            return faq_resp
        return _handle_product_info(phone, text)

    # UNKNOWN — last resort
    return _handle_unknown(phone, text)
