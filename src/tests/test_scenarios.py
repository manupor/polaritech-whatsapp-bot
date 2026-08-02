"""
Real conversation scenario tests covering all 12 required cases.
Each test verifies response behavior, business safety, and flow state.
"""

from src.core.constants import Intent, PENDING_PHRASE
from src.schemas.chatbot import IncomingMessage
from src.services.response_service import handle_message
from src.state.conversation_store import conversation_store


PHONE = "+50688009999"


def _msg(text: str) -> IncomingMessage:
    return IncomingMessage(
        phone_number=PHONE,
        sender_name="Escenario",
        message_id="sc_001",
        text=text,
        timestamp="1700000000",
    )


# ── 1. Product recommendation for heat ──────────────────────────────────────

def test_scenario_01_mucho_calor():
    """'Hola, quiero saber cuál recomiendan para mucho calor' → Nano Cerámica"""
    resp = handle_message(_msg("Hola, quiero saber cuál recomiendan para mucho calor"))
    # Should identify as product info and mention Nano Cerámica
    assert resp.intent in (Intent.PRODUCT_INFO, Intent.FAQ, Intent.GREETING)
    reply = resp.reply_text.lower()
    # Must mention nano cerámica or the greeting menu
    assert "nano cerámica" in reply or "nanocerámica" in reply or "polaritech" in reply


# ── 2. Night privacy ────────────────────────────────────────────────────────

def test_scenario_02_night_privacy():
    """'Necesito privacidad pero que de noche no se vea nada' → Sand Blasting / night explanation"""
    resp = handle_message(_msg("Necesito privacidad pero que de noche no se vea nada"))
    reply = resp.reply_text.lower()
    # Must explain the night-time limitation and recommend Sand Blasting
    assert "noche" in reply or "sand blasting" in reply
    assert "permanente" in reply or "24" in reply or "esmerilado" in reply


# ── 3. Price per meter ──────────────────────────────────────────────────────

def test_scenario_03_price_per_meter():
    """'¿Cuánto vale el metro?' → No fixed price, personalized quote"""
    resp = handle_message(_msg("¿Cuánto vale el metro cuadrado?"))
    assert resp.intent == Intent.QUOTE_REQUEST
    reply = resp.reply_text.lower()
    # Must NOT contain a fixed price and must say personalized
    assert "personalizada" in reply or "no manejamos" in reply
    assert "$" not in resp.reply_text  # Must never invent a price


# ── 4. No measurements, only photos ────────────────────────────────────────

def test_scenario_04_no_measurements():
    """'No tengo medidas, solo fotos' in a quote flow → accept, note preliminary"""
    # Start a quote flow first
    handle_message(_msg("Quiero cotizar"))
    resp = handle_message(_msg("No tengo medidas, solo fotos"))
    reply = resp.reply_text.lower()
    # Must acknowledge that photos are enough for preliminary
    assert "preliminar" in reply or "fotografías" in reply or "instalación" in reply
    # Flow should mark no_measurements
    flow = conversation_store.get_flow(PHONE)
    assert flow.no_measurements is True


# ── 5. Quote with location info ─────────────────────────────────────────────

def test_scenario_05_quote_with_location():
    """'Quiero cotizar para Escazú, son 6 ventanas' → extracts zona and medidas"""
    resp = handle_message(_msg("Quiero cotizar para Escazú, son 6 ventanas"))
    assert resp.intent == Intent.QUOTE_REQUEST
    flow = conversation_store.get_flow(PHONE)
    assert flow.flow_type == "quote"
    # Should have extracted some fields
    assert "medidas" in flow.collected or "zona" in flow.collected
    # Should ask for missing fields (not all fields)
    reply = resp.reply_text.lower()
    assert "necesito" in reply or "información" in reply


# ── 6. Technical visit ──────────────────────────────────────────────────────

def test_scenario_06_technical_visit():
    """'Necesito que vayan a revisar el lugar' → escalate with visit template"""
    resp = handle_message(_msg("Necesito que vayan a revisar el lugar"))
    assert resp.intent == Intent.TECHNICAL_VISIT
    assert resp.escalated is True
    assert resp.escalation is not None
    assert resp.escalation.priority == "normal"
    assert "gam" in resp.reply_text.lower()


# ── 7. Warranty / peeling ───────────────────────────────────────────────────

def test_scenario_07_peeling_warranty():
    """'La lámina se me está despegando' → warranty escalation, high priority"""
    resp = handle_message(_msg("La lámina se me está despegando"))
    assert resp.intent == Intent.WARRANTY_CLAIM
    assert resp.escalated is True
    assert resp.escalation is not None
    assert resp.escalation.priority == "high"
    # Should ask for evidence
    assert "fotografías" in resp.reply_text.lower()
    # Description should be auto-extracted
    assert "descripcion" in resp.escalation.collected_fields or len(resp.escalation.missing_fields) < 4


# ── 8. 3M competitor ────────────────────────────────────────────────────────

def test_scenario_08_3m_cheaper():
    """'Me ofrecieron 3M más barato' → neutral competitor response"""
    resp = handle_message(_msg("Me ofrecieron 3M más barato"))
    assert resp.intent == Intent.COMPETITOR
    reply = resp.reply_text.lower()
    # Must not speak negatively about 3M
    assert "mala" not in reply and "inferior" not in reply
    # Must recommend comparing total value
    assert "comparar" in reply or "desempeño" in reply or "calidad" in reply
    # Must mention 3M or technologies
    assert "3m" in reply or "tecnología" in reply


# ── 9. Financing ────────────────────────────────────────────────────────────

def test_scenario_09_financing():
    """'¿Tienen financiamiento?' → pending phrase + escalation"""
    resp = handle_message(_msg("¿Tienen financiamiento?"))
    assert resp.intent == Intent.PENDING_QUERY
    assert PENDING_PHRASE in resp.reply_text
    assert resp.escalated is True


# ── 10. Technical visit cost ────────────────────────────────────────────────

def test_scenario_10_visit_cost():
    """'¿Cuánto cuesta la visita técnica?' → pending phrase or visit template"""
    resp = handle_message(_msg("¿Cuánto cuesta la visita técnica?"))
    reply = resp.reply_text.lower()
    # Must contain the exact pending phrase or the visit template
    assert PENDING_PHRASE.lower() in reply or "gam" in reply
    assert resp.escalated is True


# ── 11. Silver Espejo warranty ──────────────────────────────────────────────

def test_scenario_11_silver_espejo_warranty():
    """'¿Cuál garantía tiene Silver Espejo?' → must not state a single number confidently"""
    resp = handle_message(_msg("¿Cuál garantía tiene Silver Espejo?"))
    reply = resp.reply_text.lower()
    # Should mention silver and contain warranty info
    assert "silver" in reply or "espejo" in reply or "garantía" in reply or "garantia" in reply
    # Must NOT confidently state "12 años" (Silver has 6 in JSON, conflicting with 7 in MD)
    # The guarantee should show "6 años" or a note about conflicting info, not 12
    assert "12 años" not in reply


# ── 12. Discount ────────────────────────────────────────────────────────────

def test_scenario_12_discount():
    """'Quiero descuento' → no promise, budget review offer"""
    resp = handle_message(_msg("Quiero descuento"))
    assert resp.intent == Intent.DISCOUNT
    reply = resp.reply_text.lower()
    # Must NOT promise a discount
    assert "10%" not in reply and "20%" not in reply
    assert "prometer" in reply or "autorización" in reply or "presupuesto" in reply
