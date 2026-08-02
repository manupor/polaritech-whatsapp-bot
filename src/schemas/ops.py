"""
Pydantic response schemas for the internal Ops API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Escalation ───────────────────────────────────────────────────────────────

class EscalationOut(BaseModel):
    id: int
    phone_number: str
    intent: str
    summary: str
    collected_fields: Dict[str, Any] = {}
    missing_fields: List[str] = []
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Lead ─────────────────────────────────────────────────────────────────────

class LeadOut(BaseModel):
    id: int
    phone_number: str
    lead_type: str
    province: Optional[str] = None
    zone: Optional[str] = None
    measurements: Optional[str] = None
    main_need: Optional[str] = None
    product_interest: Optional[str] = None
    has_photos: bool = False
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Conversation ─────────────────────────────────────────────────────────────

class ConversationOut(BaseModel):
    phone_number: str
    profile_name: str = "Unknown"
    current_intent: Optional[str] = None
    flow_type: Optional[str] = None
    collected_fields: Dict[str, Any] = {}
    missing_fields: List[str] = []
    needs_human: bool = False
    last_bot_response: Optional[str] = None
    updated_at: Optional[datetime] = None


# ── Status update ────────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: str


# ── Paginated list wrapper ───────────────────────────────────────────────────

class PaginatedList(BaseModel):
    items: List[Any]
    total: int
    limit: int
    offset: int
