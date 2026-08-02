"""
Tests for flow completion state handling to prevent bugs where:
- Completed flows revive and show collection buttons
- Post-closure buttons don't work correctly
- Button IDs are not respected
"""

import pytest
from src.schemas.chatbot import IncomingMessage
from src.services.response_service import handle_message, _handle_button_click
from src.state.conversation_store import conversation_store
from src.core.constants import Intent


def test_quote_completion_clears_flow_with_post_closure_buttons():
    """Test that completing a quote flow shows post-closure buttons, not collection buttons."""
    phone = "+50612345678"
    conversation_store.clear(phone)  # Start fresh

    # Simulate completing a quote flow
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="San José, Escazú, calor, tengo medidas 2x3",
        timestamp="2024-01-01T00:00:00",
    )

    # This would normally complete the flow, but we'll test the handler directly
    from src.services.response_service import _handle_quote
    response = _handle_quote(phone, msg.text)

    # After completion, response should have post-closure buttons
    # (This is a simplified test - in reality flow completion happens when all fields are collected)
    # The key is that buttons should NOT include "No tengo medidas" after completion
    button_ids = [b.get("id") for b in response.buttons]
    assert "no_measurements" not in button_ids, "Should not show 'No tengo medidas' after completion"


def test_button_click_respects_button_id():
    """Test that button clicks use button_id, not text classification."""
    phone = "+50612345678"
    conversation_store.clear(phone)

    # Simulate clicking "go_main_menu" button
    response = _handle_button_click(phone, "go_main_menu")

    # Should return greeting with menu buttons
    assert response.intent == Intent.GREETING
    assert "valentina" in response.reply_text.lower() or "asistente" in response.reply_text.lower()
    
    # Should have menu buttons, not post-closure buttons
    button_ids = [b.get("id") for b in response.buttons]
    assert "menu_productos" in button_ids or "menu_cotizacion" in button_ids


def test_button_click_start_visit_flow():
    """Test that 'start_visit_flow' button starts technical visit flow."""
    phone = "+50612345678"
    conversation_store.clear(phone)

    response = _handle_button_click(phone, "start_visit_flow")

    # Should start technical visit flow
    assert response.intent == Intent.TECHNICAL_VISIT
    assert "visita" in response.reply_text.lower()


def test_button_click_human_help():
    """Test that 'human_help' button triggers escalation."""
    phone = "+50612345678"
    conversation_store.clear(phone)

    response = _handle_button_click(phone, "human_help")

    # Should escalate to human
    assert response.intent == Intent.ESCALATE
    assert response.escalated is True
    assert response.escalation is not None


def test_unknown_button_id():
    """Test that unknown button IDs are handled gracefully."""
    phone = "+50612345678"
    conversation_store.clear(phone)

    response = _handle_button_click(phone, "unknown_button")

    # Should return unknown intent response
    assert response.intent == Intent.UNKNOWN


def test_handle_message_with_button_id():
    """Test that handle_message uses button_id when present."""
    phone = "+50612345678"
    conversation_store.clear(phone)

    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="Menu principal",  # Text doesn't matter when button_id is present
        button_id="go_main_menu",
        button_title="🏠 Menú principal",
        timestamp="2024-01-01T00:00:00",
    )

    response = handle_message(msg)

    # Should use button_id, not text classification
    assert response.intent == Intent.GREETING


def test_hydrate_flow_skips_completed_flows():
    """Test that hydrate_flow does not revive completed flows."""
    from src.services.persistence_service import hydrate_flow
    from src.db.database import get_db
    from src.db import repositories as repo
    import json

    phone = "+50612345678"
    conversation_store.clear(phone)

    # Create a snapshot with completed status
    db = get_db()
    try:
        repo.upsert_snapshot(
            db,
            phone_number=phone,
            current_intent="quote_request",
            flow_type="quote",
            flow_status="completed",  # This is the key
            collected_fields={"provincia": "San José", "zona": "Escazú"},
            missing_fields=[],
            needs_human=False,
        )
        db.commit()

        # Try to hydrate - should skip because flow is completed
        hydrate_flow(phone)

        # Flow should NOT be revived in memory
        flow = conversation_store.get_flow(phone)
        assert flow.flow_type is None or flow.flow_type == "", "Flow should not be revived when completed"
        assert len(flow.collected) == 0, "Collected fields should not be restored when completed"
    finally:
        db.close()
        # Cleanup
        db = get_db()
        try:
            snap = repo.get_snapshot_by_phone(db, phone)
            if snap:
                db.delete(snap)
                db.commit()
        finally:
            db.close()


def test_persist_outbound_sets_completed_status():
    """Test that persist_outbound sets flow_status to completed when no missing fields."""
    from src.services.persistence_service import persist_outbound
    from src.db.database import get_db
    from src.db import repositories as repo
    from src.schemas.chatbot import BotResponse

    phone = "+50612345678"
    conversation_store.clear(phone)

    # Set up a completed flow in memory
    conversation_store.set_flow(phone, "quote")
    flow = conversation_store.get_flow(phone)
    flow.merge({"provincia": "San José", "zona": "Escazú", "necesidad": "calor", "fotografias": "recibidas"})
    flow.no_measurements = True  # All fields collected

    # Create a response that would trigger escalation
    from src.services.escalation_service import build_escalation_payload
    escalation = build_escalation_payload(
        Intent.QUOTE_REQUEST, flow, summary="Cotización lista"
    )

    response = BotResponse(
        phone_number=phone,
        reply_text="Cotización lista para seguimiento",
        intent=Intent.QUOTE_REQUEST,
        escalated=True,
        escalation=escalation,
        buttons=[],
    )

    # Persist
    persist_outbound(response)

    # Check that snapshot has completed status
    db = get_db()
    try:
        snap = repo.get_snapshot_by_phone(db, phone)
        assert snap is not None, "Snapshot should exist"
        assert snap.flow_status == "completed", f"Flow status should be completed, got {snap.flow_status}"
    finally:
        db.close()
        # Cleanup
        db = get_db()
        try:
            snap = repo.get_snapshot_by_phone(db, phone)
            if snap:
                db.delete(snap)
                db.commit()
        finally:
            db.close()
        conversation_store.clear(phone)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
