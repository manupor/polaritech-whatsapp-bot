"""
First-contact welcome flow.

Sends a greeting text and optional image to new conversations, then lets the
normal pipeline continue.  "New" is defined as:
  - contact does not exist, OR
  - no conversation snapshot, OR
  - last interaction > WELCOME_WINDOW_HOURS ago
"""

from __future__ import annotations

import logging
from typing import Optional

from src.core.config import settings
from src.db.database import get_db
from src.db import repositories as repo
from src.services.whatsapp_service import SendResult, whatsapp_client

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "Hola! Muchas gracias por escribirnos.\n"
    "Le saluda Valentina, asistente virtual de Polaritech. Será un gusto ayudarle.\n"
    "A continuación le compartiré la información necesaria para preparar su cotización."
)


async def maybe_send_welcome(phone_number: str, sender_name: str = "Unknown") -> bool:
    """
    Check if this is a new conversation and, if so, send welcome messages.

    Returns True if the welcome was sent, False otherwise.
    Failures are logged but never raised.
    """
    try:
        needs_welcome = _check_needs_welcome(phone_number)
    except Exception:
        logger.exception("welcome_check_failed  phone=%s", phone_number)
        return False

    if not needs_welcome:
        return False

    logger.info("welcome_flow_triggered  phone=%s  name=%s", phone_number, sender_name)

    # 1. Send greeting text
    text_result = await whatsapp_client.send_text(phone_number, WELCOME_TEXT)
    _persist_welcome_text(phone_number, text_result)

    # 2. Send image (if configured)
    await _send_welcome_image(phone_number)

    return True


def _check_needs_welcome(phone_number: str) -> bool:
    """Query DB to determine if welcome is needed."""
    db = get_db()
    try:
        return repo.is_new_conversation(
            db, phone_number, window_hours=settings.welcome_window_hours,
        )
    finally:
        db.close()


async def _send_welcome_image(phone_number: str) -> None:
    """Send the welcome image via URL or media ID, or skip with a warning."""
    image_url = settings.whatsapp_welcome_image_url
    media_id = settings.whatsapp_welcome_image_id

    if not image_url and not media_id:
        logger.warning(
            "welcome_image_skipped  phone=%s  reason=no_image_config", phone_number,
        )
        return

    result = await whatsapp_client.send_image(
        phone_number,
        image_url=image_url,
        media_id=media_id,
    )
    _persist_welcome_image(phone_number, result)


def _persist_welcome_text(phone_number: str, result: SendResult) -> None:
    """Log the outbound welcome text."""
    try:
        db = get_db()
        try:
            repo.log_message(
                db,
                direction="outbound",
                phone_number=phone_number,
                message_type="text",
                text=WELCOME_TEXT,
                wa_message_id=result.message_id or None,
                intent="welcome",
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("persist_welcome_text failed for %s", phone_number)


def _persist_welcome_image(phone_number: str, result: SendResult) -> None:
    """Log the outbound welcome image."""
    try:
        db = get_db()
        try:
            repo.log_message(
                db,
                direction="outbound",
                phone_number=phone_number,
                message_type="image",
                text="[welcome image]",
                wa_message_id=result.message_id or None,
                intent="welcome",
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("persist_welcome_image failed for %s", phone_number)
