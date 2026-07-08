"""Plumbing tests: prove the Playwright->scrape->assert loop works and that a
FAIL verdict actually blocks the build. Deterministic — fake auditor, works
against the stub backend, no API key needed."""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from auditor.grader import FakeAuditor
from invoice_lab.scenarios import build_library
from pipeline.runner import evaluate_run, format_failure_report, run_pipeline

PLUMBING_FIXTURES = [f for f in build_library() if f.plumbing]


@pytest.mark.parametrize("fixture", PLUMBING_FIXTURES, ids=lambda f: f.fixture_id)
def test_ui_loop_uploads_audits_and_scrapes(
    page: Page,
    base_url: str,
    artifacts_root: Path,
    service_health: dict[str, Any],
    fixture: Any,
) -> None:
    result = run_pipeline(
        page, base_url, fixture, FakeAuditor(), artifacts_root, audit_timeout_s=120
    )
    assert result.passed, format_failure_report(fixture, result)

    scraped = result.scraped
    assert scraped["signal"] in {"GREEN", "AMBER", "RED"}
    assert scraped["risk_rating"] in {"LOW", "MEDIUM", "HIGH"}
    assert scraped["disclaimer_present"], "mandatory disclaimer missing from the DOM"
    assert scraped["rationale"]
    assert scraped["documents_missing"], "step-7 requested-but-not-received list is empty"
    assert (result.artifacts_dir / "scraped.json").exists()  # type: ignore[union-attr]
    assert (result.artifacts_dir / "ground_truth.json").exists()  # type: ignore[union-attr]


def test_signal_gate_blocks_without_auditor_call() -> None:
    fixture = next(f for f in build_library() if f.scenario == "quantity_inflation")

    class ExplodingAuditor:
        name = "must-not-be-called"

        def grade(self, ground_truth: dict[str, Any], scraped: dict[str, Any]) -> Any:
            raise AssertionError("auditor must not run when a deterministic gate fails")

    gates, verdict = evaluate_run(
        fixture,
        {"signal": "GREEN", "disclaimer_present": True},
        ExplodingAuditor(),
    )
    assert verdict is None
    assert any("signal-gate" in g for g in gates)


def test_fail_verdict_produces_blocking_failure_payload() -> None:
    """The Verdict step: a FAIL payload from the auditor must block the build
    and carry a developer-readable logical error."""
    fixture = next(f for f in build_library() if f.scenario == "mid_chain_sku_introduction")
    forced = dataclasses.replace(
        fixture, grading_notes=fixture.grading_notes + " __force_fail__"
    )
    gates, verdict = evaluate_run(
        forced,
        {"signal": "RED", "disclaimer_present": True, "rating_text": "HIGH RISK — RED"},
        FakeAuditor(),
    )
    assert gates == []
    assert verdict is not None and verdict.failed

    from pipeline.runner import PipelineResult

    result = PipelineResult(
        fixture_id=forced.fixture_id,
        scraped={"signal": "RED"},
        gate_failures=gates,
        verdict=verdict,
        duration_s=0.1,
    )
    assert not result.passed
    report = format_failure_report(forced, result)
    assert "INTELLIGENCE REGRESSION" in report
    assert "mid_chain_sku_introduction" in report
    assert "Forced failure marker" in report


def test_missing_disclaimer_fails_the_gate() -> None:
    fixture = next(f for f in build_library() if f.scenario == "clean_chain")
    gates, verdict = evaluate_run(
        fixture, {"signal": "AMBER", "disclaimer_present": False}, FakeAuditor()
    )
    assert verdict is None
    assert any("disclaimer-gate" in g for g in gates)
