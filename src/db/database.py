"""
SQLAlchemy 2.x database engine and session management.

Default: SQLite (local file).  Set DATABASE_URL to a PostgreSQL connection
string for production (no code changes needed).
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.core.config import settings

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """
    Normalize database URLs for SQLAlchemy 2.x.

    Providers like Neon, Supabase and Heroku hand out `postgres://` URLs which
    SQLAlchemy no longer recognises, and `postgresql://` defaults to psycopg2.
    We force the psycopg (v3) driver used in requirements.txt.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _normalize_url(settings.database_url)
IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    # Serverless (Vercel) creates a new process per invocation, so connection
    # pooling across requests is useless and exhausts Postgres connections.
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Enable WAL mode for SQLite to allow concurrent reads
if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):  # type: ignore
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db() -> None:
    """Create all tables that don't exist yet."""
    from src.db.models import Base  # noqa: F811
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialised  url=%s", _safe_url())


def get_db() -> Session:
    """Return a new session.  Caller must close it."""
    return SessionLocal()


def _safe_url() -> str:
    """Return DB URL with password masked for logging."""
    url = DATABASE_URL
    if "@" in url:
        parts = url.split("@")
        return "***@" + parts[-1]
    return url
