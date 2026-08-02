"""
Tests for unified intent routing to ensure menu buttons and text aliases work correctly.
"""

import pytest
from src.core.constants import normalize_text, TEXT_ALIASES, BUTTON_ID_TO_INTENT, Intent
from src.schemas.chatbot import IncomingMessage
from src.services.response_service import handle_message, _resolve_intent_unified
from src.state.conversation_store import conversation_store


def test_normalize_text():
    """Test text normalization: lowercase, remove accents, trim, collapse spaces."""
    assert normalize_text("Cotización") == "cotizacion"
    assert normalize_text("  Cotización  ") == "cotizacion"
    assert normalize_text("Cotización  con  espacios") == "cotizacion con espacios"
    assert normalize_text("ÁÉÍÓÚ") == "aeiou"
    assert normalize_text("áéíóú") == "aeiou"
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


def test_text_aliases_quote():
    """Test that quote text aliases map correctly."""
    assert normalize_text("Cotización") in TEXT_ALIASES
    assert TEXT_ALIASES[normalize_text("Cotización")] == Intent.QUOTE_REQUEST
    assert TEXT_ALIASES[normalize_text("cotizacion")] == Intent.QUOTE_REQUEST
    assert TEXT_ALIASES[normalize_text("presupuesto")] == Intent.QUOTE_REQUEST
    assert TEXT_ALIASES[normalize_text("cotizar")] == Intent.QUOTE_REQUEST


def test_text_aliases_products():
    """Test that product info text aliases map correctly."""
    assert normalize_text("productos") in TEXT_ALIASES
    assert TEXT_ALIASES[normalize_text("productos")] == Intent.PRODUCT_INFO
    assert TEXT_ALIASES[normalize_text("info de productos")] == Intent.PRODUCT_INFO
    assert TEXT_ALIASES[normalize_text("laminas")] == Intent.PRODUCT_INFO


def test_text_aliases_visit():
    """Test that visit text aliases map correctly."""
    assert normalize_text("agendar visita") in TEXT_ALIASES
    assert TEXT_ALIASES[normalize_text("agendar visita")] == Intent.TECHNICAL_VISIT
    assert TEXT_ALIASES[normalize_text("visita tecnica")] == Intent.TECHNICAL_VISIT
    assert TEXT_ALIASES[normalize_text("visita")] == Intent.TECHNICAL_VISIT


def test_text_aliases_human():
    """Test that human/escalation text aliases map correctly."""
    assert normalize_text("asesor") in TEXT_ALIASES
    assert TEXT_ALIASES[normalize_text("asesor")] == Intent.ESCALATE
    assert TEXT_ALIASES[normalize_text("hablar con asesor")] == Intent.ESCALATE


def test_button_id_mapping():
    """Test that button IDs map directly to intents."""
    from src.core.constants import MENU_ID_QUOTE, MENU_ID_PRODUCTS, MENU_ID_VISIT, MENU_ID_HUMAN
    
    assert BUTTON_ID_TO_INTENT[MENU_ID_QUOTE] == Intent.QUOTE_REQUEST
    assert BUTTON_ID_TO_INTENT[MENU_ID_PRODUCTS] == Intent.PRODUCT_INFO
    assert BUTTON_ID_TO_INTENT[MENU_ID_VISIT] == Intent.TECHNICAL_VISIT
    assert BUTTON_ID_TO_INTENT[MENU_ID_HUMAN] == Intent.ESCALATE


def test_unified_resolver_button_id_priority():
    """Test that button_id takes priority over text classification."""
    from src.core.constants import MENU_ID_QUOTE
    
    # button_id should override any text
    intent = _resolve_intent_unified("random text", button_id=MENU_ID_QUOTE)
    assert intent == Intent.QUOTE_REQUEST


def test_unified_resolver_text_alias_priority():
    """Test that text aliases take priority over LLM/keywords."""
    intent = _resolve_intent_unified("Cotización")
    assert intent == Intent.QUOTE_REQUEST
    
    intent = _resolve_intent_unified("cotizacion")
    assert intent == Intent.QUOTE_REQUEST
    
    intent = _resolve_intent_unified("presupuesto")
    assert intent == Intent.QUOTE_REQUEST


def test_handle_message_with_quote_button():
    """Test that clicking the Quote button starts quote flow."""
    from src.core.constants import MENU_ID_QUOTE
    
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="Quiero solicitar una cotización",
        button_id=MENU_ID_QUOTE,
        button_title="Cotización",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should start quote flow
    assert response.intent == Intent.QUOTE_REQUEST
    assert "cotización" in response.reply_text.lower() or "información" in response.reply_text.lower()


def test_handle_message_with_quote_text():
    """Test that typing 'Cotización' (with tilde) starts quote flow."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="Cotización",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should start quote flow via text alias
    assert response.intent == Intent.QUOTE_REQUEST


def test_handle_message_with_quote_text_no_tilde():
    """Test that typing 'cotizacion' (no tilde) starts quote flow."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="cotizacion",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should start quote flow via text alias
    assert response.intent == Intent.QUOTE_REQUEST


def test_handle_message_with_presupuesto():
    """Test that typing 'presupuesto' starts quote flow."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="presupuesto",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should start quote flow via text alias
    assert response.intent == Intent.QUOTE_REQUEST


def test_handle_message_with_visit_button():
    """Test that clicking the Visit button starts visit flow."""
    from src.core.constants import MENU_ID_VISIT
    
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="Necesito una visita técnica",
        button_id=MENU_ID_VISIT,
        button_title="Agendar visita",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should start visit flow
    assert response.intent == Intent.TECHNICAL_VISIT


def test_handle_message_with_products_button():
    """Test that clicking the Products button shows product info."""
    from src.core.constants import MENU_ID_PRODUCTS
    
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="Información de productos",
        button_id=MENU_ID_PRODUCTS,
        button_title="Info de productos",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should show product info
    assert response.intent == Intent.PRODUCT_INFO


def test_handle_message_with_human_button():
    """Test that clicking the Human button triggers escalation."""
    from src.core.constants import MENU_ID_HUMAN
    
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="asesor",
        button_id=MENU_ID_HUMAN,
        button_title="Hablar con asesor",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # Should trigger escalation
    assert response.intent == Intent.ESCALATE
    assert response.escalated is True


def test_fallback_only_when_no_match():
    """Test that fallback only triggers when there's no match at all."""
    phone = "+50612345678"
    conversation_store.clear(phone)
    
    # This should not match any alias and should fall through to classifier
    # The key is that it shouldn't incorrectly match "Cotización" or other aliases
    msg = IncomingMessage(
        phone_number=phone,
        sender_name="Test User",
        message_id="msg1",
        text="xyz completely random text that matches nothing",
        timestamp="2024-01-01T00:00:00",
    )
    
    response = handle_message(msg)
    
    # The key assertion: it should NOT match quote/product/visit via aliases
    # It may match greeting, FAQ, or UNKNOWN depending on classifier
    assert response.intent not in (Intent.QUOTE_REQUEST, Intent.PRODUCT_INFO, Intent.TECHNICAL_VISIT, Intent.ESCALATE)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
