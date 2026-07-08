import pytest

from app.agent.gateway import StubAuditGateway, get_audit_gateway
from app.agent.protocol import STANDARD_DISCLAIMER
from app.agent.service import SubmissionError, run_audit, validate_submission
from app.config import get_settings
from app.schemas.audit import SIGNAL_FOR_RATING, SIGNAL_GUIDANCE, RiskRating, Signal
from tests.conftest import INVOICE_CSV, TINY_PDF


async def _audit(files: list[tuple[str, bytes]]):  # type: ignore[no-untyped-def]
    return await run_audit(
        StubAuditGateway(),
        files=files,
        case_reference="BFL-TEST-1",
        vendor_name="Acme Trading FZE",
        brand="ExampleBrand",
        product_category="apparel",
        notes="",
    )


async def test_report_always_carries_verbatim_disclaimer() -> None:
    report = await _audit([("invoice.pdf", TINY_PDF)])
    assert report.disclaimer == STANDARD_DISCLAIMER


async def test_signal_follows_risk_rating() -> None:
    report = await _audit([("invoice.pdf", TINY_PDF)])
    assert report.risk_rating is RiskRating.MEDIUM  # stub default
    assert report.signal is Signal.AMBER
    assert report.signal_guidance == SIGNAL_GUIDANCE[Signal.AMBER]


async def test_generic_descriptions_escalate_to_red() -> None:
    report = await _audit([("invoice.csv", INVOICE_CSV)])  # contains "mixed garments"
    assert report.risk_rating is RiskRating.HIGH
    assert report.signal is Signal.RED
    assert any(f.severity == "critical" for f in report.red_flags)


async def test_document_count_matches_submission() -> None:
    report = await _audit([("invoice.pdf", TINY_PDF), ("chain.csv", INVOICE_CSV)])
    assert "2 submitted document(s)" in report.executive_summary
    assert len(report.documents_analyzed) == 2


async def test_missing_documents_listed_for_step7() -> None:
    report = await _audit([("invoice.pdf", TINY_PDF)])
    names = [d.name.lower() for d in report.documents_missing]
    assert any("proof of payment" in n for n in names)
    assert any("bill of lading" in n for n in names)
    assert all(d.why_needed for d in report.documents_missing)


def test_rating_signal_mapping_is_total() -> None:
    assert SIGNAL_FOR_RATING[RiskRating.LOW] is Signal.GREEN
    assert SIGNAL_FOR_RATING[RiskRating.MEDIUM] is Signal.AMBER
    assert SIGNAL_FOR_RATING[RiskRating.HIGH] is Signal.RED
    assert set(SIGNAL_GUIDANCE) == set(Signal)


def test_submission_limits() -> None:
    settings = get_settings()
    with pytest.raises(SubmissionError, match="at least one"):
        validate_submission([])
    too_many = [(f"f{i}.pdf", b"%PDF-x") for i in range(settings.max_files_per_audit + 1)]
    with pytest.raises(SubmissionError, match="Too many files"):
        validate_submission(too_many)
    with pytest.raises(SubmissionError, match="per-file limit"):
        validate_submission([("huge.pdf", b"x" * (settings.max_file_bytes + 1))])


def test_gateway_factory_defaults_to_stub() -> None:
    assert isinstance(get_audit_gateway(), StubAuditGateway)


def test_anthropic_backend_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPLIANCE_AUDIT_BACKEND", "anthropic")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="COMPLIANCE_ANTHROPIC_API_KEY"):
        get_audit_gateway()
