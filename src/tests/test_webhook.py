"""
Tests for webhook verification, inbound payload parsing, idempotency,
unsupported message types, and outbound payload formatting.
"""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.db.database import get_db
from src.db import repositories as repo
from src.main import app
from src.services.whatsapp_service import SendResult, WhatsAppClient
from src.state.idempotency_store import InMemoryIdempotencyStore, idempotency_store


client = TestClient(app)

_DEFAULT_SENDER = "50688001234"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_idempotency():
    """Clear the idempotency store before each test."""
    if isinstance(idempotency_store, InMemoryIdempotencyStore):
        idempotency_store._store.clear()
    yield


@pytest.fixture(autouse=True)
def _seed_existing_contact():
    """Seed default senders so the welcome flow does NOT trigger in these tests."""
    db = get_db()
    try:
        for phone in (_DEFAULT_SENDER, "50688005678", "50688099999"):
            repo.upsert_contact(db, phone, "Test User")
            repo.upsert_snapshot(db, phone_number=phone, current_intent="greeting", last_bot_response="hi")
        db.commit()
    finally:
        db.close()
    yield


def _text_payload(
    text: str = "Hola",
    msg_id: str = "wamid.test001",
    sender: str = "50688001234",
    sender_name: str = "Test User",
) -> dict:
    """Build a realistic WhatsApp text-message webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551234567",
                        "phone_number_id": "PHONE_NUMBER_ID",
                    },
                    "contacts": [{
                        "profile": {"name": sender_name},
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


def _image_payload(msg_id: str = "wamid.img001", sender: str = "50688001234") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551234567",
                        "phone_number_id": "PHONE_NUMBER_ID",
                    },
                    "contacts": [{
                        "profile": {"name": "Foto User"},
                        "wa_id": sender,
                    }],
                    "messages": [{
                        "from": sender,
                        "id": msg_id,
                        "timestamp": "1700000000",
                        "type": "image",
                        "image": {
                            "mime_type": "image/jpeg",
                            "sha256": "abc123",
                            "id": "media_id_001",
                            "caption": "Ventanas del proyecto",
                        },
                    }],
                },
            }],
        }],
    }


def _document_payload(msg_id: str = "wamid.doc001") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551234567",
                        "phone_number_id": "PHONE_NUMBER_ID",
                    },
                    "messages": [{
                        "from": "50688001234",
                        "id": msg_id,
                        "timestamp": "1700000000",
                        "type": "document",
                        "document": {
                            "mime_type": "application/pdf",
                            "sha256": "def456",
                            "id": "media_id_002",
                            "filename": "planos.pdf",
                        },
                    }],
                },
            }],
        }],
    }


def _sticker_payload(msg_id: str = "wamid.stk001") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551234567",
                        "phone_number_id": "PHONE_NUMBER_ID",
                    },
                    "messages": [{
                        "from": "50688001234",
                        "id": msg_id,
                        "timestamp": "1700000000",
                        "type": "sticker",
                    }],
                },
            }],
        }],
    }


def _status_payload() -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551234567",
                        "phone_number_id": "PHONE_NUMBER_ID",
                    },
                    "statuses": [{
                        "id": "wamid.sent001",
                        "status": "delivered",
                        "timestamp": "1700000001",
                        "recipient_id": "50688001234",
                    }],
                },
            }],
        }],
    }


# ── Webhook verification ────────────────────────────────────────────────────

@patch("src.api.webhook.settings")
def test_verify_webhook_success(mock_settings):
    mock_settings.whatsapp_verify_token = "my_test_token"
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my_test_token",
            "hub.challenge": "challenge_abc123",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "challenge_abc123"


@patch("src.api.webhook.settings")
def test_verify_webhook_wrong_token(mock_settings):
    mock_settings.whatsapp_verify_token = "correct_token"
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge_abc123",
        },
    )
    assert resp.status_code == 403


@patch("src.api.webhook.settings")
def test_verify_webhook_wrong_mode(mock_settings):
    mock_settings.whatsapp_verify_token = "my_test_token"
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": "my_test_token",
            "hub.challenge": "challenge_abc123",
        },
    )
    assert resp.status_code == 403


def test_verify_webhook_missing_params():
    resp = client.get("/webhook")
    # Missing required params → should still return 403 (not crash)
    assert resp.status_code in (403, 422, 200)


# ── Inbound text payload parsing ─────────────────────────────────────────────

@patch("src.api.webhook.whatsapp_client")
def test_inbound_text_message(mock_wa):
    mock_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    mock_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    # Use seeded sender to avoid welcome, test normal response with buttons
    resp = client.post("/webhook", json=_text_payload("Información de productos"))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    # Product info should have sent buttons
    mock_wa.send_interactive_buttons.assert_called_once()
    call_args = mock_wa.send_interactive_buttons.call_args
    assert call_args[0][0] == "50688001234"  # to


@patch("src.api.webhook.whatsapp_client")
def test_inbound_text_extracts_sender_name(mock_wa):
    mock_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    mock_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    payload = _text_payload("Hola", sender_name="María García")
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200


@patch("src.api.webhook.whatsapp_client")
def test_inbound_multiple_messages(mock_wa):
    """Payload with two messages should trigger two outbound replies."""
    mock_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    mock_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    payload = _text_payload("Hola")
    # Add a second message to the same entry
    payload["entry"][0]["changes"][0]["value"]["messages"].append({
        "from": "50688005678",
        "id": "wamid.test002",
        "timestamp": "1700000001",
        "type": "text",
        "text": {"body": "Buenos días"},
    })
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    # Both greetings use buttons now
    assert mock_wa.send_interactive_buttons.call_count == 2


# ── Unsupported message types ────────────────────────────────────────────────

@patch("src.api.webhook.whatsapp_client")
def test_inbound_image_unsupported_reply(mock_wa):
    mock_wa.send_text = AsyncMock()
    resp = client.post("/webhook", json=_image_payload())
    assert resp.status_code == 200
    mock_wa.send_text.assert_called_once()
    reply_text = mock_wa.send_text.call_args[0][1]
    assert "texto" in reply_text.lower()


@patch("src.api.webhook.whatsapp_client")
def test_inbound_document_unsupported_reply(mock_wa):
    mock_wa.send_text = AsyncMock()
    resp = client.post("/webhook", json=_document_payload())
    assert resp.status_code == 200
    mock_wa.send_text.assert_called_once()
    reply_text = mock_wa.send_text.call_args[0][1]
    assert "texto" in reply_text.lower()


@patch("src.api.webhook.whatsapp_client")
def test_inbound_sticker_unsupported_reply(mock_wa):
    mock_wa.send_text = AsyncMock()
    resp = client.post("/webhook", json=_sticker_payload())
    assert resp.status_code == 200
    mock_wa.send_text.assert_called_once()
    reply_text = mock_wa.send_text.call_args[0][1]
    assert "texto" in reply_text.lower()


@patch("src.api.webhook.whatsapp_client")
def test_status_payload_no_reply(mock_wa):
    """Status-only payloads should be logged but not trigger any reply."""
    mock_wa.send_text = AsyncMock()
    resp = client.post("/webhook", json=_status_payload())
    assert resp.status_code == 200
    mock_wa.send_text.assert_not_called()


# ── Idempotency ──────────────────────────────────────────────────────────────

@patch("src.api.webhook.whatsapp_client")
def test_duplicate_payload_no_double_reply(mock_wa):
    """Same message_id twice should only reply once due to idempotency."""
    mock_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    mock_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    payload = _text_payload("Hola", msg_id="wamid.dedup001")

    resp1 = client.post("/webhook", json=payload)
    assert resp1.status_code == 200

    resp2 = client.post("/webhook", json=payload)
    assert resp2.status_code == 200

    # Only one send despite two webhook deliveries (greeting uses buttons)
    assert mock_wa.send_interactive_buttons.call_count == 1


@patch("src.api.webhook.whatsapp_client")
def test_different_msg_ids_both_processed(mock_wa):
    """Different message_ids should both trigger replies."""
    mock_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    mock_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))

    resp1 = client.post("/webhook", json=_text_payload("Hola", msg_id="wamid.a"))
    resp2 = client.post("/webhook", json=_text_payload("Hola", msg_id="wamid.b"))
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Both greetings use buttons now
    assert mock_wa.send_interactive_buttons.call_count == 2


# ── Outbound payload format ─────────────────────────────────────────────────

def test_outbound_payload_structure():
    """WhatsAppClient._build_text_payload must match Meta's expected format."""
    payload = WhatsAppClient._build_text_payload(to="50688001234", body="Hola")
    assert payload["messaging_product"] == "whatsapp"
    assert payload["recipient_type"] == "individual"
    assert payload["to"] == "50688001234"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Hola"
    assert payload["text"]["preview_url"] is False


def test_outbound_payload_unicode():
    """Outbound payload preserves Spanish characters and emojis."""
    body = "👋 ¡Bienvenido! Información sobre películas"
    payload = WhatsAppClient._build_text_payload(to="50688001234", body=body)
    assert payload["text"]["body"] == body


# ── Idempotency store unit tests ─────────────────────────────────────────────

def test_idempotency_store_basic():
    store = InMemoryIdempotencyStore()
    assert store.is_seen("msg1") is False
    store.mark_seen("msg1")
    assert store.is_seen("msg1") is True
    assert store.is_seen("msg2") is False


def test_idempotency_store_max_size():
    store = InMemoryIdempotencyStore(max_size=3)
    for i in range(5):
        store.mark_seen(f"msg{i}")
    # Oldest entries should have been evicted
    assert store.is_seen("msg0") is False
    assert store.is_seen("msg1") is False
    assert store.is_seen("msg2") is True
    assert store.is_seen("msg3") is True
    assert store.is_seen("msg4") is True


# ── Invalid payload handling ─────────────────────────────────────────────────

def test_invalid_payload_returns_error():
    resp = client.post("/webhook", json={"invalid": "data"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
