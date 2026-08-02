import src.kb.loader as loader
from src.state.conversation_store import conversation_store
import src.db.database as _db_mod
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Test-scoped in-memory SQLite DB ──────────────────────────────────────────
# StaticPool ensures all connections share the same in-memory database.
_test_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_test_engine, autoflush=False, expire_on_commit=False)

# Patch the module-level engine and session factory so all code that imports
# from src.db.database uses the in-memory engine during tests.
_db_mod.engine = _test_engine
_db_mod.SessionLocal = _TestSession


def pytest_runtest_setup(item):
    """Reset KB caches, conversation state, and DB tables before each test."""
    loader._kb = None
    loader._md_articles = None
    conversation_store._turns.clear()
    conversation_store._flows.clear()

    # Recreate all tables fresh for every test
    from src.db.models import Base
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
