"""Tests for database URL normalization across providers."""

from src.db.database import _normalize_url


def test_normalize_heroku_style_postgres_url():
    url = "postgres://user:pass@host:5432/db"
    assert _normalize_url(url) == "postgresql+psycopg://user:pass@host:5432/db"


def test_normalize_standard_postgresql_url():
    url = "postgresql://user:pass@host/db?sslmode=require"
    assert _normalize_url(url) == "postgresql+psycopg://user:pass@host/db?sslmode=require"


def test_normalize_keeps_explicit_driver():
    url = "postgresql+psycopg://user:pass@host/db"
    assert _normalize_url(url) == url


def test_normalize_leaves_sqlite_untouched():
    url = "sqlite:///polaritech.db"
    assert _normalize_url(url) == url
