"""Audit gateways: the real Claude-backed auditor and a deterministic stub."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.agent.checklist import STANDARD_DOCUMENT_CHECKLIST
from app.agent.protocol import REPORT_JSON_SCHEMA, SYSTEM_PROMPT
from app.config import get_settings
from app.schemas.audit import (
    AgentFindings,
    ChainLink,
    CheckStatus,
    MissingDocument,
    RedFlag,
    RiskRating,
    SanitizationCheck,
    Severity,
    StepFinding,
)

_PROTOCOL_STEPS = [
    "Full Invoice Verification",
    "Vendor Authenticity & Due Diligence",
    "Chain of Title & Proof of Movement",
    "SKU, Quantity, and Value Flow Testing",
    "Brand Authenticity",
]


class AuditFailedError(Exception):
    """The audit could not be completed; the message is safe to surface."""


@dataclass
class GatewayResult:
    findings: AgentFindings
    model_id: str


class AuditGateway(Protocol):
    async def run_audit(
        self, *, content_blocks: list[dict[str, Any]], case_context: dict[str, str]
    ) -> GatewayResult: ...


class AnthropicAuditGateway:
    """Runs the full protocol against the Claude API.

    PDFs/images are analyzed natively by the model (high-fidelity OCR incl.
    font and table-alignment anomalies). Structured outputs guarantee the
    response parses into AgentFindings.
    """

    def __init__(self, api_key: str, model: str, max_output_tokens: int) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_output_tokens = max_output_tokens

    async def run_audit(
        self, *, content_blocks: list[dict[str, Any]], case_context: dict[str, str]
    ) -> GatewayResult:
        import anthropic

        # list[Any]: the SDK accepts plain dict blocks; its param union is too
        # wide to spell out for the dynamic PDF/image/text mix we build.
        user_content: list[Any] = [
            {
                "type": "text",
                "text": (
                    "Case context (provided by the buying team):\n"
                    + json.dumps(case_context, indent=2, sort_keys=True)
                    + "\n\nThe supporting documents submitted for this audit follow. "
                    "Documents not attached here were requested but not received."
                ),
            },
            *content_blocks,
            {
                "type": "text",
                "text": (
                    "All documents have been provided above. Execute the full validation "
                    "protocol now and respond with the structured JSON report."
                ),
            },
        ]

        try:
            # Streaming keeps long audits (thinking + full report) inside HTTP
            # timeouts; the static system prompt is cached across audits.
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_output_tokens,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "high",
                    "format": {"type": "json_schema", "schema": REPORT_JSON_SCHEMA},
                },
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_content}],
            ) as stream:
                message = await stream.get_final_message()
        except anthropic.RateLimitError as exc:
            raise AuditFailedError(
                "The audit service is rate limited right now; retry in a minute."
            ) from exc
        except anthropic.APIStatusError as exc:
            raise AuditFailedError(f"The audit model returned an error: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AuditFailedError("Could not reach the audit model (network error).") from exc

        if message.stop_reason == "refusal":
            raise AuditFailedError(
                "The audit model declined to process this submission. Remove any "
                "unrelated sensitive content and retry, or escalate to Compliance."
            )
        if message.stop_reason == "max_tokens":
            raise AuditFailedError(
                "The report was truncated (too many documents in one submission). "
                "Split the submission and retry."
            )

        text = "".join(block.text for block in message.content if block.type == "text")
        try:
            findings = AgentFindings.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValueError) as exc:
            raise AuditFailedError("The audit model returned an unreadable report.") from exc
        return GatewayResult(findings=findings, model_id=message.model)


class StubAuditGateway:
    """Deterministic gateway for development and tests. No network, no key.

    It flags obvious tells in extracted text (so the UI can be demoed) and is
    intentionally conservative: it never returns LOW risk, because it has not
    actually verified anything.
    """

    model_id = "stub-audit-v0"

    async def run_audit(
        self, *, content_blocks: list[dict[str, Any]], case_context: dict[str, str]
    ) -> GatewayResult:
        text_corpus = " ".join(
            block["text"].lower() for block in content_blocks if block.get("type") == "text"
        )
        # Every submitted file contributes exactly one "Document N:" label block.
        n_docs = sum(
            1
            for block in content_blocks
            if block.get("type") == "text" and block["text"].startswith("Document ")
        )

        red_flags = [
            RedFlag(
                severity=Severity.HIGH,
                category="vendor-due-diligence",
                description=(
                    "Stub backend: vendor registration and brand authorization were not "
                    "verified against any external source."
                ),
                evidence="No live verification is performed by the stub gateway.",
            )
        ]
        rating = RiskRating.MEDIUM
        if "mixed garments" in text_corpus:
            red_flags.append(
                RedFlag(
                    severity=Severity.CRITICAL,
                    category="quantity-flow",
                    description=(
                        'Generic product description "mixed garments" prevents SKU-level '
                        "traceability across the chain."
                    ),
                    evidence='Uploaded document contains the description "mixed garments".',
                )
            )
            rating = RiskRating.HIGH

        received = [f"{s} (submitted)" for s in case_context.get("filenames", "").split("|") if s]
        missing = [
            MissingDocument(name=item["name"], why_needed=item["why_needed"])
            for item in STANDARD_DOCUMENT_CHECKLIST
        ]

        findings = AgentFindings(
            executive_summary=(
                f"Stub audit of {n_docs} submitted document(s) for vendor "
                f"'{case_context.get('vendor_name', 'unknown')}'. This canned report is for "
                "development only and reflects no real verification."
            ),
            sanitization_check=SanitizationCheck(
                status=CheckStatus.NOT_TESTABLE,
                findings=["Stub backend does not inspect redactions."],
            ),
            steps=[
                StepFinding(
                    step=i,
                    title=title,
                    status=CheckStatus.NOT_TESTABLE,
                    findings=["Not evaluated by the stub backend."],
                )
                for i, title in enumerate(_PROTOCOL_STEPS, start=1)
            ],
            chain_of_title=[
                ChainLink(
                    position=1,
                    entity=case_context.get("brand", "Brand owner"),
                    role="brand owner",
                    verified=False,
                    notes="Chain mapping requires the real audit backend.",
                ),
                ChainLink(
                    position=2,
                    entity=case_context.get("vendor_name", "Vendor"),
                    role="vendor to BFL",
                    verified=False,
                    notes="Chain mapping requires the real audit backend.",
                ),
            ],
            red_flags=red_flags,
            risk_rating=rating,
            risk_rationale=(
                "Stub backend cannot verify documents, vendors, or chain of title, so the "
                "submission is held for clarification by default."
            ),
            documents_received=received,
            documents_missing=missing,
            recommended_actions=[
                "Configure COMPLIANCE_AUDIT_BACKEND=anthropic to run the real protocol.",
                "Collect the full standard document set from the vendor before re-submitting.",
            ],
        )
        return GatewayResult(findings=findings, model_id=self.model_id)


def get_audit_gateway() -> AuditGateway:
    settings = get_settings()
    if settings.audit_backend == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "COMPLIANCE_AUDIT_BACKEND=anthropic requires COMPLIANCE_ANTHROPIC_API_KEY."
            )
        return AnthropicAuditGateway(
            api_key=settings.anthropic_api_key,
            model=settings.audit_model,
            max_output_tokens=settings.audit_max_output_tokens,
        )
    return StubAuditGateway()
