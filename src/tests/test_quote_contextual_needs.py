"""
Tests for quote flow contextual need detection and recommendations.
"""

import pytest
from src.schemas.chatbot import IncomingMessage
from src.services.response_service import handle_message
from src.state.conversation_store import conversation_store


def _create_message(phone: str, text: str, msg_id: str = "msg1") -> IncomingMessage:
    """Helper to create IncomingMessage with required timestamp."""
    return IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id=msg_id,
        text=text,
        timestamp="2024-01-01T00:00:00Z",
    )


def test_quote_flow_with_calor_need():
    """Test quote flow with 'calor' need generates Nano Cerámica recommendation."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Quiero una cotización", "msg1")
    response = handle_message(msg)
    assert "cotización" in response.reply_text.lower()
    
    # Respond with "calor"
    msg = _create_message(phone, "calor", "msg2")
    response = handle_message(msg)
    
    # Should contain Nano Cerámica recommendation
    assert "Nano Cerámica" in response.reply_text
    assert "reducir calor" in response.reply_text.lower()
    # Should ask for missing fields
    assert "necesito" in response.reply_text.lower()


def test_quote_flow_with_quiero_calor():
    """Test quote flow with 'quiero calor' need generates recommendation."""
    phone = "+50612345679"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Respond with "quiero calor"
    msg = _create_message(phone, "quiero calor", "msg2")
    response = handle_message(msg)
    
    # Should contain Nano Cerámica recommendation
    assert "Nano Cerámica" in response.reply_text
    assert "Perfecto" in response.reply_text


def test_quote_flow_with_privacidad_need():
    """Test quote flow with 'privacidad' need generates privacy recommendation."""
    phone = "+50612345680"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Necesito cotización", "msg1")
    response = handle_message(msg)
    
    # Respond with "privacidad"
    msg = _create_message(phone, "privacidad", "msg2")
    response = handle_message(msg)
    
    # Should contain privacy recommendation
    assert "privacidad diurna" in response.reply_text.lower()
    assert "Económica" in response.reply_text or "Silver Espejo" in response.reply_text
    assert "Sand Blasting" in response.reply_text


def test_quote_flow_with_seguridad_need():
    """Test quote flow with 'seguridad' need generates security recommendation."""
    phone = "+50612345681"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Respond with "seguridad"
    msg = _create_message(phone, "seguridad", "msg2")
    response = handle_message(msg)
    
    # Should contain security recommendation
    assert "Película de Seguridad" in response.reply_text
    assert "fragmentos" in response.reply_text.lower()


def test_quote_flow_with_decoracion_need():
    """Test quote flow with 'decoracion' need generates decoration recommendation."""
    phone = "+50612345682"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Respond with "decoracion"
    msg = _create_message(phone, "decoracion", "msg2")
    response = handle_message(msg)
    
    # Should contain decoration recommendation
    assert "Sand Blasting" in response.reply_text
    assert "vidrio esmerilado" in response.reply_text.lower()


def test_quote_flow_with_decoracion_tilde():
    """Test quote flow with 'decoración' (with tilde) need generates recommendation."""
    phone = "+50612345683"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Respond with "decoración"
    msg = _create_message(phone, "decoración", "msg2")
    response = handle_message(msg)
    
    # Should contain decoration recommendation
    assert "Sand Blasting" in response.reply_text


def test_quote_flow_with_busco_calor():
    """Test quote flow with 'busco calor' need generates recommendation."""
    phone = "+50612345684"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Respond with "busco calor"
    msg = _create_message(phone, "busco calor", "msg2")
    response = handle_message(msg)
    
    # Should contain Nano Cerámica recommendation
    assert "Nano Cerámica" in response.reply_text


def test_quote_flow_with_necesito_seguridad():
    """Test quote flow with 'necesito seguridad' need generates recommendation."""
    phone = "+50612345685"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Respond with "necesito seguridad"
    msg = _create_message(phone, "necesito seguridad", "msg2")
    response = handle_message(msg)
    
    # Should contain security recommendation
    assert "Película de Seguridad" in response.reply_text


def test_quote_flow_without_need_uses_generic_thanks():
    """Test quote flow without detected need uses generic thanks message."""
    phone = "+50612345686"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Respond with unrelated text (no need detected)
    msg = _create_message(phone, "San José, 2x2 metros", "msg2")
    response = handle_message(msg)
    
    # Should use generic thanks, not contextual recommendation
    assert "Gracias por la información" in response.reply_text
    assert "Perfecto" not in response.reply_text


def test_quote_flow_continues_after_recommendation():
    """Test quote flow continues asking for missing fields after recommendation."""
    phone = "+50612345687"
    conversation_store.clear(phone)
    
    # Start quote flow
    msg = _create_message(phone, "Cotizar", "msg1")
    response = handle_message(msg)
    
    # Respond with "calor"
    msg = _create_message(phone, "calor", "msg2")
    response = handle_message(msg)
    
    # Should still ask for missing fields
    assert "necesito" in response.reply_text.lower()
    # Should mention that we need more information
    assert "necesito" in response.reply_text.lower() or "necesita" in response.reply_text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
