"""
SQLAlchemy ORM models for persisted data.

Tables:
  contacts              – unique WhatsApp contacts
  message_logs          – every inbound/outbound message
  conversation_snapshots – latest flow state per phone
  escalation_records    – warranty, visit, quote escalations
  lead_records          – structured leads for follow-up
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(32), unique=True, nullable=False, index=True)
    profile_name = Column(String(255), nullable=False, default="Unknown")
    first_seen_at = Column(DateTime, nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    direction = Column(String(10), nullable=False)  # "inbound" | "outbound"
    phone_number = Column(String(32), nullable=False, index=True)
    message_type = Column(String(20), nullable=False, default="text")
    text = Column(Text, nullable=False, default="")
    wa_message_id = Column(String(128), nullable=True)
    intent = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class ConversationSnapshot(Base):
    __tablename__ = "conversation_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(32), unique=True, nullable=False, index=True)
    current_intent = Column(String(32), nullable=True)
    flow_type = Column(String(20), nullable=True)
    flow_status = Column(String(20), nullable=False, default="idle")  # idle, collecting, completed
    collected_fields_json = Column(Text, nullable=True)
    missing_fields_json = Column(Text, nullable=True)
    needs_human = Column(Integer, nullable=False, default=0)  # 0/1, SQLite-friendly bool
    human_takeover = Column(Integer, nullable=False, default=0)  # 0/1
    bot_active = Column(Integer, nullable=False, default=1)  # 0/1
    last_bot_response = Column(Text, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class EscalationRecord(Base):
    __tablename__ = "escalation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(32), nullable=False, index=True)
    intent = Column(String(32), nullable=False)
    summary = Column(Text, nullable=False, default="")
    collected_fields_json = Column(Text, nullable=True)
    missing_fields_json = Column(Text, nullable=True)
    priority = Column(String(10), nullable=False, default="normal")
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class LeadRecord(Base):
    __tablename__ = "lead_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(32), nullable=False, index=True)
    lead_type = Column(String(20), nullable=False)  # "quote", "technical_visit", "warranty", "general"
    province = Column(String(64), nullable=True)
    zone = Column(String(128), nullable=True)
    measurements = Column(String(255), nullable=True)
    main_need = Column(String(128), nullable=True)
    product_interest = Column(String(255), nullable=True)
    has_photos = Column(Integer, nullable=False, default=0)  # 0/1
    status = Column(String(20), nullable=False, default="new")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
