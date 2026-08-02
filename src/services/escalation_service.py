"""
Determines whether a conversation should be handed off to a human agent
and builds structured escalation metadata.

Escalation triggers (from source docs):
  - Explicit request by user
  - Warranty claims  (priority: high)
  - Technical visits (priority: normal)
  - Quote handoff    (priority: normal)
  - Undocumented / unconfirmed cases
  - Max-turn threshold exceeded
"""

import logging
from typing import Dict, List

from src.core.constants import ALWAYS_ESCALATE_INTENTS, Intent, MAX_TURNS_BEFORE_ESCALATION
from src.schemas.chatbot import EscalationPayload
from src.state.conversation_store import FlowState, conversation_store

logger = logging.getLogger(__name__)

# Intents that receive high-priority escalation
_HIGH_PRIORITY_INTENTS = frozenset({Intent.WARRANTY_CLAIM})


def should_escalate(
    phone: str,
    intent: Intent,
    explicit_request: bool = False,
) -> bool:
    if explicit_request:
        logger.info("Escalation requested explicitly by %s", phone)
        return True

    if intent in ALWAYS_ESCALATE_INTENTS:
        logger.info("Auto-escalation for intent %s from %s", intent, phone)
        return True

    turns = conversation_store.turn_count(phone)
    if turns >= MAX_TURNS_BEFORE_ESCALATION:
        logger.info("Auto-escalation triggered for %s after %d turns", phone, turns)
        return True

    return False


def build_escalation_payload(
    intent: Intent,
    flow: FlowState,
    summary: str = "",
) -> EscalationPayload:
    """Build a structured payload for the human agent receiving the handoff."""
    priority = "high" if intent in _HIGH_PRIORITY_INTENTS else "normal"

    if flow.flow_type == "quote":
        missing = flow.quote_missing()
    elif flow.flow_type == "warranty":
        missing = flow.warranty_missing()
    elif flow.flow_type == "visit":
        missing = flow.visit_missing()
    else:
        missing = []

    return EscalationPayload(
        intent=intent,
        summary=summary or f"Escalación automática — {intent.value}",
        collected_fields=dict(flow.collected),
        missing_fields=missing,
        priority=priority,
    )
