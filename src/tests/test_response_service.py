from src.core.constants import Intent, PENDING_PHRASE
from src.schemas.chatbot import IncomingMessage
from src.services.response_service import handle_message
from src.state.conversation_store import conversation_store


PHONE = "+50688001234"


def _make_msg(text: str, phone: str = PHONE) -> IncomingMessage:
    return IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg_001",
        text=text,
        timestamp="1700000000",
    )


# ── Existing core tests (updated for new templates) ─────────────────────────

def test_greeting_response():
    resp = handle_message(_make_msg("Hola, buenas tardes"))
    assert resp.intent == Intent.GREETING
    assert "Polaritech" in resp.reply_text


def test_escalation_response():
    resp = handle_message(_make_msg("Quiero hablar con alguien"))
    assert resp.intent == Intent.ESCALATE
    assert resp.escalated is True
    assert resp.escalation is not None
    assert resp.escalation.intent == Intent.ESCALATE


def test_warranty_claim_escalates():
    resp = handle_message(_make_msg("La lámina se me está despegando"))
    assert resp.intent == Intent.WARRANTY_CLAIM
    assert resp.escalated is True
    assert resp.escalation is not None
    assert resp.escalation.priority == "high"
    assert "fotografías" in resp.reply_text.lower()


def test_technical_visit_escalates():
    resp = handle_message(_make_msg("Necesito una visita técnica"))
    assert resp.intent == Intent.TECHNICAL_VISIT
    assert resp.escalated is True
    assert resp.escalation is not None
    assert resp.escalation.priority == "normal"
    assert "gam" in resp.reply_text.lower()


def test_quote_request_asks_for_info():
    resp = handle_message(_make_msg("Necesito una cotización"))
    assert resp.intent == Intent.QUOTE_REQUEST
    assert "personalizada" in resp.reply_text.lower()
    assert "fotografías" in resp.reply_text.lower()
    assert "provincia" in resp.reply_text.lower()
    assert "medidas" in resp.reply_text.lower()


def test_unknown_response():
    resp = handle_message(_make_msg("xyzzy nonsense"))
    assert resp.intent == Intent.UNKNOWN


def test_product_info_from_kb():
    resp = handle_message(_make_msg("Información sobre Nano Cerámica"))
    assert resp.intent == Intent.PRODUCT_INFO
    assert "cerámica" in resp.reply_text.lower() or "ceramica" in resp.reply_text.lower()
