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

MENU_BODY = "¿En qué le puedo ayudar?"

MENU_BUTTONS = [
    {"id": "menu_productos", "title": "Info de productos"},
    {"id": "menu_cotizacion", "title": "Cotización"},
    {"id": "menu_visita", "title": "Agendar visita"},
]

MENU_FOOTER = "O escriba asesor para hablar con un miembro del equipo."


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

    # Send welcome text with interactive buttons in one message
    welcome_body = f"{WELCOME_TEXT}\n\n{MENU_BODY}"
    menu_result = await whatsapp_client.send_interactive_buttons(
        phone_number,
        body=welcome_body,
        buttons=MENU_BUTTONS,
        footer=MENU_FOOTER,
    )
    # Persist menu in background (don't block)
    _persist_menu(phone_number, menu_result)

    # Send image separately if configured (after the text to avoid disorder)
    image_url = settings.whatsapp_welcome_image_url
    media_id = settings.whatsapp_welcome_image_id
    logger.info(
        "welcome_image_check  phone=%s  image_url=%s  media_id=%s",
        phone_number, image_url or "", media_id or "",
    )
    if image_url or media_id:
        img_result = await whatsapp_client.send_image(
            phone_number,
            image_url=image_url,
            media_id=media_id,
            caption="",
        )
        logger.info(
            "welcome_image_result  phone=%s  success=%s  status=%s  error=%s",
            phone_number, img_result.success, img_result.status_code, img_result.error or "",
        )
        # Persist image in background (don't block)
        _persist_welcome_image(phone_number, img_result)
    else:
        logger.info("welcome_image_skipped  phone=%s  reason=no_url_or_media_id", phone_number)

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


def _persist_menu(phone_number: str, result: SendResult) -> None:
    """Log the outbound interactive menu."""
    try:
        db = get_db()
        try:
            repo.log_message(
                db,
                direction="outbound",
                phone_number=phone_number,
                message_type="interactive",
                text="[welcome menu buttons]",
                wa_message_id=result.message_id or None,
                intent="welcome",
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("persist_welcome_menu failed for %s", phone_number)
