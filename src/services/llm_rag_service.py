"""
RAG (Retrieval-Augmented Generation) service for rewriting KB responses using LLM.
The LLM is constrained to only use information from the KB content provided.
"""

import logging
from typing import Optional

from src.core.config import settings
from src.core.constants import Intent

logger = logging.getLogger(__name__)

# System prompt to enforce guardrails
RAG_SYSTEM_PROMPT = """Eres Valentina, asistente virtual de Polaritech Window Film. Tu tarea es reescribir la respuesta proporcionada para que sea más natural y amigable, PERO:

REGLAS ESTRICTAS:
1. SOLO puedes usar la información proporcionada en la "RESPUESTA BASE". No inventes datos.
2. NO menciones precios, garantías, especificaciones o fechas que no estén en la respuesta base.
3. NO hables negativamente de competidores.
4. NO prometas descuentos o fechas sin autorización.
5. Mantén el tono profesional pero cercano.
6. Si la respuesta base está vacía o no tiene información relevante, responde con la respuesta base tal cual.

Respuesta base: {{base_response}}

Contexto del intent: {{intent}}

Reescribe la respuesta de forma natural:"""


def rewrite_response_with_llm(
    base_response: str,
    intent: Intent,
) -> Optional[str]:
    """
    Rewrite a KB response using LLM to make it more natural.
    Returns None if LLM is not configured or fails.
    """
    # Check if LLM is configured
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        logger.debug("OpenAI API key not configured, skipping LLM rewrite")
        return None
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        logger.debug("Anthropic API key not configured, skipping LLM rewrite")
        return None

    # Skip if base response is empty or too short
    if not base_response or len(base_response.strip()) < 20:
        logger.debug("Base response too short, skipping LLM rewrite")
        return None

    try:
        if settings.llm_provider == "openai":
            return _rewrite_with_openai(base_response, intent)
        elif settings.llm_provider == "anthropic":
            return _rewrite_with_anthropic(base_response, intent)
        else:
            logger.warning(f"Unknown LLM provider: {settings.llm_provider}")
            return None
    except Exception as e:
        logger.error(f"LLM rewrite failed: {e}")
        return None


def _rewrite_with_openai(base_response: str, intent: Intent) -> Optional[str]:
    """Rewrite response using OpenAI API."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        prompt = RAG_SYSTEM_PROMPT.format(
            base_response=base_response,
            intent=intent.value,
        )

        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": base_response},
            ],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        rewritten = response.choices[0].message.content.strip()
        logger.info(f"LLM rewrote response (intent={intent.value})")
        return rewritten
    except ImportError:
        logger.error("OpenAI library not installed. Run: pip install openai")
        return None
    except Exception as e:
        logger.error(f"OpenAI rewrite error: {e}")
        return None


def _rewrite_with_anthropic(base_response: str, intent: Intent) -> Optional[str]:
    """Rewrite response using Anthropic API."""
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)
        prompt = RAG_SYSTEM_PROMPT.format(
            base_response=base_response,
            intent=intent.value,
        )

        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        rewritten = response.content[0].text.strip()
        logger.info(f"LLM rewrote response (intent={intent.value})")
        return rewritten
    except ImportError:
        logger.error("Anthropic library not installed. Run: pip install anthropic")
        return None
    except Exception as e:
        logger.error(f"Anthropic rewrite error: {e}")
        return None
