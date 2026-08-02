"""
Internal request / response models used across services.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel

from src.core.constants import Intent


class IncomingMessage(BaseModel):
    phone_number: str
    sender_name: str
    message_id: str
    text: str
    timestamp: str
    button_id: Optional[str] = None
    button_title: Optional[str] = None


class EscalationPayload(BaseModel):
    intent: Intent
    summary: str
    collected_fields: Dict[str, str] = {}
    missing_fields: List[str] = []
    priority: str = "normal"  # "high" or "normal"


class BotResponse(BaseModel):
    phone_number: str
    reply_text: str
    intent: Intent
    escalated: bool = False
    escalation: Optional[EscalationPayload] = None
    # Quick-reply buttons offered to guide the user. Each item: {"id", "title"}
    buttons: List[Dict[str, str]] = []
