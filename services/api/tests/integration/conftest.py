"""Integration fixtures — require a real Postgres + pgvector reachable via INTEGRATION_DATABASE_URL.

Run via `pytest tests/integration` in CI; skipped silently if no DB URL is set.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

INTEGRATION_DB_URL = os.environ.get("INTEGRATION_DATABASE_URL")


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
    # bust cached Settings so the env above takes effect
    from app.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(INTEGRATION_DB_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
async def db_clean() -> AsyncIterator[None]:
    """Truncate all data tables between tests."""
    assert INTEGRATION_DB_URL
    engine = create_async_engine(INTEGRATION_DB_URL, future=True)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE outfit_events, outfit_items, outfits, item_corrections, "
                "wardrobe_items, kid_consents, family_members, style_profiles, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()
    yield


@pytest.fixture()
def client(db_clean: None) -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def guardian_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def auth_headers(guardian_id: str) -> dict[str, str]:
    return {"X-Dev-User-Id": guardian_id}


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
