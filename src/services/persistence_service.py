"""
Persistence hooks — called alongside (never instead of) the chatbot pipeline.

All DB writes happen in a single session per event so they either all commit
or all roll back.  Failures are logged but never crash the bot.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.db.database import get_db
from src.db import repositories as repo
from src.schemas.chatbot import BotResponse, EscalationPayload, IncomingMessage
from src.state.conversation_store import conversation_store

logger = logging.getLogger(__name__)


def persist_inbound(
    msg: IncomingMessage,
    *,
    wa_message_id: Optional[str] = None,
    message_type: str = "text",
) -> None:
    """Upsert contact and log the inbound message."""
    try:
        db = get_db()
        try:
            repo.upsert_contact(db, msg.phone_number, msg.sender_name)
            repo.log_message(
                db,
                direction="inbound",
                phone_number=msg.phone_number,
                message_type=message_type,
                text=msg.text,
                wa_message_id=wa_message_id or msg.message_id,
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("persist_inbound failed for %s", msg.phone_number)


def persist_outbound(
    response: BotResponse,
    *,
    wa_message_id: Optional[str] = None,
) -> None:
    """Log the outbound message, sync snapshot, create lead/escalation if needed."""
    try:
        db = get_db()
        try:
            # Log outbound message
            repo.log_message(
                db,
                direction="outbound",
                phone_number=response.phone_number,
                message_type="text",
                text=response.reply_text,
                wa_message_id=wa_message_id,
                intent=response.intent.value,
            )

            # Sync conversation snapshot
            flow = conversation_store.get_flow(response.phone_number)
            collected = dict(flow.collected) if flow.flow_type else {}
            missing = _flow_missing(flow)

            repo.upsert_snapshot(
                db,
                phone_number=response.phone_number,
                current_intent=response.intent.value,
                flow_type=flow.flow_type or None,
                collected_fields=collected,
                missing_fields=missing,
                needs_human=response.escalated,
                last_bot_response=response.reply_text[:2000],
            )

            # Create lead on quote handoff
            if (
                response.escalated
                and response.escalation
                and response.intent.value == "quote_request"
            ):
                _create_lead_from_escalation(db, response)

            # Create escalation record for warranty/technical visit
            if response.escalated and response.escalation:
                intent_val = response.intent.value
                if intent_val in ("warranty_claim", "technical_visit"):
                    _create_escalation_record(db, response)

            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("persist_outbound failed for %s", response.phone_number)


def _create_lead_from_escalation(db, response: BotResponse) -> None:
    esc = response.escalation
    if not esc:
        return
    collected = esc.collected_fields or {}
    repo.upsert_lead(
        db,
        phone_number=response.phone_number,
        lead_type="quote",
        province=collected.get("provincia"),
        zone=collected.get("zona"),
        measurements=collected.get("medidas"),
        main_need=collected.get("necesidad"),
        product_interest=collected.get("producto"),
        has_photos=bool(collected.get("fotografias")),
    )


def _create_escalation_record(db, response: BotResponse) -> None:
    esc = response.escalation
    if not esc:
        return
    repo.create_escalation(
        db,
        phone_number=response.phone_number,
        intent=esc.intent.value,
        summary=esc.summary,
        collected_fields=esc.collected_fields,
        missing_fields=esc.missing_fields,
        priority=esc.priority,
    )


def _flow_missing(flow) -> list:
    """Get missing fields from in-memory flow state."""
    if flow.flow_type == "quote":
        return flow.quote_missing()
    if flow.flow_type == "warranty":
        return flow.warranty_missing()
    if flow.flow_type == "visit":
        return flow.visit_missing()
    return []
