"""
Tests for intent classification bug fix.
Verifies that common text doesn't incorrectly trigger TECHNICAL_VISIT.
"""

import pytest
from src.schemas.chatbot import IncomingMessage
from src.services.response_service import handle_message
from src.state.conversation_store import conversation_store
from src.core.constants import Intent


def _create_message(phone: str, text: str, msg_id: str = "msg1") -> IncomingMessage:
    """Helper to create IncomingMessage with required timestamp."""
    return IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id=msg_id,
        text=text,
        timestamp="2024-01-01T00:00:00Z",
    )


def test_no_active_flow_product_text_resolves_to_product_info():
    """Test that product text without active flow resolves to PRODUCT_INFO, not TECHNICAL_VISIT."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    msg = _create_message(phone, "Estoy buscando láminas para el calor")
    response = handle_message(msg)
    
    # Should resolve to PRODUCT_INFO, not TECHNICAL_VISIT
    assert response.intent == Intent.PRODUCT_INFO
    assert response.intent != Intent.TECHNICAL_VISIT


def test_no_active_flow_privacy_text_resolves_to_product_info():
    """Test that privacy text without active flow resolves to PRODUCT_INFO, not TECHNICAL_VISIT."""
    phone = "+50612345679"
    conversation_store.clear(phone)
    
    msg = _create_message(phone, "quiero privacidad")
    response = handle_message(msg)
    
    # Should resolve to PRODUCT_INFO, not TECHNICAL_VISIT
    assert response.intent == Intent.PRODUCT_INFO
    assert response.intent != Intent.TECHNICAL_VISIT


def test_no_active_flow_security_text_resolves_to_product_info():
    """Test that security text without active flow resolves to PRODUCT_INFO or FAQ, not TECHNICAL_VISIT."""
    phone = "+50612345680"
    conversation_store.clear(phone)
    
    msg = _create_message(phone, "busco seguridad")
    response = handle_message(msg)
    
    # Should resolve to PRODUCT_INFO or FAQ, not TECHNICAL_VISIT
    assert response.intent in (Intent.PRODUCT_INFO, Intent.FAQ)
    assert response.intent != Intent.TECHNICAL_VISIT


def test_active_quote_flow_product_text_continues_quote():
    """Test that product text in active quote flow continues quote flow with recommendation."""
    phone = "+50612345681"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    assert response.intent == Intent.QUOTE_REQUEST
    
    # Send product text
    msg = _create_message(phone, "Estoy buscando láminas para el calor", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow, not switch to TECHNICAL_VISIT
    assert response.intent == Intent.QUOTE_REQUEST
    assert response.intent != Intent.TECHNICAL_VISIT
    # Should contain Nano Cerámica recommendation
    assert "Nano Cerámica" in response.reply_text


def test_active_quote_flow_location_fills_fields():
    """Test that location text in active quote flow fills province and zone."""
    phone = "+50612345682"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send location text
    msg = _create_message(phone, "San José, Curridabat", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow
    assert response.intent == Intent.QUOTE_REQUEST
    assert response.intent != Intent.TECHNICAL_VISIT


def test_active_quote_flow_no_measurements_continues_quote():
    """Test that 'no tengo medidas' in active quote flow continues quote flow."""
    phone = "+50612345683"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send no measurements text
    msg = _create_message(phone, "No tengo medidas", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow, not switch to TECHNICAL_VISIT
    assert response.intent == Intent.QUOTE_REQUEST
    assert response.intent != Intent.TECHNICAL_VISIT


def test_active_quote_flow_no_photos_continues_quote():
    """Test that 'no tengo fotos' in active quote flow continues quote flow or FAQ, not TECHNICAL_VISIT."""
    phone = "+50612345684"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send no photos text
    msg = _create_message(phone, "No tengo fotos", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow or FAQ, not switch to TECHNICAL_VISIT
    assert response.intent in (Intent.QUOTE_REQUEST, Intent.FAQ)
    assert response.intent != Intent.TECHNICAL_VISIT


def test_active_quote_flow_multiple_needs_recommendations():
    """Test that 'calor y privacidad' in active quote flow generates combined recommendations."""
    phone = "+50612345685"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send multiple needs text
    msg = _create_message(phone, "Calor y privacidad", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow, not switch to TECHNICAL_VISIT
    assert response.intent == Intent.QUOTE_REQUEST
    assert response.intent != Intent.TECHNICAL_VISIT
    # Should contain recommendations for both needs
    assert "Nano Cerámica" in response.reply_text or "privacidad" in response.reply_text.lower()


def test_explicit_visit_language_triggers_technical_visit():
    """Test that explicit visit language still triggers TECHNICAL_VISIT."""
    phone = "+50612345686"
    conversation_store.clear(phone)
    
    msg = _create_message(phone, "Quiero agendar una visita técnica")
    response = handle_message(msg)
    
    # Should resolve to TECHNICAL_VISIT
    assert response.intent == Intent.TECHNICAL_VISIT


def test_active_quote_flow_explicit_visit_language_allows_visit():
    """Test that explicit visit language in active quote flow allows switching to TECHNICAL_VISIT."""
    phone = "+50612345687"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send explicit visit language
    msg = _create_message(phone, "Necesito que revisen en sitio", "msg2")
    response = handle_message(msg)
    
    # Should allow switch to TECHNICAL_VISIT
    assert response.intent == Intent.TECHNICAL_VISIT


def test_active_quote_flow_common_text_does_not_trigger_visit():
    """Test that common text in active quote flow does NOT trigger TECHNICAL_VISIT."""
    phone = "+50612345688"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send common text that might have triggered visit before
    msg = _create_message(phone, "No tengo fotos", "msg2")
    response = handle_message(msg)
    
    # Should NOT switch to TECHNICAL_VISIT (may be QUOTE_REQUEST or FAQ)
    assert response.intent != Intent.TECHNICAL_VISIT


def test_active_quote_flow_location_fills_province_and_zone():
    """Test that 'San José, Curridabat' in active quote flow fills province and zone."""
    phone = "+50612345689"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send location text
    msg = _create_message(phone, "San José, Curridabat", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow
    assert response.intent == Intent.QUOTE_REQUEST
    # Check that province and zone were filled
    flow = conversation_store.get_flow(phone)
    assert "provincia" in flow.collected or "zona" in flow.collected


def test_active_quote_flow_multiple_needs_combined_recommendations():
    """Test that 'calor y privacidad' in active quote flow generates combined recommendations."""
    phone = "+50612345690"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send multiple needs text
    msg = _create_message(phone, "calor y privacidad", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow
    assert response.intent == Intent.QUOTE_REQUEST
    # Should contain recommendations for both needs
    assert "Nano Cerámica" in response.reply_text
    assert "privacidad" in response.reply_text.lower()


def test_active_quote_flow_no_photos_continues_quote():
    """Test that 'no tengo fotos' in active quote flow continues quote flow."""
    phone = "+50612345691"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send no photos text
    msg = _create_message(phone, "no tengo fotos", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow
    assert response.intent == Intent.QUOTE_REQUEST
    # Check that photos status was set
    flow = conversation_store.get_flow(phone)
    assert flow.collected.get("fotografias") == "missing"


def test_active_quote_flow_no_measurements_continues_quote():
    """Test that 'no tengo medidas' in active quote flow continues quote flow."""
    phone = "+50612345692"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send no measurements text
    msg = _create_message(phone, "no tengo medidas", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow
    assert response.intent == Intent.QUOTE_REQUEST
    # Check that no_measurements flag was set
    flow = conversation_store.get_flow(phone)
    assert flow.no_measurements is True


def test_active_quote_flow_product_text_continues_quote_no_visit():
    """Test that 'estoy buscando láminas para el calor' in active quote flow continues quote, not technical_visit."""
    phone = "+50612345693"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Send product text
    msg = _create_message(phone, "estoy buscando láminas para el calor", "msg2")
    response = handle_message(msg)
    
    # Should continue in quote flow, NOT switch to TECHNICAL_VISIT
    assert response.intent == Intent.QUOTE_REQUEST
    assert response.intent != Intent.TECHNICAL_VISIT
    # Should contain Nano Cerámica recommendation
    assert "Nano Cerámica" in response.reply_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
