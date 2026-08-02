import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.dashboard import router as dashboard_router
from src.api.ops import router as ops_router
from src.api.webhook import router as webhook_router
from src.core.config import settings
from src.db.database import init_db
from src.kb.loader import get_kb, get_md_articles

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────
    kb = get_kb()
    md_articles = get_md_articles()
    logger.info(
        "Polaritech bot started — %d products, %d FAQs, %d MD sections, %d pending fields",
        len(kb.products), len(kb.faq), len(md_articles), len(kb.pending_information),
    )
    init_db()
    wa_ready = bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)
    logger.info(
        "WhatsApp API ready=%s  api_version=%s  phone_number_id=%s",
        wa_ready, settings.meta_api_version,
        settings.whatsapp_phone_number_id[:4] + "***" if settings.whatsapp_phone_number_id else "not set",
    )
    yield
    # ── Shutdown ─────────────────────────────────────────────────────


app = FastAPI(
    title="Polaritech WhatsApp Bot",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.include_router(webhook_router)
app.include_router(ops_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
