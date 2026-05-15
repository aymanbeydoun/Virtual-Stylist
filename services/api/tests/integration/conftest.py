"""Integration fixtures — require a real Postgres + pgvector reachable via INTEGRATION_DATABASE_URL.

Run via `pytest tests/integration` in CI; skipped silently if no DB URL is set.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command

INTEGRATION_DB_URL = os.environ.get("INTEGRATION_DATABASE_URL")


def _sync_url(async_url: str) -> str:
    return async_url.replace("+asyncpg", "")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if INTEGRATION_DB_URL:
        return
    skip = pytest.mark.skip(reason="INTEGRATION_DATABASE_URL not set")
    for item in items:
        if "tests/integration/" in str(item.path).replace("\\", "/"):
            item.add_marker(skip)


def _alembic_config(db_url: str) -> Config:
    here = Path(__file__).resolve().parent.parent.parent  # services/api/
    cfg = Config(str(here / "alembic.ini"))
    cfg.set_main_option("script_location", str(here / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> Iterator[None]:
    if not INTEGRATION_DB_URL:
        yield
        return
    storage_dir = tempfile.mkdtemp(prefix="vs-integration-")
    os.environ["DATABASE_URL"] = INTEGRATION_DB_URL
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_LOCAL_PATH"] = storage_dir
    os.environ["DEV_AUTH_BYPASS"] = "true"
    os.environ["MODEL_GATEWAY_BACKEND"] = "stub"
    from app.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(INTEGRATION_DB_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
def _db_clean() -> None:
    """Truncate all data tables between tests using a synchronous driver.

    Synchronous on purpose: avoids creating async engines bound to a
    test-local event loop that gets closed before the engine is disposed.
    """
    assert INTEGRATION_DB_URL
    with psycopg.connect(_sync_url(INTEGRATION_DB_URL), autocommit=True) as conn:
        conn.execute(
            "TRUNCATE TABLE outfit_events, outfit_items, outfits, item_corrections, "
            "wardrobe_items, kid_consents, family_members, style_profiles, users "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture()
def client(_db_clean: None) -> Iterator[TestClient]:
    """Fresh TestClient per test backed by a NullPool engine so no asyncpg
    connections leak across the per-test anyio portal event loop."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app import db as db_module
    from app.config import get_settings

    db_module.engine = create_async_engine(
        get_settings().database_url, poolclass=NullPool, future=True
    )
    db_module.SessionLocal = async_sessionmaker(db_module.engine, expire_on_commit=False)

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def guardian_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def auth_headers(guardian_id: str) -> dict[str, str]:
    return {"X-Dev-User-Id": guardian_id}
