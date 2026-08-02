"""
WhatsApp Cloud API webhook endpoints:
  GET  /webhook  — verification handshake
  POST /webhook  — incoming message processing

Production-safe:
  - Structured logging for every inbound message, intent, and outbound result
  - Idempotency guard prevents duplicate replies on webhook retries
  - Unsupported message types get a safe Spanish fallback
  - Outbound failures are logged but never crash the server
"""

import logging
from typing import Dict

from fastapi import APIRouter, Query, Request, Response

from src.core.config import settings
from src.schemas.chatbot import IncomingMessage
from src.schemas.whatsapp import WhatsAppMessage, WhatsAppWebhookPayload
from src.db.database import get_db
from src.db import repositories as repo
from src.services.persistence_service import persist_inbound, persist_outbound
from src.services.response_service import handle_message
from src.services.welcome_service import maybe_send_welcome
from src.services.whatsapp_service import whatsapp_client
from src.state.idempotency_store import idempotency_store

logger = logging.getLogger(__name__)

router = APIRouter()

_UNSUPPORTED_TYPE_REPLY = (
    "Por el momento solo puedo procesar mensajes de texto. "
    "Por favor, envíe su consulta como texto y con gusto le atiendo."
)


# ── GET /webhook — Meta verification handshake ───────────────────────────────

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> Response:
    """Meta sends a GET request to verify ownership of the webhook URL."""
    if (
        hub_mode == "subscribe"
        and hub_verify_token
        and hub_verify_token == settings.whatsapp_verify_token
    ):
        logger.info("Webhook verified successfully")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("Webhook verification failed — token mismatch")
    return Response(content="Forbidden", status_code=403)


# ── POST /webhook — inbound message processing ──────────────────────────────

@router.post("/webhook")
async def receive_message(request: Request) -> dict:
    """Process inbound WhatsApp webhook events."""
    body = await request.json()

    try:
        payload = WhatsAppWebhookPayload.model_validate(body)
    except Exception:
        logger.exception("Failed to parse webhook payload")
        return {"status": "error", "detail": "invalid payload"}

    for entry in payload.entry:
        for change in entry.changes:
            value = change.value

            # ── Log statuses (delivery receipts) but don't process ────
            if value.statuses:
                for st in value.statuses:
                    logger.debug(
                        "status_update  msg_id=%s  status=%s  recipient=%s",
                        st.id, st.status, st.recipient_id,
                    )

            if not value.messages:
                continue

            contacts = value.contacts or []
            contact_map: Dict[str, str] = {
                c.wa_id: c.profile.name for c in contacts
            }

            for wa_msg in value.messages:
                await _process_message(wa_msg, contact_map)

    return {"status": "ok"}


async def _process_message(
    wa_msg: WhatsAppMessage,
    contact_map: Dict[str, str],
) -> None:
    """Route a single inbound WhatsApp message through the pipeline."""
    msg_id = wa_msg.id
    sender = wa_msg.from_
    sender_name = contact_map.get(sender, "Unknown")

    # ── Idempotency guard ────────────────────────────────────────────
    if idempotency_store.is_seen(msg_id):
        logger.info("inbound_duplicate  msg_id=%s  sender=%s  — skipped", msg_id, sender)
        return
    idempotency_store.mark_seen(msg_id)

    # ── Interactive replies (button/list taps) ───────────────────────
    if wa_msg.type == "interactive" and wa_msg.interactive:
        reply_text = ""
        reply_id = ""
        if wa_msg.interactive.button_reply:
            reply_text = wa_msg.interactive.button_reply.title
            reply_id = wa_msg.interactive.button_reply.id
        elif wa_msg.interactive.list_reply:
            reply_text = wa_msg.interactive.list_reply.title
            reply_id = wa_msg.interactive.list_reply.id

        logger.info(
            "inbound_interactive  msg_id=%s  sender=%s  reply_id=%s  title=%s",
            msg_id, sender, reply_id, reply_text,
        )

        # Map button IDs to natural language text for the pipeline
        button_text_map = {
            "menu_productos": "Información de productos",
            "menu_cotizacion": "Quiero solicitar una cotización",
            "menu_visita": "Necesito una visita técnica",
        }
        text_for_pipeline = button_text_map.get(reply_id, reply_text)

        incoming = IncomingMessage(
            phone_number=sender,
            sender_name=sender_name,
            message_id=msg_id,
            text=text_for_pipeline,
            timestamp=wa_msg.timestamp,
        )

        persist_inbound(incoming, wa_message_id=msg_id)

        if _is_human_takeover(sender):
            logger.info("bot_paused  msg_id=%s  sender=%s  reason=human_takeover", msg_id, sender)
            return

        bot_response = handle_message(incoming)
        result = await whatsapp_client.send_text(
            bot_response.phone_number, bot_response.reply_text,
        )
        persist_outbound(bot_response, wa_message_id=result.message_id or None)
        return

    # ── Text messages — main pipeline ────────────────────────────────
    if wa_msg.type == "text" and wa_msg.text:
        logger.info(
            "inbound_text  msg_id=%s  sender=%s  name=%s  text=%s",
            msg_id, sender, sender_name, wa_msg.text.body[:120],
        )

        incoming = IncomingMessage(
            phone_number=sender,
            sender_name=sender_name,
            message_id=msg_id,
            text=wa_msg.text.body,
            timestamp=wa_msg.timestamp,
        )

        # ── Welcome flow for new conversations ────────────────────────
        await maybe_send_welcome(sender, sender_name)

        persist_inbound(incoming, wa_message_id=msg_id)

        # ── Human takeover guard ─────────────────────────────────────
        if _is_human_takeover(sender):
            logger.info(
                "bot_paused  msg_id=%s  sender=%s  reason=human_takeover",
                msg_id, sender,
            )
            return

        bot_response = handle_message(incoming)

        logger.info(
            "outbound_intent  msg_id=%s  intent=%s  escalated=%s",
            msg_id, bot_response.intent.value, bot_response.escalated,
        )

        result = await whatsapp_client.send_text(
            bot_response.phone_number, bot_response.reply_text,
        )
        logger.info(
            "outbound_result  msg_id=%s  send_ok=%s  wa_msg_id=%s",
            msg_id, result.success, result.message_id or "n/a",
        )

        persist_outbound(bot_response, wa_message_id=result.message_id or None)
        return

    # ── Image messages — log metadata, reply with limitation notice ──
    if wa_msg.type == "image" and wa_msg.image:
        logger.info(
            "inbound_image  msg_id=%s  sender=%s  media_id=%s  mime=%s  caption=%s",
            msg_id, sender,
            wa_msg.image.id, wa_msg.image.mime_type,
            (wa_msg.image.caption or "")[:80],
        )
        await whatsapp_client.send_text(sender, _UNSUPPORTED_TYPE_REPLY)
        return

    # ── Document messages — log metadata, reply with limitation ──────
    if wa_msg.type == "document" and wa_msg.document:
        logger.info(
            "inbound_document  msg_id=%s  sender=%s  media_id=%s  filename=%s",
            msg_id, sender,
            wa_msg.document.id, wa_msg.document.filename or "unknown",
        )
        await whatsapp_client.send_text(sender, _UNSUPPORTED_TYPE_REPLY)
        return

    # ── All other types — safe fallback ──────────────────────────────
    logger.info(
        "inbound_unsupported  msg_id=%s  sender=%s  type=%s",
        msg_id, sender, wa_msg.type,
    )
    await whatsapp_client.send_text(sender, _UNSUPPORTED_TYPE_REPLY)


def _is_human_takeover(phone_number: str) -> bool:
    """Check DB for human takeover flag. Never raises."""
    try:
        db = get_db()
        try:
            return repo.is_bot_paused(db, phone_number)
        finally:
            db.close()
    except Exception:
        logger.exception("takeover_check_failed  phone=%s", phone_number)
        return False
