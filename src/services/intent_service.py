"""
Keyword-based intent classifier.
Replace with an LLM call for richer understanding.
"""

from src.core.constants import Intent, INTENT_KEYWORDS


def classify_intent(text: str) -> Intent:
    normalised = text.lower().strip()

    # Priority order: escalation-type intents first, then specialised, then info
    priority_order = [
        Intent.ESCALATE,
        Intent.WARRANTY_CLAIM,
        Intent.TECHNICAL_VISIT,
        Intent.DISCOUNT,
        Intent.COMPETITOR,
        Intent.PENDING_QUERY,
        Intent.GREETING,
        Intent.QUOTE_REQUEST,
        Intent.APPOINTMENT,
        Intent.PRODUCT_INFO,
    ]

    for intent in priority_order:
        keywords = INTENT_KEYWORDS.get(intent, [])
        if any(kw in normalised for kw in keywords):
            return intent

    return Intent.UNKNOWN
