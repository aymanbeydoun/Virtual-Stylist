"""The Senior Auditor AI: grades the primary agent's dashboard output.

Given a fixture's ground truth and the payload scraped from the DOM, it
returns a structured PASS/FAIL verdict. A FAIL payload fails the build.
"""
from __future__ import annotations

import json
import os
from typing import Any, Protocol

from auditor.schema import (
    VERDICT_JSON_SCHEMA,
    AuditorVerdict,
    CheckName,
    CheckResult,
    GradingFailure,
)

AUDITOR_SYSTEM_PROMPT = """You are the Senior Auditor AI for BFL Group's compliance CI \
pipeline. A junior AI compliance agent has audited a synthetic (dummy) invoice case and \
published its report on a dashboard. You are given:
1. GROUND TRUTH: the case's actual documents (with exact line items and figures), the \
defects that were deliberately seeded, and the expected outcome. Each document's \
content_facts is the exhaustive record of what is printed on that page — every party, \
address, tax registration, date, reference, line item and total that appears on the \
document is listed there (a "note" field marks anything unusual, e.g. redactions or \
fields the document type does not carry).
2. SCRAPED DASHBOARD OUTPUT: what the junior agent actually displayed.

Grade the junior agent's LOGIC, not its style. Run exactly these four checks:

- defect_detection: every required seeded defect (expected.required_defect_keys) must be \
clearly surfaced somewhere in the dashboard output (red flags, step findings, rationale, \
or summary). Semantic equivalence counts — the agent does not need to use the defect key \
or identical wording, but a reader must be able to tell the specific problem was caught. \
Vague boilerplate ("documents incomplete") does NOT count as catching a specific defect.
- rating_consistency: the displayed signal must be one of expected.allowed_signals, and \
the rating/rationale must be internally consistent (e.g. rationale describing critical \
unresolved defects while the signal is GREEN is inconsistent).
- math_reconciliation: any quantities, totals, or arithmetic the agent states must agree \
with the ground-truth document facts. If the case seeds a quantity or value defect, the \
agent's cited numbers must match the documents.
- hallucination_screen: the agent must not invent documents that were not provided, \
claim verifications it could not perform, cite specific identifiers or figures that \
appear nowhere in any document's content_facts, or fabricate defects that contradict \
the ground truth. Cautious language, extra legitimate observations, paraphrased or \
reformatted values that match content_facts (e.g. quoting a tax registration without \
the "TRN " prefix, reordered addresses, computed subtotals), and requests for missing \
standard documents are NOT hallucinations. Two further classes of statements are \
legitimate findings, never hallucinations: (a) visual-presentation observations — the \
synthetic documents are deliberately rendered as plain typed text, so agent remarks \
that a document lacks a letterhead, logo, signature, stamp, security feature, or looks \
like a plain text/spreadsheet extract are accurate vision findings (content_facts lists \
printed CONTENT and may note presentation; absence of a feature from content_facts \
means the document does NOT have it); (b) coverage observations about spreadsheets — \
where content_facts records a "rows" list, those rows are the file's complete contents, \
so an agent claim that a chain link, leg, or SKU is missing from that spreadsheet is \
CORRECT whenever no matching row exists, and must be verified against "rows" before \
being called fabricated.

Verdict rules:
- verdict = FAIL if ANY check fails; otherwise PASS.
- Do not fail for: tone, verbosity, extra cautious red flags that are defensible from \
the documents, conservative rating WITHIN the allowed set, or requests for more \
documentation.
- For every failed check add one failures[] entry with the seeded defect_key it relates \
to ("-" if none), a precise explanation of the logical error, and the dashboard text \
(or its absence) as evidence. Write explanations for the developer who must fix the \
regression.

Respond only with the structured JSON verdict."""


class Auditor(Protocol):
    name: str

    def grade(self, ground_truth: dict[str, Any], scraped: dict[str, Any]) -> AuditorVerdict: ...


class SeniorAuditorAI:
    """LLM-powered assertion layer (Claude, structured output)."""

    def __init__(self, api_key: str, model: str, max_output_tokens: int = 16000) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_output_tokens = max_output_tokens
        self.name = f"senior-auditor:{model}"

    def grade(self, ground_truth: dict[str, Any], scraped: dict[str, Any]) -> AuditorVerdict:
        payload = (
            "GROUND TRUTH (the real facts of this synthetic case):\n"
            + json.dumps(ground_truth, indent=1, sort_keys=True)
            + "\n\nSCRAPED DASHBOARD OUTPUT (what the junior agent displayed):\n"
            + json.dumps(scraped, indent=1, sort_keys=True)
            + "\n\nGrade it now."
        )
        with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_output_tokens,
            thinking={"type": "adaptive"},
            output_config={
                "effort": "high",
                "format": {"type": "json_schema", "schema": VERDICT_JSON_SCHEMA},
            },
            system=[
                {
                    "type": "text",
                    "text": AUDITOR_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": payload}],
        ) as stream:
            message = stream.get_final_message()

        if message.stop_reason not in ("end_turn", "stop_sequence"):
            raise RuntimeError(
                f"Senior Auditor did not complete grading (stop_reason={message.stop_reason})"
            )
        text = "".join(block.text for block in message.content if block.type == "text")
        return AuditorVerdict.model_validate_json(text)


class FakeAuditor:
    """Deterministic auditor for harness plumbing tests — no network, no key.

    Fails when the scraped signal is outside the fixture's allowed set, or
    when the ground truth carries the __force_fail__ marker (used to test
    that a FAIL payload actually blocks the build).
    """

    name = "fake-auditor"

    def grade(self, ground_truth: dict[str, Any], scraped: dict[str, Any]) -> AuditorVerdict:
        allowed = set(ground_truth.get("expected", {}).get("allowed_signals", []))
        failures: list[GradingFailure] = []
        if "__force_fail__" in ground_truth.get("grading_notes", ""):
            failures.append(
                GradingFailure(
                    check=CheckName.DEFECT_DETECTION,
                    defect_key=ground_truth["expected"]["required_defect_keys"][0]
                    if ground_truth["expected"]["required_defect_keys"]
                    else "-",
                    explanation="Forced failure marker present (harness self-test).",
                    dashboard_evidence="n/a",
                )
            )
        if allowed and scraped.get("signal") not in allowed:
            failures.append(
                GradingFailure(
                    check=CheckName.RATING_CONSISTENCY,
                    defect_key="-",
                    explanation=(
                        f"Signal {scraped.get('signal')!r} is outside the allowed set "
                        f"{sorted(allowed)}."
                    ),
                    dashboard_evidence=str(scraped.get("rating_text", "")),
                )
            )
        verdict = "FAIL" if failures else "PASS"
        return AuditorVerdict(
            verdict=verdict,
            checks=[
                CheckResult(
                    check=CheckName.RATING_CONSISTENCY,
                    status="fail" if failures else "pass",
                    details="Deterministic fake grading (plumbing mode).",
                )
            ],
            failures=failures,
            summary=f"Fake auditor: {verdict.lower()} (plumbing mode, no LLM grading).",
        )


def get_auditor() -> Auditor:
    """Pick the auditor from the environment.

    E2E_AUDITOR=fake       -> FakeAuditor (plumbing)
    E2E_AUDITOR=anthropic  -> SeniorAuditorAI (requires ANTHROPIC_API_KEY)
    unset                  -> anthropic when a key is present, else fake
    """
    choice = os.environ.get("E2E_AUDITOR", "").strip().lower()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if choice == "fake":
        return FakeAuditor()
    if choice == "anthropic" or (not choice and api_key):
        if not api_key:
            raise RuntimeError("E2E_AUDITOR=anthropic requires ANTHROPIC_API_KEY.")
        return SeniorAuditorAI(
            api_key=api_key,
            model=os.environ.get("E2E_AUDITOR_MODEL", "claude-opus-4-8"),
        )
    return FakeAuditor()
