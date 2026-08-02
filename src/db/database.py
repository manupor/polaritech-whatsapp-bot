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

from src.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Enable WAL mode for SQLite to allow concurrent reads
if "sqlite" in settings.database_url:
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
    url = settings.database_url
    if "@" in url:
        parts = url.split("@")
        return "***@" + parts[-1]
    return url
