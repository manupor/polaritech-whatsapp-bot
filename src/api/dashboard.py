"""
Internal operations dashboard — server-rendered HTML via Jinja2.

Mounted under /dashboard.  No auth yet; isolate behind reverse-proxy/VPN in production.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.db.database import get_db
from src.db import repositories as repo
from src.db.models import Contact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ── Dashboard Home ───────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def dashboard_home(request: Request):
    db = get_db()
    try:
        counts = {
            "escalations_open": len(repo.list_escalations(db, status="open", limit=1000)),
            "escalations_in_progress": len(repo.list_escalations(db, status="in_progress", limit=1000)),
            "leads_new": len(repo.list_leads(db, status="new", limit=1000)),
            "leads_contacted": len(repo.list_leads(db, status="contacted", limit=1000)),
            "leads_quoted": len(repo.list_leads(db, status="quoted", limit=1000)),
        }
    finally:
        db.close()
    return templates.TemplateResponse(request, "dashboard_home.html", {
        "counts": counts,
    })


# ── Escalations ─────────────────────────────────────────────────────────────

@router.get("/escalations", response_class=HTMLResponse)
def escalations_list(
    request: Request,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
):
    db = get_db()
    try:
        records = repo.list_escalations(db, status=status, priority=priority, limit=200)
    finally:
        db.close()
    return templates.TemplateResponse(request, "escalations.html", {
        "records": records,
        "filter_status": status or "",
        "filter_priority": priority or "",
    })


@router.get("/escalations/{record_id}", response_class=HTMLResponse)
def escalation_detail(request: Request, record_id: int):
    db = get_db()
    try:
        record = repo.get_escalation(db, record_id)
    finally:
        db.close()
    if not record:
        return HTMLResponse("<h1>404 — Escalación no encontrada</h1>", status_code=404)

    collected = json.loads(record.collected_fields_json or "{}")
    missing = json.loads(record.missing_fields_json or "[]")

    return templates.TemplateResponse(request, "escalation_detail.html", {
        "record": record,
        "collected_fields": ", ".join(f"{k}: {v}" for k, v in collected.items()) if collected else "",
        "missing_fields": ", ".join(missing) if missing else "",
    })


@router.post("/escalations/{record_id}/status")
def escalation_update_status(record_id: int, status: str = Form(...)):
    db = get_db()
    try:
        rec = repo.update_escalation_status(db, record_id, status)
        if not rec:
            return HTMLResponse("<h1>404 — Escalación no encontrada</h1>", status_code=404)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/dashboard/escalations/{record_id}", status_code=303)


# ── Leads ────────────────────────────────────────────────────────────────────

@router.get("/leads", response_class=HTMLResponse)
def leads_list(
    request: Request,
    status: Optional[str] = Query(None),
    lead_type: Optional[str] = Query(None),
):
    db = get_db()
    try:
        records = repo.list_leads(db, status=status, lead_type=lead_type, limit=200)
    finally:
        db.close()
    return templates.TemplateResponse(request, "leads.html", {
        "records": records,
        "filter_status": status or "",
        "filter_lead_type": lead_type or "",
    })


@router.get("/leads/{record_id}", response_class=HTMLResponse)
def lead_detail(request: Request, record_id: int):
    db = get_db()
    try:
        record = repo.get_lead(db, record_id)
    finally:
        db.close()
    if not record:
        return HTMLResponse("<h1>404 — Lead no encontrado</h1>", status_code=404)

    return templates.TemplateResponse(request, "lead_detail.html", {
        "record": record,
    })


@router.post("/leads/{record_id}/status")
def lead_update_status(record_id: int, status: str = Form(...)):
    db = get_db()
    try:
        rec = repo.update_lead_status(db, record_id, status)
        if not rec:
            return HTMLResponse("<h1>404 — Lead no encontrado</h1>", status_code=404)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url=f"/dashboard/leads/{record_id}", status_code=303)


# ── Message History ────────────────────────────────────────────────────────────

@router.get("/messages", response_class=HTMLResponse)
def message_history(
    request: Request,
    phone: Optional[str] = Query(None),
):
    """View full message log history for a phone number."""
    messages = []
    if phone:
        db = get_db()
        try:
            messages = repo.list_message_logs(db, phone_number=phone, limit=200)
        finally:
            db.close()

    return templates.TemplateResponse(request, "message_history.html", {
        "phone": phone or "",
        "messages": messages,
    })


# ── Conversation Lookup ──────────────────────────────────────────────────────

@router.get("/conversations", response_class=HTMLResponse)
def conversation_lookup(
    request: Request,
    phone: Optional[str] = Query(None),
):
    searched = bool(phone)
    snapshot = None
    collected_fields = ""
    missing_fields = ""

    if phone:
        db = get_db()
        try:
            snap = repo.get_snapshot_by_phone(db, phone)
            if snap:
                contact = db.query(Contact).filter(Contact.phone_number == phone).first()
                snapshot = type("Snapshot", (), {
                    "phone_number": snap.phone_number,
                    "profile_name": contact.profile_name if contact else "Unknown",
                    "current_intent": snap.current_intent,
                    "flow_type": snap.flow_type,
                    "needs_human": bool(snap.needs_human),
                    "human_takeover": bool(snap.human_takeover),
                    "bot_active": bool(snap.bot_active),
                    "last_bot_response": snap.last_bot_response,
                    "last_message_at": snap.last_message_at,
                    "updated_at": snap.updated_at,
                })()
                collected = json.loads(snap.collected_fields_json or "{}")
                missing = json.loads(snap.missing_fields_json or "[]")
                collected_fields = ", ".join(f"{k}: {v}" for k, v in collected.items()) if collected else ""
                missing_fields = ", ".join(missing) if missing else ""
        finally:
            db.close()

    return templates.TemplateResponse(request, "conversation_lookup.html", {
        "phone": phone or "",
        "searched": searched,
        "snapshot": snapshot,
        "collected_fields": collected_fields,
        "missing_fields": missing_fields,
    })


# ── Conversation Actions ─────────────────────────────────────────────────────

@router.post("/conversations/takeover")
def conversation_takeover(phone: str = Form(...)):
    """Human takes over conversation — bot stops responding."""
    db = get_db()
    try:
        snap = repo.set_human_takeover(db, phone, takeover=True)
        if not snap:
            return HTMLResponse("<h1>404 — Conversación no encontrada</h1>", status_code=404)
        db.commit()
    finally:
        db.close()
    logger.info("dashboard_takeover  phone=%s", phone)
    return RedirectResponse(url=f"/dashboard/conversations?phone={phone}", status_code=303)


@router.post("/conversations/resume")
def conversation_resume(phone: str = Form(...)):
    """Resume bot — disable human takeover."""
    db = get_db()
    try:
        snap = repo.set_human_takeover(db, phone, takeover=False)
        if not snap:
            return HTMLResponse("<h1>404 — Conversación no encontrada</h1>", status_code=404)
        db.commit()
    finally:
        db.close()
    logger.info("dashboard_resume  phone=%s", phone)
    return RedirectResponse(url=f"/dashboard/conversations?phone={phone}", status_code=303)


@router.post("/conversations/mark-lead")
def conversation_mark_lead(phone: str = Form(...)):
    """Create a lead from the current conversation snapshot."""
    db = get_db()
    try:
        snap = repo.get_snapshot_by_phone(db, phone)
        if not snap:
            return HTMLResponse("<h1>404 — Conversación no encontrada</h1>", status_code=404)
        collected = json.loads(snap.collected_fields_json or "{}")
        repo.upsert_lead(
            db,
            phone_number=phone,
            lead_type=snap.flow_type or "general",
            province=collected.get("provincia"),
            zone=collected.get("zona"),
            measurements=collected.get("medidas"),
            main_need=collected.get("necesidad"),
            product_interest=collected.get("producto"),
            has_photos=bool(collected.get("fotografias")),
        )
        db.commit()
    finally:
        db.close()
    logger.info("dashboard_mark_lead  phone=%s", phone)
    return RedirectResponse(url=f"/dashboard/conversations?phone={phone}", status_code=303)


@router.post("/conversations/mark-escalation")
def conversation_mark_escalation(phone: str = Form(...)):
    """Create an escalation record from the current conversation snapshot."""
    db = get_db()
    try:
        snap = repo.get_snapshot_by_phone(db, phone)
        if not snap:
            return HTMLResponse("<h1>404 — Conversación no encontrada</h1>", status_code=404)
        collected = json.loads(snap.collected_fields_json or "{}")
        missing = json.loads(snap.missing_fields_json or "[]")
        repo.create_escalation(
            db,
            phone_number=phone,
            intent=snap.current_intent or "unknown",
            summary=f"Escalación manual desde dashboard",
            collected_fields=collected,
            missing_fields=missing,
            priority="high",
        )
        db.commit()
    finally:
        db.close()
    logger.info("dashboard_mark_escalation  phone=%s", phone)
    return RedirectResponse(url=f"/dashboard/conversations?phone={phone}", status_code=303)
