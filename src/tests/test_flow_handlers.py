"""
Tests for flow-specific handlers (quote_no_measurements, visit + image, etc.)
"""

import pytest
from src.core.constants import QUOTE_NO_MEASUREMENTS, normalize_text, FLOW_TEXT_ALIASES
from src.schemas.chatbot import IncomingMessage
from src.services.response_service import handle_message, _handle_flow_button
from src.state.conversation_store import conversation_store


def test_quote_no_measurements_button():
    """Test that quote_no_measurements button sets no_measurements and continues flow."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Start quote flow
    conversation_store.set_flow(phone, "quote")
    flow = conversation_store.get_flow(phone)
    
    # Initially no_measurements should be False
    assert flow.no_measurements is False
    
    # Simulate clicking the button
    response = _handle_flow_button(phone, QUOTE_NO_MEASUREMENTS, flow)
    
    # no_measurements should now be True
    assert flow.no_measurements is True
    
    # Response should be from quote handler
    assert response.intent.value == "quote_request"


def test_quote_no_measurements_text():
    """Test that 'no tengo medidas' text sets no_measurements via flow text alias."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Start quote flow
    conversation_store.set_flow(phone, "quote")
    flow = conversation_store.get_flow(phone)
    
    # Initially no_measurements should be False
    assert flow.no_measurements is False
    
    # Send text "no tengo medidas"
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="no tengo medidas",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # no_measurements should now be True
    assert flow.no_measurements is True
    
    # Response should be from quote handler
    assert response.intent.value == "quote_request"


def test_quote_no_se_las_medidas_text():
    """Test that 'no se las medidas' text sets no_measurements via flow text alias."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Start quote flow
    conversation_store.set_flow(phone, "quote")
    flow = conversation_store.get_flow(phone)
    
    # Send text "no se las medidas"
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="no se las medidas",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # no_measurements should now be True
    assert flow.no_measurements is True


def test_quote_sin_medidas_text():
    """Test that 'sin medidas' text sets no_measurements via flow text alias."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Start quote flow
    conversation_store.set_flow(phone, "quote")
    flow = conversation_store.get_flow(phone)
    
    # Send text "sin medidas"
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="sin medidas",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # no_measurements should now be True
    assert flow.no_measurements is True


def test_quote_no_measurements_only_in_active_quote_flow():
    """Test that no_measurements only triggers when in active quote flow."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Don't start quote flow - should be idle
    flow = conversation_store.get_flow(phone)
    assert flow.flow_type is None or flow.flow_type == ""
    
    # Send text "no tengo medidas"
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="no tengo medidas",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should NOT set no_measurements (no active flow)
    # Should go through normal intent resolution
    assert flow.no_measurements is False


def test_flow_text_aliases_normalization():
    """Test that flow text aliases work with normalized text."""
    # Test with tildes
    assert normalize_text("No tengo medidas") in FLOW_TEXT_ALIASES
    assert FLOW_TEXT_ALIASES[normalize_text("No tengo medidas")] == "no_measurements"
    
    # Test without tildes
    assert normalize_text("no tengo medidas") in FLOW_TEXT_ALIASES
    
    # Test with extra spaces
    assert normalize_text("  no tengo medidas  ") in FLOW_TEXT_ALIASES


def test_visit_flow_image_handling():
    """Test that image in visit flow marks fotografias and continues flow."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Start visit flow
    conversation_store.set_flow(phone, "visit")
    flow = conversation_store.get_flow(phone)
    
    # Initially fotografias should not be set
    assert "fotografias" not in flow.collected
    
    # Simulate image handling in webhook
    # This is tested at the webhook level, but we can verify the flow state
    flow.merge({"fotografias": "recibidas"})
    
    # fotografias should now be set
    assert flow.collected["fotografias"] == "recibidas"


def test_visit_flow_image_continues_flow():
    """Test that image in visit flow continues asking for missing fields."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Start visit flow
    conversation_store.set_flow(phone, "visit")
    flow = conversation_store.get_flow(phone)
    
    # Mark fotografias as received
    flow.merge({"fotografias": "recibidas"})
    
    # Send a message to continue the flow
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="San José",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should continue visit flow
    assert response.intent.value == "technical_visit"
    
    # Should still have fotografias in collected
    assert flow.collected.get("fotografias") == "recibidas"


def test_quote_flow_with_button_id():
    """Test that quote_no_measurements button ID is handled correctly."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Start quote flow
    conversation_store.set_flow(phone, "quote")
    flow = conversation_store.get_flow(phone)
    
    # Send message with button_id
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="No tengo medidas",
        button_id=QUOTE_NO_MEASUREMENTS,
        button_title="No tengo medidas",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # no_measurements should be set
    assert flow.no_measurements is True
    
    # Should not fall through to fallback
    assert response.intent.value != "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
