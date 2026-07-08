"""Verdict contract between the Senior Auditor AI and the build."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class CheckName(StrEnum):
    DEFECT_DETECTION = "defect_detection"
    RATING_CONSISTENCY = "rating_consistency"
    MATH_RECONCILIATION = "math_reconciliation"
    HALLUCINATION_SCREEN = "hallucination_screen"


class CheckResult(BaseModel):
    check: CheckName
    status: str  # "pass" | "fail"
    details: str


class GradingFailure(BaseModel):
    check: CheckName
    defect_key: str  # seeded defect key, or "-" when not defect-specific
    explanation: str
    dashboard_evidence: str


class AuditorVerdict(BaseModel):
    verdict: str  # "PASS" | "FAIL"
    checks: list[CheckResult]
    failures: list[GradingFailure]
    summary: str

    @property
    def failed(self) -> bool:
        return self.verdict != "PASS"


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


_CHECK_ENUM = {"type": "string", "enum": [c.value for c in CheckName]}

VERDICT_JSON_SCHEMA: dict[str, Any] = _obj(
    {
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "checks": {
            "type": "array",
            "items": _obj(
                {
                    "check": _CHECK_ENUM,
                    "status": {"type": "string", "enum": ["pass", "fail"]},
                    "details": {"type": "string"},
                }
            ),
        },
        "failures": {
            "type": "array",
            "items": _obj(
                {
                    "check": _CHECK_ENUM,
                    "defect_key": {"type": "string"},
                    "explanation": {"type": "string"},
                    "dashboard_evidence": {"type": "string"},
                }
            ),
        },
        "summary": {"type": "string"},
    }
)
