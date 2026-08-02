"""
Tests for LLM integration (intent classification and response rewriting).
Tests verify that LLM services work when configured and fallback gracefully when not.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.core.config import settings
from src.core.constants import Intent
from src.services.llm_intent_service import classify_intent_with_llm
from src.services.llm_rag_service import rewrite_response_with_llm


class TestLLMIntentClassification:
    """Test LLM-based intent classification."""

    def test_no_api_key_returns_none(self):
        """When API key is not configured, should return None (fallback to keywords)."""
        with patch.object(settings, "openai_api_key", ""):
            result = classify_intent_with_llm("Hola, quisiera información")
            assert result is None

    def test_no_anthropic_api_key_returns_none(self):
        """When Anthropic API key is not configured, should return None."""
        with patch.object(settings, "llm_provider", "anthropic"):
            with patch.object(settings, "anthropic_api_key", ""):
                result = classify_intent_with_llm("Hola, quisiera información")
                assert result is None

    def test_unknown_provider_returns_none(self):
        """When LLM provider is unknown, should return None."""
        with patch.object(settings, "llm_provider", "unknown"):
            with patch.object(settings, "openai_api_key", "test_key"):
                result = classify_intent_with_llm("Hola")
                assert result is None


class TestLLMRAGService:
    """Test LLM-based response rewriting."""

    def test_no_api_key_returns_none(self):
        """When API key is not configured, should return None (use original response)."""
        with patch.object(settings, "openai_api_key", ""):
            result = rewrite_response_with_llm("Respuesta base", Intent.FAQ)
            assert result is None

    def test_short_response_skips_rewrite(self):
        """When base response is too short, should skip LLM rewrite."""
        with patch.object(settings, "openai_api_key", "test_key"):
            result = rewrite_response_with_llm("Hola", Intent.GREETING)
            assert result is None

    def test_empty_response_skips_rewrite(self):
        """When base response is empty, should skip LLM rewrite."""
        with patch.object(settings, "openai_api_key", "test_key"):
            result = rewrite_response_with_llm("", Intent.FAQ)
            assert result is None

    def test_unknown_provider_returns_none(self):
        """When LLM provider is unknown, should return None."""
        with patch.object(settings, "llm_provider", "unknown"):
            with patch.object(settings, "openai_api_key", "test_key"):
                result = rewrite_response_with_llm("Respuesta base", Intent.FAQ)
                assert result is None


class TestHybridClassification:
    """Test hybrid classification (LLM with keyword fallback)."""

    def test_hybrid_classification_fallback_to_keywords(self):
        """When LLM returns None, should fallback to keyword classification."""
        from src.services.response_service import _classify_intent_hybrid

        with patch("src.services.response_service.classify_intent_with_llm", return_value=None):
            result = _classify_intent_hybrid("Información de productos")
            # Should fallback to keyword classification
            assert result == Intent.PRODUCT_INFO

    def test_hybrid_classification_uses_llm_when_available(self):
        """When LLM returns valid intent, should use it."""
        from src.services.response_service import _classify_intent_hybrid

        with patch("src.services.response_service.classify_intent_with_llm", return_value=Intent.GREETING):
            result = _classify_intent_hybrid("Hola")
            assert result == Intent.GREETING
