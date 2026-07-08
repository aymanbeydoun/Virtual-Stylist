from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from app.agent.checklist import STANDARD_DOCUMENT_CHECKLIST
from app.agent.gateway import AuditFailedError, AuditGateway, get_audit_gateway
from app.agent.service import SubmissionError, run_audit
from app.config import get_settings
from app.schemas.audit import AuditReport

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "audit_backend": settings.audit_backend}


@router.get("/checklist")
async def checklist() -> list[dict[str, str]]:
    """The standard document requirement list (shown in the UI up front)."""
    return STANDARD_DOCUMENT_CHECKLIST


@router.post("/audits", response_model=AuditReport)
async def create_audit(
    files: list[UploadFile],
    gateway: Annotated[AuditGateway, Depends(get_audit_gateway)],
    case_reference: Annotated[str, Form()] = "",
    vendor_name: Annotated[str, Form()] = "",
    brand: Annotated[str, Form()] = "",
    product_category: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
) -> AuditReport:
    payload: list[tuple[str, bytes]] = []
    for upload in files:
        data = await upload.read()
        payload.append((upload.filename or "unnamed-file", data))

    try:
        report = await run_audit(
            gateway,
            files=payload,
            case_reference=case_reference.strip(),
            vendor_name=vendor_name.strip(),
            brand=brand.strip(),
            product_category=product_category.strip(),
            notes=notes.strip(),
        )
    except SubmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AuditFailedError as exc:
        logger.error("audit_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    logger.info(
        "audit_completed",
        case_reference=report.case_reference,
        vendor=report.vendor_name,
        risk_rating=report.risk_rating,
        signal=report.signal,
        documents=len(report.documents_analyzed),
        model_id=report.model_id,
    )
    return report
