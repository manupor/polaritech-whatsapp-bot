"""
Vercel serverless entry point.
Exposes the FastAPI app for Vercel's Python runtime.

Vercel's Python runtime does not support FastAPI lifespan events,
so we create a minimal app here that includes the same routers
but skips the async lifespan context manager.

Vercel filesystem is read-only except /tmp, so we override DATABASE_URL
to point to /tmp for SQLite.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path so 'src' package is importable
_project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _project_root)

# Override SQLite path to writable /tmp on Vercel (must happen BEFORE src imports)
_db_url = os.environ.get("DATABASE_URL", "")
if not _db_url or "sqlite" in _db_url:
    os.environ["DATABASE_URL"] = "sqlite:////tmp/polaritech.db"

import logging  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.db.database import init_db  # noqa: E402
from src.kb.loader import get_kb, get_md_articles  # noqa: E402
from src.api.webhook import router as webhook_router  # noqa: E402
from src.api.ops import router as ops_router  # noqa: E402
from src.api.dashboard import router as dashboard_router  # noqa: E402

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

# Eagerly initialize KB and DB (no lifespan needed)
get_kb()
get_md_articles()
init_db()

app = FastAPI(
    title="Polaritech WhatsApp Bot",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.include_router(webhook_router)
app.include_router(ops_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
