"""The Playwright-to-LLM-assertion loop.

drive_fixture : upload a dummy case through the real UI, wait for the agent's
                verdict, scrape rating/reasoning/tables from the DOM.
evaluate_run  : deterministic gates + Senior Auditor AI grading -> verdict.
run_pipeline  : the full loop, with artifacts written for the developers.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from auditor.grader import Auditor
from auditor.schema import AuditorVerdict
from invoice_lab.scenarios import Fixture

DISCLAIMER_OPENING = "Audit & Compliance has performed the above procedures"


class PipelineInfraError(Exception):
    """The loop itself broke (service error, timeout) — distinct from a FAIL verdict."""


@dataclass
class PipelineResult:
    fixture_id: str
    scraped: dict[str, Any]
    gate_failures: list[str]
    verdict: AuditorVerdict | None
    duration_s: float
    artifacts_dir: Path | None = None

    @property
    def blocking_failures(self) -> list[str]:
        failures = list(self.gate_failures)
        if self.verdict is not None and self.verdict.failed:
            failures.extend(
                f"[{f.check}] {f.explanation} (defect: {f.defect_key}; "
                f"evidence: {f.dashboard_evidence})"
                for f in self.verdict.failures
            )
        return failures

    @property
    def passed(self) -> bool:
        return not self.blocking_failures


# --- capture ----------------------------------------------------------------


def _texts(page: Page, selector: str) -> list[str]:
    return [t.strip() for t in page.locator(selector).all_inner_texts() if t.strip()]


def scrape_report(page: Page) -> dict[str, Any]:
    """Scrape the rendered report straight from the DOM (not from the API)."""
    verdict = page.locator("[data-testid=verdict]")
    red_flags = []
    for flag in page.locator("[data-testid=red-flag]").all():
        red_flags.append(
            {
                "severity": flag.get_attribute("data-severity") or "",
                "text": flag.inner_text().replace("\n", " ").strip(),
            }
        )
    steps = []
    for step in page.locator("[data-testid=step]").all():
        steps.append(
            {
                "status": step.get_attribute("data-status") or "",
                "text": step.inner_text().replace("\n", " ").strip(),
            }
        )
    chain_rows = [
        row.inner_text().replace("\t", " | ").replace("\n", " | ").strip()
        for row in page.locator("[data-testid=chain-row]").all()
    ]
    disclaimer = page.locator("[data-testid=disclaimer-text]").inner_text().strip()
    return {
        "signal": verdict.get_attribute("data-signal") or "",
        "risk_rating": verdict.get_attribute("data-rating") or "",
        "rating_text": page.locator("[data-testid=rating]").inner_text().strip(),
        "guidance": page.locator("[data-testid=guidance]").inner_text().strip(),
        "rationale": page.locator("[data-testid=rationale]").inner_text().strip(),
        "executive_summary": page.locator("[data-testid=executive-summary]").inner_text().strip(),
        "sanitization": page.locator("[data-testid=sanitization]").inner_text().strip(),
        "red_flags": red_flags,
        "steps": steps,
        "chain_of_title_rows": chain_rows,
        "documents_received": _texts(page, "[data-testid=docs-received] li"),
        "documents_missing": _texts(page, "[data-testid=docs-missing] li"),
        "recommended_actions": _texts(page, "[data-testid=actions] li"),
        "disclaimer_present": disclaimer.startswith(DISCLAIMER_OPENING),
    }


# --- drive ------------------------------------------------------------------


def drive_fixture(
    page: Page,
    base_url: str,
    fixture: Fixture,
    docs_dir: Path,
    *,
    audit_timeout_s: float,
) -> dict[str, Any]:
    """Phase 2 trigger: upload the dummy invoice set via the front-end and
    capture the rendered result from the DOM."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for doc in fixture.documents:
        path = docs_dir / doc.filename
        path.write_bytes(doc.data)
        paths.append(str(path))

    page.goto(base_url, wait_until="networkidle")
    page.fill("#case_reference", fixture.case["case_reference"])
    page.fill("#vendor_name", fixture.case["vendor_name"])
    page.fill("#brand", fixture.case["brand"])
    page.fill("#product_category", fixture.case["product_category"])
    page.fill("#notes", fixture.case["notes"])
    page.set_input_files("#fileinput", paths)
    page.click("#runbtn")

    page.wait_for_selector(
        "[data-testid=verdict], #status.err", timeout=audit_timeout_s * 1000
    )
    if page.locator("#status.err").count() > 0:
        raise PipelineInfraError(
            f"The app reported an error instead of a verdict: "
            f"{page.locator('#status').inner_text().strip()!r}"
        )
    return scrape_report(page)


# --- assert -----------------------------------------------------------------


def evaluate_run(
    fixture: Fixture, scraped: dict[str, Any], auditor: Auditor
) -> tuple[list[str], AuditorVerdict | None]:
    """Deterministic gates first (cheap, objective); Senior Auditor grading
    only when the gates pass — a hard gate failure already blocks the build."""
    gates: list[str] = []
    if not scraped.get("disclaimer_present"):
        gates.append(
            "[disclaimer-gate] The mandatory Audit & Compliance disclaimer is missing "
            "from the rendered report."
        )
    signal = scraped.get("signal", "")
    if signal not in fixture.allowed_signals:
        gates.append(
            f"[signal-gate] Signal {signal!r} is outside the expected set "
            f"{sorted(fixture.allowed_signals)} for scenario {fixture.scenario!r}."
        )
    if gates:
        return gates, None
    return gates, auditor.grade(fixture.ground_truth(), scraped)


# --- the whole loop ---------------------------------------------------------


def run_pipeline(
    page: Page,
    base_url: str,
    fixture: Fixture,
    auditor: Auditor,
    artifacts_root: Path,
    *,
    audit_timeout_s: float = 420.0,
) -> PipelineResult:
    artifacts_dir = artifacts_root / fixture.fixture_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    (artifacts_dir / "ground_truth.json").write_text(
        json.dumps(fixture.ground_truth(), indent=1, sort_keys=True)
    )
    try:
        scraped = drive_fixture(
            page,
            base_url,
            fixture,
            artifacts_dir / "documents",
            audit_timeout_s=audit_timeout_s,
        )
    except Exception:
        try:
            page.screenshot(path=str(artifacts_dir / "failure.png"), full_page=True)
        except Exception:
            pass
        raise

    (artifacts_dir / "scraped.json").write_text(json.dumps(scraped, indent=1, sort_keys=True))
    gate_failures, verdict = evaluate_run(fixture, scraped, auditor)
    if verdict is not None:
        (artifacts_dir / "verdict.json").write_text(verdict.model_dump_json(indent=1))

    result = PipelineResult(
        fixture_id=fixture.fixture_id,
        scraped=scraped,
        gate_failures=gate_failures,
        verdict=verdict,
        duration_s=round(time.monotonic() - started, 1),
        artifacts_dir=artifacts_dir,
    )
    if not result.passed:
        page.screenshot(path=str(artifacts_dir / "failure.png"), full_page=True)
    _append_result_line(artifacts_root, result, auditor.name)
    return result


def _append_result_line(artifacts_root: Path, result: PipelineResult, auditor_name: str) -> None:
    line = {
        "fixture_id": result.fixture_id,
        "signal": result.scraped.get("signal"),
        "passed": result.passed,
        "gate_failures": result.gate_failures,
        "auditor": auditor_name,
        "auditor_verdict": result.verdict.verdict if result.verdict else None,
        "duration_s": result.duration_s,
    }
    with (artifacts_root / "results.jsonl").open("a") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")


def format_failure_report(fixture: Fixture, result: PipelineResult) -> str:
    lines = [
        f"INTELLIGENCE REGRESSION — {fixture.fixture_id} ({fixture.title})",
        f"Signal shown: {result.scraped.get('signal')!r}; "
        f"expected one of {sorted(fixture.allowed_signals)}.",
        "Logical errors:",
    ]
    lines += [f"  - {failure}" for failure in result.blocking_failures]
    if result.verdict is not None:
        lines.append(f"Senior Auditor summary: {result.verdict.summary}")
    if result.artifacts_dir is not None:
        lines.append(f"Artifacts: {result.artifacts_dir}")
    return "\n".join(lines)
