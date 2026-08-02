"""
Pydantic models representing the WhatsApp Cloud API webhook payload.
Only the fields we actually use are modelled; everything else is ignored
via model_config extra='ignore'.

Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Contact / Profile ────────────────────────────────────────────────────────

class WhatsAppProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""


class WhatsAppContact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    profile: WhatsAppProfile = WhatsAppProfile()
    wa_id: str


# ── Message body types ───────────────────────────────────────────────────────

class WhatsAppText(BaseModel):
    body: str


class WhatsAppImage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mime_type: str = ""
    sha256: str = ""
    id: str = ""
    caption: Optional[str] = None


class WhatsAppDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mime_type: str = ""
    sha256: str = ""
    id: str = ""
    filename: Optional[str] = None
    caption: Optional[str] = None


# ── Message ──────────────────────────────────────────────────────────────────

class WhatsAppMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: Optional[WhatsAppText] = None
    image: Optional[WhatsAppImage] = None
    document: Optional[WhatsAppDocument] = None


# ── Statuses ─────────────────────────────────────────────────────────────────

class WhatsAppStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    status: str  # "sent", "delivered", "read", "failed"
    timestamp: str
    recipient_id: str


# ── Webhook structure ────────────────────────────────────────────────────────

class WhatsAppMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    display_phone_number: str
    phone_number_id: str


class WhatsAppValue(BaseModel):
    model_config = ConfigDict(extra="ignore")
    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: Optional[List[WhatsAppContact]] = None
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[WhatsAppStatus]] = None


class WhatsAppChange(BaseModel):
    model_config = ConfigDict(extra="ignore")
    field: str
    value: WhatsAppValue


class WhatsAppEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    changes: List[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    object: str
    entry: List[WhatsAppEntry]
