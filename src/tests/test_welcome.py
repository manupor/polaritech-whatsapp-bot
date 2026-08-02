"""
Tests for the first-contact welcome flow.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.db.database import get_db
from src.db import repositories as repo
from src.db.models import ConversationSnapshot, Contact, MessageLog
from src.main import app
from src.services.welcome_service import WELCOME_TEXT, maybe_send_welcome
from src.services.whatsapp_service import WhatsAppClient, SendResult
from src.state.idempotency_store import InMemoryIdempotencyStore, idempotency_store

client = TestClient(app)


# ── Fixtures ─────────────────────────────────────────────────────────────────

import pytest


@pytest.fixture(autouse=True)
def _reset_idempotency():
    if isinstance(idempotency_store, InMemoryIdempotencyStore):
        idempotency_store._store.clear()
    yield


def _text_payload(
    text: str = "Hola",
    msg_id: str = "wamid.welcome001",
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
                        "profile": {"name": "Nuevo Cliente"},
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


# ── Test: New contact gets greeting + image ──────────────────────────────────

@patch("src.services.welcome_service.settings")
@patch("src.api.webhook.whatsapp_client")
@patch("src.services.welcome_service.whatsapp_client")
def test_new_contact_gets_welcome(mock_welcome_wa, mock_webhook_wa, mock_settings):
    """First message from unknown contact triggers welcome text + image."""
    mock_settings.welcome_window_hours = 24.0
    mock_settings.whatsapp_welcome_image_url = "https://example.com/welcome.jpg"
    mock_settings.whatsapp_welcome_image_id = ""
    mock_settings.whatsapp_access_token = "test_token"

    mock_welcome_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_txt"))
    mock_welcome_wa.send_image = AsyncMock(return_value=SendResult(success=True, message_id="wmid_img"))
    mock_welcome_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_menu"))
    mock_webhook_wa.send_text = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))
    mock_webhook_wa.send_interactive_buttons = AsyncMock(return_value=SendResult(success=True, message_id="wmid_reply"))

    resp = client.post("/webhook", json=_text_payload(sender="50688077777"))
    assert resp.status_code == 200

    # Welcome image was sent with greeting as caption
    mock_welcome_wa.send_image.assert_called_once()
    img_call = mock_welcome_wa.send_image.call_args
    assert img_call[0][0] == "50688077777"
    assert img_call[1]["image_url"] == "https://example.com/welcome.jpg"
    assert img_call[1]["caption"] == WELCOME_TEXT

    # Interactive menu buttons were sent
    mock_welcome_wa.send_interactive_buttons.assert_called_once()


# ── Test: Existing active conversation does NOT get welcome again ────────────

@patch("src.api.webhook.whatsapp_client")
@patch("src.services.welcome_service.whatsapp_client")
def test_existing_active_conversation_no_welcome(mock_welcome_wa, mock_webhook_wa):
    """If contact has a recent snapshot, welcome is NOT sent."""
    mock_welcome_wa.send_text = AsyncMock()
    mock_welcome_wa.send_image = AsyncMock()
    mock_welcome_wa.send_interactive_buttons = AsyncMock()
    mock_webhook_wa.send_text = AsyncMock(return_value=AsyncMock(success=True, message_id=""))
    mock_webhook_wa.send_interactive_buttons = AsyncMock(return_value=AsyncMock(success=True, message_id=""))

    phone = "50688066666"

    # Seed a recent contact + snapshot
    db = get_db()
    try:
        repo.upsert_contact(db, phone, "Existing User")
        repo.upsert_snapshot(
            db,
            phone_number=phone,
            current_intent="greeting",
            last_bot_response="Previous response",
        )
        db.commit()
    finally:
        db.close()

    resp = client.post("/webhook", json=_text_payload(sender=phone, msg_id="wamid.exist001"))
    assert resp.status_code == 200

    # Welcome was NOT sent
    mock_welcome_wa.send_text.assert_not_called()
    mock_welcome_wa.send_image.assert_not_called()


# ── Test: Conversation older than 24h gets welcome again ─────────────────────

@patch("src.services.welcome_service.settings")
@patch("src.api.webhook.whatsapp_client")
@patch("src.services.welcome_service.whatsapp_client")
def test_old_conversation_gets_welcome_again(mock_welcome_wa, mock_webhook_wa, mock_settings):
    """If last snapshot is > 24h old, welcome is sent again."""
    mock_settings.welcome_window_hours = 24.0
    mock_settings.whatsapp_welcome_image_url = ""
    mock_settings.whatsapp_welcome_image_id = ""
    mock_settings.whatsapp_access_token = "test_token"

    mock_welcome_wa.send_text = AsyncMock(return_value=AsyncMock(message_id=""))
    mock_welcome_wa.send_image = AsyncMock()
    mock_welcome_wa.send_interactive_buttons = AsyncMock(return_value=AsyncMock(message_id=""))
    mock_webhook_wa.send_text = AsyncMock(return_value=AsyncMock(success=True, message_id=""))
    mock_webhook_wa.send_interactive_buttons = AsyncMock(return_value=AsyncMock(success=True, message_id=""))

    phone = "50688055555"

    # Seed contact + old snapshot (48h ago)
    db = get_db()
    try:
        repo.upsert_contact(db, phone, "Old User")
        snap = ConversationSnapshot(
            phone_number=phone,
            current_intent="greeting",
            updated_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        db.add(snap)
        db.commit()
    finally:
        db.close()

    resp = client.post("/webhook", json=_text_payload(sender=phone, msg_id="wamid.old001"))
    assert resp.status_code == 200

    # Welcome text was sent (but no image since config is empty)
    mock_welcome_wa.send_text.assert_called_once()


# ── Test: Duplicate webhook does NOT duplicate welcome ───────────────────────

@patch("src.services.welcome_service.settings")
@patch("src.api.webhook.whatsapp_client")
@patch("src.services.welcome_service.whatsapp_client")
def test_duplicate_webhook_no_duplicate_welcome(mock_welcome_wa, mock_webhook_wa, mock_settings):
    """Idempotency guard prevents welcome from being sent twice."""
    mock_settings.welcome_window_hours = 24.0
    mock_settings.whatsapp_welcome_image_url = ""
    mock_settings.whatsapp_welcome_image_id = ""
    mock_settings.whatsapp_access_token = "test_token"

    mock_welcome_wa.send_text = AsyncMock(return_value=AsyncMock(message_id=""))
    mock_welcome_wa.send_image = AsyncMock()
    mock_welcome_wa.send_interactive_buttons = AsyncMock(return_value=AsyncMock(message_id=""))
    mock_webhook_wa.send_text = AsyncMock(return_value=AsyncMock(success=True, message_id=""))
    mock_webhook_wa.send_interactive_buttons = AsyncMock(return_value=AsyncMock(success=True, message_id=""))

    payload = _text_payload(sender="50688044444", msg_id="wamid.dedup_welcome")
    resp1 = client.post("/webhook", json=payload)
    resp2 = client.post("/webhook", json=payload)
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    # Welcome text sent only once
    assert mock_welcome_wa.send_text.call_count == 1


# ── Test: Missing image config sends only greeting text ──────────────────────

@patch("src.services.welcome_service.settings")
@patch("src.api.webhook.whatsapp_client")
@patch("src.services.welcome_service.whatsapp_client")
def test_missing_image_config_text_only(mock_welcome_wa, mock_webhook_wa, mock_settings):
    """If no image URL/ID configured, only welcome text is sent."""
    mock_settings.welcome_window_hours = 24.0
    mock_settings.whatsapp_welcome_image_url = ""
    mock_settings.whatsapp_welcome_image_id = ""
    mock_settings.whatsapp_access_token = "test_token"

    mock_welcome_wa.send_text = AsyncMock(return_value=AsyncMock(message_id=""))
    mock_welcome_wa.send_image = AsyncMock()
    mock_welcome_wa.send_interactive_buttons = AsyncMock(return_value=AsyncMock(message_id=""))
    mock_webhook_wa.send_text = AsyncMock(return_value=AsyncMock(success=True, message_id=""))
    mock_webhook_wa.send_interactive_buttons = AsyncMock(return_value=AsyncMock(success=True, message_id=""))

    resp = client.post("/webhook", json=_text_payload(sender="50688033333", msg_id="wamid.noimg001"))
    assert resp.status_code == 200

    # Text sent, image NOT sent
    mock_welcome_wa.send_text.assert_called_once()
    mock_welcome_wa.send_image.assert_not_called()


# ── Test: Outbound image payload format ──────────────────────────────────────

def test_image_payload_with_url():
    """Build image payload using a URL."""
    payload = WhatsAppClient._build_image_payload(
        "50688001234", image_url="https://example.com/img.jpg", caption="Welcome",
    )
    assert payload["messaging_product"] == "whatsapp"
    assert payload["type"] == "image"
    assert payload["to"] == "50688001234"
    assert payload["image"]["link"] == "https://example.com/img.jpg"
    assert payload["image"]["caption"] == "Welcome"
    assert "id" not in payload["image"]


def test_image_payload_with_media_id():
    """Build image payload using a pre-uploaded media ID."""
    payload = WhatsAppClient._build_image_payload(
        "50688001234", media_id="media_123456",
    )
    assert payload["image"]["id"] == "media_123456"
    assert "link" not in payload["image"]


def test_image_payload_media_id_takes_priority():
    """If both are given, media_id is used."""
    payload = WhatsAppClient._build_image_payload(
        "50688001234", image_url="https://example.com/img.jpg", media_id="media_123",
    )
    assert payload["image"]["id"] == "media_123"
    assert "link" not in payload["image"]


# ── Test: is_new_conversation repo helper ────────────────────────────────────

def test_is_new_conversation_no_contact():
    db = get_db()
    try:
        assert repo.is_new_conversation(db, "+50600000000") is True
    finally:
        db.close()


def test_is_new_conversation_contact_no_snapshot():
    db = get_db()
    try:
        repo.upsert_contact(db, "+50600000001", "Test")
        db.commit()
        assert repo.is_new_conversation(db, "+50600000001") is True
    finally:
        db.close()


def test_is_new_conversation_recent_snapshot():
    db = get_db()
    try:
        repo.upsert_contact(db, "+50600000002", "Test")
        repo.upsert_snapshot(db, phone_number="+50600000002", current_intent="greeting")
        db.commit()
        assert repo.is_new_conversation(db, "+50600000002") is False
    finally:
        db.close()


def test_is_new_conversation_old_snapshot():
    db = get_db()
    try:
        repo.upsert_contact(db, "+50600000003", "Test")
        snap = ConversationSnapshot(
            phone_number="+50600000003",
            current_intent="greeting",
            updated_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        db.add(snap)
        db.commit()
        assert repo.is_new_conversation(db, "+50600000003", window_hours=24.0) is True
    finally:
        db.close()
