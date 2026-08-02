"""
Repository layer — thin wrappers around SQLAlchemy queries.

All functions accept a `Session` so callers control transaction boundaries.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.db.models import (
    Contact,
    ConversationSnapshot,
    EscalationRecord,
    LeadRecord,
    MessageLog,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Contact ──────────────────────────────────────────────────────────────────

def upsert_contact(
    db: Session,
    phone_number: str,
    profile_name: str = "Unknown",
) -> Contact:
    contact = db.query(Contact).filter(Contact.phone_number == phone_number).first()
    if contact:
        contact.last_seen_at = _utcnow()
        if profile_name and profile_name != "Unknown":
            contact.profile_name = profile_name
    else:
        contact = Contact(
            phone_number=phone_number,
            profile_name=profile_name,
            first_seen_at=_utcnow(),
            last_seen_at=_utcnow(),
        )
        db.add(contact)
    db.flush()
    return contact


def is_new_conversation(db: Session, phone_number: str, window_hours: float = 24.0) -> bool:
    """
    Return True if this phone_number should receive a welcome message.

    Conditions (any → True):
      - Contact does not exist
      - No conversation snapshot exists
      - Last snapshot update is older than `window_hours`
    """
    contact = db.query(Contact).filter(Contact.phone_number == phone_number).first()
    if not contact:
        return True

    snap = (
        db.query(ConversationSnapshot)
        .filter(ConversationSnapshot.phone_number == phone_number)
        .first()
    )
    if not snap:
        return True

    if snap.updated_at is None:
        return True

    cutoff = _utcnow() - timedelta(hours=window_hours)
    # SQLite may return naive datetimes — normalize for comparison
    snap_time = snap.updated_at
    if snap_time.tzinfo is None:
        snap_time = snap_time.replace(tzinfo=timezone.utc)
    return snap_time < cutoff


# ── MessageLog ───────────────────────────────────────────────────────────────

def log_message(
    db: Session,
    *,
    direction: str,
    phone_number: str,
    message_type: str = "text",
    text: str = "",
    wa_message_id: Optional[str] = None,
    intent: Optional[str] = None,
) -> MessageLog:
    entry = MessageLog(
        direction=direction,
        phone_number=phone_number,
        message_type=message_type,
        text=text[:4000] if text else "",
        wa_message_id=wa_message_id,
        intent=intent,
        created_at=_utcnow(),
    )
    db.add(entry)
    db.flush()
    return entry


# ── ConversationSnapshot ─────────────────────────────────────────────────────

def upsert_snapshot(
    db: Session,
    phone_number: str,
    current_intent: Optional[str] = None,
    flow_type: Optional[str] = None,
    collected_fields: Optional[Dict[str, Any]] = None,
    missing_fields: Optional[List[str]] = None,
    needs_human: bool = False,
    last_bot_response: Optional[str] = None,
) -> ConversationSnapshot:
    snap = (
        db.query(ConversationSnapshot)
        .filter(ConversationSnapshot.phone_number == phone_number)
        .first()
    )
    now = _utcnow()
    if snap:
        snap.current_intent = current_intent
        snap.flow_type = flow_type or ""
        snap.collected_fields_json = json.dumps(collected_fields or {}, ensure_ascii=False)
        snap.missing_fields_json = json.dumps(missing_fields or [], ensure_ascii=False)
        snap.needs_human = 1 if needs_human else 0
        snap.last_bot_response = last_bot_response
        snap.last_message_at = now
        snap.updated_at = now
        # Preserve human_takeover / bot_active — only dashboard actions change them
    else:
        snap = ConversationSnapshot(
            phone_number=phone_number,
            current_intent=current_intent,
            flow_type=flow_type or "",
            collected_fields_json=json.dumps(collected_fields or {}, ensure_ascii=False),
            missing_fields_json=json.dumps(missing_fields or [], ensure_ascii=False),
            needs_human=1 if needs_human else 0,
            human_takeover=0,
            bot_active=1,
            last_bot_response=last_bot_response,
            last_message_at=now,
            updated_at=now,
        )
        db.add(snap)
    db.flush()
    return snap


def get_snapshot_by_phone(db: Session, phone_number: str) -> Optional[ConversationSnapshot]:
    return (
        db.query(ConversationSnapshot)
        .filter(ConversationSnapshot.phone_number == phone_number)
        .first()
    )


def is_bot_paused(db: Session, phone_number: str) -> bool:
    """Return True if human has taken over this conversation."""
    snap = get_snapshot_by_phone(db, phone_number)
    if not snap:
        return False
    return bool(snap.human_takeover)


def set_human_takeover(db: Session, phone_number: str, takeover: bool = True) -> Optional[ConversationSnapshot]:
    """Toggle human takeover on a conversation."""
    snap = get_snapshot_by_phone(db, phone_number)
    if not snap:
        return None
    snap.human_takeover = 1 if takeover else 0
    snap.bot_active = 0 if takeover else 1
    snap.updated_at = _utcnow()
    db.flush()
    return snap


# ── EscalationRecord ────────────────────────────────────────────────────────

def create_escalation(
    db: Session,
    *,
    phone_number: str,
    intent: str,
    summary: str = "",
    collected_fields: Optional[Dict[str, str]] = None,
    missing_fields: Optional[List[str]] = None,
    priority: str = "normal",
) -> EscalationRecord:
    record = EscalationRecord(
        phone_number=phone_number,
        intent=intent,
        summary=summary,
        collected_fields_json=json.dumps(collected_fields or {}, ensure_ascii=False),
        missing_fields_json=json.dumps(missing_fields or [], ensure_ascii=False),
        priority=priority,
        status="open",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(record)
    db.flush()
    return record


def get_escalation(db: Session, record_id: int) -> Optional[EscalationRecord]:
    return db.query(EscalationRecord).filter(EscalationRecord.id == record_id).first()


def list_escalations(
    db: Session,
    *,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[EscalationRecord]:
    q = db.query(EscalationRecord)
    if status:
        q = q.filter(EscalationRecord.status == status)
    if priority:
        q = q.filter(EscalationRecord.priority == priority)
    return q.order_by(desc(EscalationRecord.created_at)).offset(offset).limit(limit).all()


def update_escalation_status(
    db: Session, record_id: int, new_status: str,
) -> Optional[EscalationRecord]:
    record = get_escalation(db, record_id)
    if record:
        record.status = new_status
        record.updated_at = _utcnow()
        db.flush()
    return record


# ── LeadRecord ───────────────────────────────────────────────────────────────

def upsert_lead(
    db: Session,
    *,
    phone_number: str,
    lead_type: str,
    province: Optional[str] = None,
    zone: Optional[str] = None,
    measurements: Optional[str] = None,
    main_need: Optional[str] = None,
    product_interest: Optional[str] = None,
    has_photos: bool = False,
) -> LeadRecord:
    """Create or update lead.  Updates only non-null fields."""
    lead = (
        db.query(LeadRecord)
        .filter(
            LeadRecord.phone_number == phone_number,
            LeadRecord.lead_type == lead_type,
            LeadRecord.status.in_(("new", "contacted")),
        )
        .order_by(desc(LeadRecord.created_at))
        .first()
    )
    now = _utcnow()
    if lead:
        if province:
            lead.province = province
        if zone:
            lead.zone = zone
        if measurements:
            lead.measurements = measurements
        if main_need:
            lead.main_need = main_need
        if product_interest:
            lead.product_interest = product_interest
        if has_photos:
            lead.has_photos = 1
        lead.updated_at = now
    else:
        lead = LeadRecord(
            phone_number=phone_number,
            lead_type=lead_type,
            province=province,
            zone=zone,
            measurements=measurements,
            main_need=main_need,
            product_interest=product_interest,
            has_photos=1 if has_photos else 0,
            status="new",
            created_at=now,
            updated_at=now,
        )
        db.add(lead)
    db.flush()
    return lead


def get_lead(db: Session, record_id: int) -> Optional[LeadRecord]:
    return db.query(LeadRecord).filter(LeadRecord.id == record_id).first()


def list_leads(
    db: Session,
    *,
    status: Optional[str] = None,
    lead_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[LeadRecord]:
    q = db.query(LeadRecord)
    if status:
        q = q.filter(LeadRecord.status == status)
    if lead_type:
        q = q.filter(LeadRecord.lead_type == lead_type)
    return q.order_by(desc(LeadRecord.created_at)).offset(offset).limit(limit).all()


def list_message_logs(
    db: Session,
    *,
    phone_number: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[MessageLog]:
    """List message logs, optionally filtered by phone_number."""
    q = db.query(MessageLog)
    if phone_number:
        q = q.filter(MessageLog.phone_number == phone_number)
    return q.order_by(desc(MessageLog.created_at)).offset(offset).limit(limit).all()


def update_lead_status(
    db: Session, record_id: int, new_status: str,
) -> Optional[LeadRecord]:
    lead = get_lead(db, record_id)
    if lead:
        lead.status = new_status
        lead.updated_at = _utcnow()
        db.flush()
    return lead
