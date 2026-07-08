from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from auditor.grader import Auditor, FakeAuditor, get_auditor


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("E2E_BASE_URL", "http://localhost:8100").rstrip("/")


@pytest.fixture(scope="session")
def artifacts_root() -> Path:
    root = Path(os.environ.get("E2E_ARTIFACTS_DIR", "e2e-artifacts")).absolute()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fetch_health(base_url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{base_url}/api/v1/health", timeout=3) as response:
            return json.loads(response.read())  # type: ignore[no-any-return]
    except (urllib.error.URLError, OSError, ValueError):
        return None


@pytest.fixture(scope="session")
def service_health(base_url: str) -> dict[str, Any]:
    """Wait for the compliance service; the pipeline drives the real app."""
    for _ in range(30):
        health = _fetch_health(base_url)
        if health is not None:
            return health
        time.sleep(1)
    pytest.fail(
        f"Compliance service is not reachable at {base_url}. Start it first, e.g.\n"
        "  cd services/compliance && uv run uvicorn app.main:app --port 8100"
    )


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        executable = os.environ.get("E2E_CHROMIUM_PATH") or None
        launched = playwright.chromium.launch(executable_path=executable)
        yield launched
        launched.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(viewport={"width": 1440, "height": 1100})
    try:
        yield context.new_page()
    finally:
        context.close()


@pytest.fixture(scope="session")
def auditor() -> Auditor:
    return get_auditor()


@pytest.fixture
def real_stack_guard(service_health: dict[str, Any], auditor: Auditor) -> None:
    """Intelligence tests must never 'pass' against the stub stack — that
    would be a silently green build with zero intelligence coverage."""
    problems = []
    if service_health.get("audit_backend") != "anthropic":
        problems.append(
            f"the service is running audit_backend={service_health.get('audit_backend')!r}; "
            "start it with COMPLIANCE_AUDIT_BACKEND=anthropic and an API key"
        )
    if isinstance(auditor, FakeAuditor):
        problems.append(
            "the Senior Auditor is the fake one; set ANTHROPIC_API_KEY "
            "(and optionally E2E_AUDITOR=anthropic)"
        )
    if problems:
        pytest.fail(
            "Intelligence run requires the real stack: " + "; and ".join(problems) + "."
        )
