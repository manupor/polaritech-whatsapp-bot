"""
Outbound WhatsApp Cloud API client.

Sends text messages via the Meta Graph API.  Designed to never crash the
application — all errors are logged and suppressed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    """Outcome of an outbound send attempt."""
    success: bool
    status_code: int = 0
    message_id: str = ""
    error: str = ""


class WhatsAppClient:
    """Thin wrapper around the WhatsApp Cloud API messages endpoint."""

    def __init__(
        self,
        access_token: str = "",
        phone_number_id: str = "",
        api_url: str = "",
        timeout: float = 30.0,
    ) -> None:
        self._access_token = access_token or settings.whatsapp_access_token
        self._phone_number_id = phone_number_id or settings.whatsapp_phone_number_id
        self._api_url = api_url or settings.whatsapp_api_url
        self._timeout = timeout or settings.whatsapp_send_timeout

    # ── Public API ───────────────────────────────────────────────────────

    async def send_text(self, to: str, body: str) -> SendResult:
        """Send a plain-text message.  Never raises."""
        if not self._access_token:
            logger.warning("WHATSAPP_ACCESS_TOKEN not set — skipping send to %s", to)
            return SendResult(success=False, error="access_token not configured")

        payload = self._build_text_payload(to, body)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._api_url,
                    headers=self._headers(),
                    json=payload,
                )

            if resp.status_code == 200:
                data = resp.json()
                msg_id = ""
                messages = data.get("messages", [])
                if messages:
                    msg_id = messages[0].get("id", "")
                logger.info(
                    "outbound_send  to=%s  status=ok  wa_message_id=%s",
                    to, msg_id,
                )
                return SendResult(success=True, status_code=200, message_id=msg_id)

            error_text = resp.text[:300]
            logger.error(
                "outbound_send  to=%s  status=error  http=%d  body=%s",
                to, resp.status_code, error_text,
            )
            return SendResult(
                success=False, status_code=resp.status_code, error=error_text,
            )

        except httpx.TimeoutException:
            logger.error("outbound_send  to=%s  status=timeout", to)
            return SendResult(success=False, error="timeout")

        except Exception as exc:
            logger.exception("outbound_send  to=%s  status=exception", to)
            return SendResult(success=False, error=str(exc))

    async def send_image(
        self,
        to: str,
        *,
        image_url: str = "",
        media_id: str = "",
        caption: str = "",
    ) -> SendResult:
        """Send an image message by URL or pre-uploaded media ID.  Never raises."""
        if not self._access_token:
            logger.warning("WHATSAPP_ACCESS_TOKEN not set — skipping image send to %s", to)
            return SendResult(success=False, error="access_token not configured")

        if not image_url and not media_id:
            logger.warning("No image_url or media_id provided — skipping image send to %s", to)
            return SendResult(success=False, error="no image source")

        payload = self._build_image_payload(to, image_url=image_url, media_id=media_id, caption=caption)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._api_url,
                    headers=self._headers(),
                    json=payload,
                )

            if resp.status_code == 200:
                data = resp.json()
                msg_id = ""
                messages = data.get("messages", [])
                if messages:
                    msg_id = messages[0].get("id", "")
                logger.info(
                    "outbound_image  to=%s  status=ok  wa_message_id=%s",
                    to, msg_id,
                )
                return SendResult(success=True, status_code=200, message_id=msg_id)

            error_text = resp.text[:300]
            logger.error(
                "outbound_image  to=%s  status=error  http=%d  body=%s",
                to, resp.status_code, error_text,
            )
            return SendResult(
                success=False, status_code=resp.status_code, error=error_text,
            )

        except httpx.TimeoutException:
            logger.error("outbound_image  to=%s  status=timeout", to)
            return SendResult(success=False, error="timeout")

        except Exception as exc:
            logger.exception("outbound_image  to=%s  status=exception", to)
            return SendResult(success=False, error=str(exc))

    async def send_interactive_buttons(
        self,
        to: str,
        *,
        body: str,
        buttons: list[Dict[str, str]],
        header: str = "",
        footer: str = "",
    ) -> SendResult:
        """Send an interactive reply-buttons message (max 3 buttons).  Never raises."""
        if not self._access_token:
            logger.warning("WHATSAPP_ACCESS_TOKEN not set — skipping interactive send to %s", to)
            return SendResult(success=False, error="access_token not configured")

        payload = self._build_interactive_buttons_payload(
            to, body=body, buttons=buttons, header=header, footer=footer,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._api_url,
                    headers=self._headers(),
                    json=payload,
                )

            if resp.status_code == 200:
                data = resp.json()
                msg_id = ""
                messages = data.get("messages", [])
                if messages:
                    msg_id = messages[0].get("id", "")
                logger.info(
                    "outbound_interactive  to=%s  status=ok  wa_message_id=%s",
                    to, msg_id,
                )
                return SendResult(success=True, status_code=200, message_id=msg_id)

            error_text = resp.text[:300]
            logger.error(
                "outbound_interactive  to=%s  status=error  http=%d  body=%s",
                to, resp.status_code, error_text,
            )
            return SendResult(
                success=False, status_code=resp.status_code, error=error_text,
            )

        except httpx.TimeoutException:
            logger.error("outbound_interactive  to=%s  status=timeout", to)
            return SendResult(success=False, error="timeout")

        except Exception as exc:
            logger.exception("outbound_interactive  to=%s  status=exception", to)
            return SendResult(success=False, error=str(exc))

    async def send_interactive_list(
        self,
        to: str,
        *,
        body: str,
        button_text: str,
        sections: list[Dict[str, Any]],
        header: str = "",
        footer: str = "",
    ) -> SendResult:
        """Send an interactive list message (up to 10 items).  Never raises."""
        if not self._access_token:
            logger.warning("WHATSAPP_ACCESS_TOKEN not set — skipping list send to %s", to)
            return SendResult(success=False, error="access_token not configured")

        payload = self._build_interactive_list_payload(
            to, body=body, button_text=button_text, sections=sections,
            header=header, footer=footer,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._api_url,
                    headers=self._headers(),
                    json=payload,
                )

            if resp.status_code == 200:
                data = resp.json()
                msg_id = ""
                messages = data.get("messages", [])
                if messages:
                    msg_id = messages[0].get("id", "")
                logger.info(
                    "outbound_list  to=%s  status=ok  wa_message_id=%s",
                    to, msg_id,
                )
                return SendResult(success=True, status_code=200, message_id=msg_id)

            error_text = resp.text[:300]
            logger.error(
                "outbound_list  to=%s  status=error  http=%d  body=%s",
                to, resp.status_code, error_text,
            )
            return SendResult(
                success=False, status_code=resp.status_code, error=error_text,
            )

        except httpx.TimeoutException:
            logger.error("outbound_list  to=%s  status=timeout", to)
            return SendResult(success=False, error="timeout")

        except Exception as exc:
            logger.exception("outbound_list  to=%s  status=exception", to)
            return SendResult(success=False, error=str(exc))

    # ── Internals ────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_text_payload(to: str, body: str) -> Dict[str, Any]:
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }

    @staticmethod
    def _build_image_payload(
        to: str,
        *,
        image_url: str = "",
        media_id: str = "",
        caption: str = "",
    ) -> Dict[str, Any]:
        image_obj: Dict[str, Any] = {}
        if media_id:
            image_obj["id"] = media_id
        elif image_url:
            image_obj["link"] = image_url
        if caption:
            image_obj["caption"] = caption
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": image_obj,
        }

    @staticmethod
    def _build_interactive_buttons_payload(
        to: str,
        *,
        body: str,
        buttons: list[Dict[str, str]],
        header: str = "",
        footer: str = "",
    ) -> Dict[str, Any]:
        action_buttons = []
        for btn in buttons[:3]:
            action_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn["id"],
                    "title": btn["title"][:20],
                },
            })
        interactive: Dict[str, Any] = {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": action_buttons},
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }

    @staticmethod
    def _build_interactive_list_payload(
        to: str,
        *,
        body: str,
        button_text: str,
        sections: list[Dict[str, Any]],
        header: str = "",
        footer: str = "",
    ) -> Dict[str, Any]:
        interactive: Dict[str, Any] = {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text[:20],
                "sections": sections,
            },
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }


# Singleton — created once, used by webhook handler
whatsapp_client = WhatsAppClient()
