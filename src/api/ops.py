"""
Internal operations API for Polaritech team.

Endpoints for viewing and managing leads, escalations, and conversations.
Auth is not implemented yet — isolate this router behind a reverse-proxy
or VPN in production until auth is added.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.db.database import get_db
from src.db import repositories as repo
from src.db.models import EscalationRecord, LeadRecord
from src.schemas.ops import (
    ConversationOut,
    EscalationOut,
    LeadOut,
    PaginatedList,
    StatusUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops"])

_VALID_ESCALATION_STATUSES = {"open", "in_progress", "closed"}
_VALID_LEAD_STATUSES = {"new", "contacted", "quoted", "closed"}


# ── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
def ops_health() -> dict:
    return {"status": "ok", "service": "ops"}


# ── Escalations ─────────────────────────────────────────────────────────────

def _escalation_to_out(rec: EscalationRecord) -> EscalationOut:
    return EscalationOut(
        id=rec.id,
        phone_number=rec.phone_number,
        intent=rec.intent,
        summary=rec.summary,
        collected_fields=json.loads(rec.collected_fields_json or "{}"),
        missing_fields=json.loads(rec.missing_fields_json or "[]"),
        priority=rec.priority,
        status=rec.status,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.get("/escalations")
def list_escalations(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedList:
    db = get_db()
    try:
        records = repo.list_escalations(
            db, status=status, priority=priority, limit=limit, offset=offset,
        )
        items = [_escalation_to_out(r) for r in records]
        total = len(items)
        return PaginatedList(items=items, total=total, limit=limit, offset=offset)
    finally:
        db.close()


@router.get("/escalations/{record_id}")
def get_escalation(record_id: int) -> EscalationOut:
    db = get_db()
    try:
        rec = repo.get_escalation(db, record_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Escalation not found")
        return _escalation_to_out(rec)
    finally:
        db.close()


@router.patch("/escalations/{record_id}/status")
def patch_escalation_status(record_id: int, body: StatusUpdate) -> EscalationOut:
    if body.status not in _VALID_ESCALATION_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(_VALID_ESCALATION_STATUSES))}",
        )
    db = get_db()
    try:
        rec = repo.update_escalation_status(db, record_id, body.status)
        if not rec:
            raise HTTPException(status_code=404, detail="Escalation not found")
        db.commit()
        return _escalation_to_out(rec)
    finally:
        db.close()


# ── Leads ────────────────────────────────────────────────────────────────────

def _lead_to_out(rec: LeadRecord) -> LeadOut:
    return LeadOut(
        id=rec.id,
        phone_number=rec.phone_number,
        lead_type=rec.lead_type,
        province=rec.province,
        zone=rec.zone,
        measurements=rec.measurements,
        main_need=rec.main_need,
        product_interest=rec.product_interest,
        has_photos=bool(rec.has_photos),
        status=rec.status,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.get("/leads")
def list_leads(
    status: Optional[str] = Query(None),
    lead_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedList:
    db = get_db()
    try:
        records = repo.list_leads(
            db, status=status, lead_type=lead_type, limit=limit, offset=offset,
        )
        items = [_lead_to_out(r) for r in records]
        total = len(items)
        return PaginatedList(items=items, total=total, limit=limit, offset=offset)
    finally:
        db.close()


@router.get("/leads/{record_id}")
def get_lead(record_id: int) -> LeadOut:
    db = get_db()
    try:
        rec = repo.get_lead(db, record_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Lead not found")
        return _lead_to_out(rec)
    finally:
        db.close()


@router.patch("/leads/{record_id}/status")
def patch_lead_status(record_id: int, body: StatusUpdate) -> LeadOut:
    if body.status not in _VALID_LEAD_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(_VALID_LEAD_STATUSES))}",
        )
    db = get_db()
    try:
        rec = repo.update_lead_status(db, record_id, body.status)
        if not rec:
            raise HTTPException(status_code=404, detail="Lead not found")
        db.commit()
        return _lead_to_out(rec)
    finally:
        db.close()


# ── Conversations ────────────────────────────────────────────────────────────

@router.get("/conversations/{phone_number}")
def get_conversation(phone_number: str) -> ConversationOut:
    db = get_db()
    try:
        snap = repo.get_snapshot_by_phone(db, phone_number)
        if not snap:
            raise HTTPException(status_code=404, detail="Conversation not found")

        contact = (
            db.query(repo.Contact)
            .filter(repo.Contact.phone_number == phone_number)
            .first()
        )

        return ConversationOut(
            phone_number=snap.phone_number,
            profile_name=contact.profile_name if contact else "Unknown",
            current_intent=snap.current_intent,
            flow_type=snap.flow_type,
            collected_fields=json.loads(snap.collected_fields_json or "{}"),
            missing_fields=json.loads(snap.missing_fields_json or "[]"),
            needs_human=bool(snap.needs_human),
            last_bot_response=snap.last_bot_response,
            updated_at=snap.updated_at,
        )
    finally:
        db.close()
