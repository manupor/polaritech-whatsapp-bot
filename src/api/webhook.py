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
from typing import Dict, Optional

import httpx

from fastapi import APIRouter, Query, Request, Response

from src.core.config import settings
from src.schemas.chatbot import IncomingMessage
from src.schemas.whatsapp import WhatsAppMessage, WhatsAppWebhookPayload
from src.db.database import get_db
from src.db import repositories as repo
from src.services.persistence_service import (
    hydrate_flow,
    persist_inbound,
    persist_outbound,
)
from src.services.response_service import handle_message, register_image_analysis
from src.services.welcome_service import maybe_send_welcome
from src.services.whatsapp_service import whatsapp_client
from src.services.vision_service import vision_service
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
            button_id=reply_id,
            button_title=reply_text,
            timestamp=wa_msg.timestamp,
        )

        persist_inbound(incoming, wa_message_id=msg_id)

        if _is_human_takeover(sender):
            logger.info("bot_paused  msg_id=%s  sender=%s  reason=human_takeover", msg_id, sender)
            return

        # Restore flow state from DB (serverless resets in-memory state)
        hydrate_flow(sender)

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
        welcome_sent = await maybe_send_welcome(sender, sender_name)

        # Persist inbound in background (don't block webhook)
        persist_inbound(incoming, wa_message_id=msg_id)

        # If welcome was just sent, skip the normal bot response to avoid duplicates
        if welcome_sent:
            logger.info("welcome_sent  msg_id=%s  sender=%s  — skipping bot response", msg_id, sender)
            return

        # ── Human takeover guard ─────────────────────────────────────
        if _is_human_takeover(sender):
            logger.info(
                "bot_paused  msg_id=%s  sender=%s  reason=human_takeover",
                msg_id, sender,
            )
            return

        # Restore flow state from DB (serverless resets in-memory state)
        hydrate_flow(sender)

        bot_response = handle_message(incoming)

        logger.info(
            "outbound_intent  msg_id=%s  intent=%s  escalated=%s  buttons=%d",
            msg_id, bot_response.intent.value, bot_response.escalated,
            len(bot_response.buttons),
        )

        # Send interactive buttons if present, otherwise plain text
        if bot_response.buttons:
            result = await whatsapp_client.send_interactive_buttons(
                bot_response.phone_number,
                body=bot_response.reply_text,
                buttons=bot_response.buttons,
            )
        else:
            result = await whatsapp_client.send_text(
                bot_response.phone_number, bot_response.reply_text,
            )

        logger.info(
            "outbound_result  msg_id=%s  send_ok=%s  wa_msg_id=%s",
            msg_id, result.success, result.message_id or "n/a",
        )

        # Persist outbound in background (don't block webhook)
        persist_outbound(bot_response, wa_message_id=result.message_id or None)
        
        # If flow was completed, clear it after persistence
        if bot_response.escalated:
            from src.state.conversation_store import conversation_store
            conversation_store.clear_flow(bot_response.phone_number)
            logger.info(
                "flow_cleared_after_persistence  phone=%s  intent=%s",
                bot_response.phone_number, bot_response.intent.value,
            )
        return

    # ── Image messages — process with vision service ──
    if wa_msg.type == "image" and wa_msg.image:
        logger.info(
            "inbound_image  msg_id=%s  sender=%s  media_id=%s  mime=%s  caption=%s",
            msg_id, sender,
            wa_msg.image.id, wa_msg.image.mime_type,
            (wa_msg.image.caption or "")[:80],
        )

        # Persist inbound image so the conversation stays active (no re-greeting)
        image_incoming = IncomingMessage(
            phone_number=sender,
            sender_name=sender_name,
            message_id=msg_id,
            text=wa_msg.image.caption or "[imagen]",
            timestamp=wa_msg.timestamp,
        )
        persist_inbound(image_incoming, wa_message_id=msg_id, message_type="image")

        # Restore flow state so the photo counts toward the active flow
        hydrate_flow(sender)

        # Download image from WhatsApp Media API
        logger.info("vision_step1_get_media_url  media_id=%s", wa_msg.image.id)
        image_url = await _get_whatsapp_media_url(wa_msg.image.id)
        if image_url:
            logger.info("vision_step2_url_obtained  url=%s", image_url[:100])
            # Analyze image with vision service (download + base64)
            analysis = await vision_service.extract_measurements(
                image_url, access_token=settings.whatsapp_access_token
            )
            if analysis:
                logger.info("vision_step3_analysis_success  description=%s", analysis['description'][:100])
                # Register the photo in the active flow and ask what's still missing
                bot_response = register_image_analysis(
                    sender, analysis["description"]
                )
                result = await whatsapp_client.send_text(
                    sender, bot_response.reply_text
                )
                persist_outbound(
                    bot_response, wa_message_id=result.message_id or None
                )
                return
            else:
                logger.warning("vision_step3_analysis_failed  vision_service returned None")
        else:
            logger.warning("vision_step2_url_failed  could not get media URL")

        # Fallback if vision analysis fails — still credit the photo to the flow
        logger.info("vision_fallback  sending manual request message")
        bot_response = register_image_analysis(
            sender,
            "No pude analizar la foto automáticamente, pero ya quedó registrada.",
        )
        result = await whatsapp_client.send_text(sender, bot_response.reply_text)
        persist_outbound(bot_response, wa_message_id=result.message_id or None)
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
    """Check if a phone number is under human takeover."""
    db = get_db()
    try:
        return repo.is_bot_paused(db, phone_number)
    finally:
        db.close()


async def _get_whatsapp_media_url(media_id: str) -> Optional[str]:
    """
    Get temporary download URL for WhatsApp media file.

    Args:
        media_id: WhatsApp media ID

    Returns:
        Temporary URL for downloading the media, or None if failed
    """
    if not settings.whatsapp_access_token:
        logger.warning("WHATSAPP_ACCESS_TOKEN not set — cannot download media")
        return None

    media_url = f"https://graph.facebook.com/{settings.meta_api_version}/{media_id}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                media_url,
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"}
            )

            if response.status_code == 200:
                data = response.json()
                url = data.get("url")
                if url:
                    logger.info("whatsapp_media_url_retrieved  media_id=%s", media_id)
                    return url
                else:
                    logger.warning("whatsapp_media_no_url  media_id=%s", media_id)
                    return None
            else:
                logger.error(
                    "whatsapp_media_failed  status=%d  media_id=%s",
                    response.status_code, media_id
                )
                return None

    except Exception as e:
        logger.exception("whatsapp_media_exception  media_id=%s  error=%s", media_id, str(e))
        return None
