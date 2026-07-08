"""Orchestrates an audit: intake -> gateway -> assembled report.

The disclaimer and the traffic-light signal are attached here, server-side,
so neither ever depends on model output.
"""
from __future__ import annotations

from app.agent.documents import DocumentBundle, UnsupportedDocumentError, build_document_bundle
from app.agent.gateway import AuditGateway
from app.agent.protocol import STANDARD_DISCLAIMER
from app.config import get_settings
from app.schemas.audit import (
    SIGNAL_FOR_RATING,
    SIGNAL_GUIDANCE,
    AuditReport,
)


class SubmissionError(Exception):
    """The submission itself is invalid (bad files / limits exceeded)."""


def validate_submission(files: list[tuple[str, bytes]]) -> None:
    settings = get_settings()
    if not files:
        raise SubmissionError("Upload at least one document to audit.")
    if len(files) > settings.max_files_per_audit:
        raise SubmissionError(
            f"Too many files: {len(files)} uploaded, limit is "
            f"{settings.max_files_per_audit} per audit."
        )
    total = 0
    for filename, data in files:
        if len(data) > settings.max_file_bytes:
            raise SubmissionError(
                f"{filename} is {len(data) / 1_048_576:.1f} MB; the per-file limit is "
                f"{settings.max_file_bytes / 1_048_576:.0f} MB."
            )
        total += len(data)
    if total > settings.max_total_bytes:
        raise SubmissionError(
            f"The upload totals {total / 1_048_576:.1f} MB; the per-audit limit is "
            f"{settings.max_total_bytes / 1_048_576:.0f} MB. Split the submission."
        )


async def run_audit(
    gateway: AuditGateway,
    *,
    files: list[tuple[str, bytes]],
    case_reference: str,
    vendor_name: str,
    brand: str,
    product_category: str,
    notes: str,
) -> AuditReport:
    validate_submission(files)
    try:
        bundle: DocumentBundle = build_document_bundle(files)
    except UnsupportedDocumentError as exc:
        raise SubmissionError(str(exc)) from exc

    case_context = {
        "case_reference": case_reference or "not provided",
        "vendor_name": vendor_name or "not provided",
        "brand": brand or "not provided",
        "product_category": product_category or "not provided",
        "buyer_notes": notes or "none",
        "filenames": "|".join(s.filename for s in bundle.summaries),
    }

    result = await gateway.run_audit(
        content_blocks=bundle.blocks, case_context=case_context
    )
    findings = result.findings
    signal = SIGNAL_FOR_RATING[findings.risk_rating]

    return AuditReport(
        case_reference=case_reference,
        vendor_name=vendor_name,
        brand=brand,
        product_category=product_category,
        risk_rating=findings.risk_rating,
        signal=signal,
        signal_guidance=SIGNAL_GUIDANCE[signal],
        executive_summary=findings.executive_summary,
        sanitization_check=findings.sanitization_check,
        steps=findings.steps,
        chain_of_title=findings.chain_of_title,
        red_flags=findings.red_flags,
        risk_rationale=findings.risk_rationale,
        documents_received=findings.documents_received,
        documents_missing=findings.documents_missing,
        recommended_actions=findings.recommended_actions,
        documents_analyzed=bundle.summaries,
        model_id=result.model_id,
        disclaimer=STANDARD_DISCLAIMER,
    )
