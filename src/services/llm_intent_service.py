"""
LLM-based intent classification as an alternative to keyword-based classification.
Falls back to keyword classification if LLM is not configured or fails.
"""

import logging
from typing import Optional

from src.core.config import settings
from src.core.constants import Intent

logger = logging.getLogger(__name__)

# Intent descriptions for LLM classification
INTENT_DESCRIPTIONS = {
    Intent.GREETING: "Saludo inicial del usuario (hola, buenos días, etc.)",
    Intent.FAQ: "Pregunta frecuente sobre productos, garantías, instalación, etc.",
    Intent.PRODUCT_INFO: "Solicitud de información sobre productos, catálogo, especificaciones",
    Intent.QUOTE_REQUEST: "Solicitud de cotización o presupuesto",
    Intent.APPOINTMENT: "Solicitud de cita o visita técnica",
    Intent.TECHNICAL_VISIT: "Solicitud específica de visita técnica",
    Intent.COMPETITOR: "Mención de competidores o comparación con otras marcas",
    Intent.DISCOUNT: "Solicitud de descuentos, promociones o precios más bajos",
    Intent.WARRANTY_CLAIM: "Reclamo de garantía o problema con el producto instalado",
    Intent.PENDING_QUERY: "Consulta pendiente de confirmación",
    Intent.ESCALATE: "Solicitud explícita de hablar con un asesor humano",
    Intent.UNKNOWN: "Mensaje que no encaja en ninguna categoría anterior",
}

INTENT_LIST = "\n".join(
    f"- {intent.value}: {description}"
    for intent, description in INTENT_DESCRIPTIONS.items()
)

CLASSIFICATION_PROMPT = f"""Clasifica el siguiente mensaje del usuario en una de estas categorías de intent:

{INTENT_LIST}

Mensaje del usuario: "{{user_message}}"

Responde SOLO con el nombre exacto del intent (ej: greeting, faq, product_info, quote_request, etc.)."""


def classify_intent_with_llm(user_message: str) -> Optional[Intent]:
    """
    Classify user intent using LLM. Returns None if LLM is not configured or fails.
    """
    # Check if LLM is configured
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        logger.debug("OpenAI API key not configured, skipping LLM classification")
        return None
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        logger.debug("Anthropic API key not configured, skipping LLM classification")
        return None

    try:
        if settings.llm_provider == "openai":
            return _classify_with_openai(user_message)
        elif settings.llm_provider == "anthropic":
            return _classify_with_anthropic(user_message)
        else:
            logger.warning(f"Unknown LLM provider: {settings.llm_provider}")
            return None
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return None


def _classify_with_openai(user_message: str) -> Optional[Intent]:
    """Classify intent using OpenAI API."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        prompt = CLASSIFICATION_PROMPT.format(user_message=user_message)

        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "Eres un clasificador de intents para un chatbot de WhatsApp de Polaritech Window Film."},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.llm_temperature,
            max_tokens=50,
        )

        intent_str = response.choices[0].message.content.strip().lower()
        logger.info(f"LLM classified as: {intent_str}")

        # Map string to Intent enum
        for intent in Intent:
            if intent.value == intent_str:
                return intent

        logger.warning(f"Unknown intent from LLM: {intent_str}")
        return None
    except ImportError:
        logger.error("OpenAI library not installed. Run: pip install openai")
        return None
    except Exception as e:
        logger.error(f"OpenAI classification error: {e}")
        return None


def _classify_with_anthropic(user_message: str) -> Optional[Intent]:
    """Classify intent using Anthropic API."""
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)
        prompt = CLASSIFICATION_PROMPT.format(user_message=user_message)

        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=50,
            temperature=settings.llm_temperature,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        intent_str = response.content[0].text.strip().lower()
        logger.info(f"LLM classified as: {intent_str}")

        # Map string to Intent enum
        for intent in Intent:
            if intent.value == intent_str:
                return intent

        logger.warning(f"Unknown intent from LLM: {intent_str}")
        return None
    except ImportError:
        logger.error("Anthropic library not installed. Run: pip install anthropic")
        return None
    except Exception as e:
        logger.error(f"Anthropic classification error: {e}")
        return None
