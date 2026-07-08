"""The intelligence gate: run every dummy invoice case through the real UI,
let the live agent audit it, scrape the dashboard, and have the Senior
Auditor AI grade the logic. Any FAIL fails the build.

Requires the real stack:
  - compliance service running with COMPLIANCE_AUDIT_BACKEND=anthropic
  - ANTHROPIC_API_KEY for the Senior Auditor
Run: uv run pytest -m intelligence -n 2
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import Page

from auditor.grader import Auditor
from invoice_lab.scenarios import Fixture, build_library
from pipeline.runner import format_failure_report, run_pipeline

_LIMIT = int(os.environ.get("E2E_FIXTURE_LIMIT", "0"))
_AUDIT_TIMEOUT_S = float(os.environ.get("E2E_AUDIT_TIMEOUT_S", "420"))
LIBRARY = build_library(_LIMIT if _LIMIT > 0 else None)


def _annotate(title: str, message: str) -> None:
    """Surface the logical error in the GitHub Actions UI for the developers."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        one_line = message.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::error title={title}::{one_line}")


@pytest.mark.intelligence
@pytest.mark.parametrize("fixture", LIBRARY, ids=[f.fixture_id for f in LIBRARY])
def test_agent_intelligence(
    page: Page,
    base_url: str,
    auditor: Auditor,
    artifacts_root: Path,
    real_stack_guard: None,
    fixture: Fixture,
) -> None:
    result = run_pipeline(
        page,
        base_url,
        fixture,
        auditor,
        artifacts_root,
        audit_timeout_s=_AUDIT_TIMEOUT_S,
    )
    if not result.passed:
        report = format_failure_report(fixture, result)
        _annotate(f"Intelligence regression: {fixture.fixture_id}", report)
        pytest.fail(report, pytrace=False)
