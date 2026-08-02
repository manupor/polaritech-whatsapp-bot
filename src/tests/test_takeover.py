"""
Tests for human takeover, bot pause/resume, dashboard actions,
and menu options 1-6 routing.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.db.database import get_db
from src.db import repositories as repo
from src.main import app
from src.schemas.chatbot import IncomingMessage
from src.services.response_service import handle_message
from src.services.whatsapp_service import SendResult
from src.state.idempotency_store import InMemoryIdempotencyStore, idempotency_store

client = TestClient(app)


import pytest


@pytest.fixture(autouse=True)
def _reset_idempotency():
    if isinstance(idempotency_store, InMemoryIdempotencyStore):
        idempotency_store._store.clear()
    yield


def _text_payload(
    text: str = "Hola",
    msg_id: str = "wamid.tk001",
    sender: str = "50688009999",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551234567",
                        "phone_number_id": "PHONE_ID",
                    },
                    "contacts": [{
                        "profile": {"name": "Test User"},
                        "wa_id": sender,
                    }],
                    "messages": [{
                        "from": sender,
                        "id": msg_id,
                        "timestamp": "1700000000",
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
            }],
        }],
    }


def _seed_conversation(phone: str, takeover: bool = False):
    """Create a contact + snapshot for testing."""
    db = get_db()
    try:
        repo.upsert_contact(db, phone, "Test User")
        repo.upsert_snapshot(
            db,
            phone_number=phone,
            current_intent="greeting",
            last_bot_response="Previous response",
        )
        if takeover:
            repo.set_human_takeover(db, phone, takeover=True)
        db.commit()
    finally:
        db.close()


# ── Human takeover: bot does not respond ─────────────────────────────────────

@patch("src.api.webhook.whatsapp_client")
@patch("src.services.welcome_service.whatsapp_client")
def test_bot_paused_when_human_takeover(mock_welcome_wa, mock_webhook_wa):
    """When human_takeover=true, bot should NOT send a response."""
    mock_welcome_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_txt"))
    mock_welcome_wa.send_image = AsyncMock(return_value=SendResult(success=True, message_id="wmid_img"))
    mock_welcome_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_menu"))
    mock_webhook_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    mock_webhook_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))

    phone = "50688088001"
    _seed_conversation(phone, takeover=True)

    resp = client.post("/webhook", json=_text_payload(
        text="Necesito una cotización", sender=phone, msg_id="wamid.paused001",
    ))
    assert resp.status_code == 200

    # The webhook whatsapp_client should NOT have been called for the bot response
    mock_webhook_wa.send_text.assert_not_called()


# ── Bot responds normally when NOT in takeover ───────────────────────────────

@patch("src.api.webhook.whatsapp_client")
@patch("src.services.welcome_service.whatsapp_client")
def test_bot_responds_when_not_takeover(mock_welcome_wa, mock_webhook_wa):
    """When human_takeover=false, bot responds normally."""
    mock_welcome_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_txt"))
    mock_welcome_wa.send_image = AsyncMock(return_value=SendResult(success=True, message_id="wmid_img"))
    mock_welcome_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_menu"))
    mock_webhook_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    mock_webhook_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))

    phone = "50688088002"
    _seed_conversation(phone, takeover=False)

    resp = client.post("/webhook", json=_text_payload(
        text="Hola", sender=phone, msg_id="wamid.active001",
    ))
    assert resp.status_code == 200

    # Bot should have sent a response (greeting uses buttons)
    mock_webhook_wa.send_interactive_buttons.assert_called_once()


# ── Dashboard takeover action ────────────────────────────────────────────────

def test_dashboard_takeover_action():
    phone = "+50688088003"
    _seed_conversation(phone)

    resp = client.post(
        "/dashboard/conversations/takeover",
        data={"phone": phone},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    # Verify takeover is set
    db = get_db()
    try:
        snap = repo.get_snapshot_by_phone(db, phone)
        assert snap.human_takeover == 1
        assert snap.bot_active == 0
    finally:
        db.close()


# ── Dashboard resume action ──────────────────────────────────────────────────

def test_dashboard_resume_action():
    phone = "+50688088004"
    _seed_conversation(phone, takeover=True)

    resp = client.post(
        "/dashboard/conversations/resume",
        data={"phone": phone},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    # Verify takeover is cleared
    db = get_db()
    try:
        snap = repo.get_snapshot_by_phone(db, phone)
        assert snap.human_takeover == 0
        assert snap.bot_active == 1
    finally:
        db.close()


# ── Dashboard mark-lead action ───────────────────────────────────────────────

def test_dashboard_mark_lead():
    phone = "+50688088005"
    _seed_conversation(phone)

    resp = client.post(
        "/dashboard/conversations/mark-lead",
        data={"phone": phone},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    # Verify lead was created
    db = get_db()
    try:
        leads = repo.list_leads(db, status="new")
        assert any(l.phone_number == phone for l in leads)
    finally:
        db.close()


# ── Dashboard mark-escalation action ─────────────────────────────────────────

def test_dashboard_mark_escalation():
    phone = "+50688088006"
    _seed_conversation(phone)

    resp = client.post(
        "/dashboard/conversations/mark-escalation",
        data={"phone": phone},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    # Verify escalation was created
    db = get_db()
    try:
        escs = repo.list_escalations(db, status="open")
        assert any(e.phone_number == phone for e in escs)
    finally:
        db.close()


# ── Dashboard actions return 404 for unknown phone ───────────────────────────

def test_takeover_404_unknown_phone():
    resp = client.post(
        "/dashboard/conversations/takeover",
        data={"phone": "+000"},
    )
    assert resp.status_code == 404


def test_resume_404_unknown_phone():
    resp = client.post(
        "/dashboard/conversations/resume",
        data={"phone": "+000"},
    )
    assert resp.status_code == 404


def test_mark_lead_404_unknown_phone():
    resp = client.post(
        "/dashboard/conversations/mark-lead",
        data={"phone": "+000"},
    )
    assert resp.status_code == 404


def test_mark_escalation_404_unknown_phone():
    resp = client.post(
        "/dashboard/conversations/mark-escalation",
        data={"phone": "+000"},
    )
    assert resp.status_code == 404


# ── is_bot_paused repo helper ────────────────────────────────────────────────

def test_is_bot_paused_no_snapshot():
    db = get_db()
    try:
        assert repo.is_bot_paused(db, "+000") is False
    finally:
        db.close()


def test_is_bot_paused_with_takeover():
    phone = "+50688088007"
    _seed_conversation(phone, takeover=True)
    db = get_db()
    try:
        assert repo.is_bot_paused(db, phone) is True
    finally:
        db.close()


def test_is_bot_paused_without_takeover():
    phone = "+50688088008"
    _seed_conversation(phone, takeover=False)
    db = get_db()
    try:
        assert repo.is_bot_paused(db, phone) is False
    finally:
        db.close()


# ── Menu options 1-6: greeting + each option intent ──────────────────────────

def _msg(text: str, phone: str = "+1") -> IncomingMessage:
    return IncomingMessage(
        phone_number=phone, sender_name="Test", message_id="test_id",
        text=text, timestamp="1700000000",
    )


def test_menu_greeting():
    resp = handle_message(_msg("Hola buenas tardes"))
    assert resp.intent.value == "greeting"
    assert "Valentina" in resp.reply_text


def test_menu_option_1_cotizacion():
    resp = handle_message(_msg("Quiero solicitar una cotización"))
    assert resp.intent.value == "quote_request"
    assert "cotización" in resp.reply_text.lower() or "cotizacion" in resp.reply_text.lower()


def test_menu_option_2_producto():
    resp = handle_message(_msg("Información sobre nano cerámica"))
    assert resp.intent.value in ("product_info", "faq")


def test_menu_option_3_precios():
    resp = handle_message(_msg("Cuánto cuesta el metro cuadrado"))
    assert resp.intent.value == "quote_request"


def test_menu_option_4_visita_tecnica():
    resp = handle_message(_msg("Necesito una visita técnica"))
    assert resp.intent.value == "technical_visit"
    assert resp.escalated is True


def test_menu_option_5_privacidad():
    resp = handle_message(_msg("Qué opciones tienen de privacidad"))
    assert resp.intent.value in ("product_info", "faq")


def test_menu_option_6_fachada():
    resp = handle_message(_msg("Tengo restricciones de fachada"))
    # Should find KB info about facade restrictions or fall to product_info
    assert resp.intent.value in ("product_info", "faq", "unknown")
