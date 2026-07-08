"""Typed report structures for the compliance audit."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RiskRating(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Signal(StrEnum):
    """Traffic-light signal shown front and center on the dashboard."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


SIGNAL_FOR_RATING: dict[RiskRating, Signal] = {
    RiskRating.LOW: Signal.GREEN,
    RiskRating.MEDIUM: Signal.AMBER,
    RiskRating.HIGH: Signal.RED,
}

SIGNAL_GUIDANCE: dict[Signal, str] = {
    Signal.GREEN: "Approve — proceed with the purchase.",
    Signal.AMBER: (
        "Approve with conditions / hold — the buying team collectively discusses "
        "the gaps below and takes a call."
    ),
    Signal.RED: (
        "Escalate to Compliance / reject — do not proceed until the red flags "
        "below are resolved."
    ),
}


class CheckStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    NOT_TESTABLE = "not_testable"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SanitizationCheck(BaseModel):
    status: CheckStatus
    findings: list[str]


class StepFinding(BaseModel):
    step: int
    title: str
    status: CheckStatus
    findings: list[str]


class RedFlag(BaseModel):
    severity: Severity
    category: str
    description: str
    evidence: str


class ChainLink(BaseModel):
    position: int
    entity: str
    role: str
    verified: bool
    notes: str


class MissingDocument(BaseModel):
    name: str
    why_needed: str


class AgentFindings(BaseModel):
    """What the model returns via structured output — everything except the
    server-owned fields (signal, guidance, disclaimer)."""

    executive_summary: str
    sanitization_check: SanitizationCheck
    steps: list[StepFinding]
    chain_of_title: list[ChainLink]
    red_flags: list[RedFlag]
    risk_rating: RiskRating
    risk_rationale: str
    documents_received: list[str]
    documents_missing: list[MissingDocument]
    recommended_actions: list[str]


class DocumentSummary(BaseModel):
    filename: str
    kind: str
    size_bytes: int
    note: str = ""


class AuditReport(BaseModel):
    """Full report returned by the API and rendered by the dashboard."""

    case_reference: str
    vendor_name: str
    brand: str
    product_category: str

    risk_rating: RiskRating
    signal: Signal
    signal_guidance: str

    executive_summary: str
    sanitization_check: SanitizationCheck
    steps: list[StepFinding]
    chain_of_title: list[ChainLink]
    red_flags: list[RedFlag]
    risk_rationale: str
    documents_received: list[str]
    documents_missing: list[MissingDocument]
    recommended_actions: list[str]

    documents_analyzed: list[DocumentSummary]
    model_id: str
    disclaimer: str = Field(description="Mandatory Audit & Compliance disclaimer, verbatim.")
