"""Opt-in, authenticated, read-only analysis of existing managed borrower evidence.

No new file upload route, no record writes and no lending decisions. Deployment
must explicitly enable this experimental endpoint after acceptance testing.
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, TenantContext, get_user_context
from database.models.file_management import ManagedFile
from database.session import get_db
from services.file_service import can_access_file, read_file_bytes
from services.document_intelligence_foundation import DocumentKind
from services.document_intelligence_reader import (
    DocumentReadError,
    MAX_INPUT_BYTES,
    read_document,
)
from services.government_payslip_stamp_preview import preview_payslip_stamp
from services.nedbank_statement_adapter import (
    NedbankStatementError, parse_nedbank_native_pdf,
)

router = APIRouter(prefix="/document-intelligence", tags=["Document Intelligence"])
_ALLOWED_CATEGORIES = {"borrower_payslip", "borrower_bank_statement"}


def _enabled() -> bool:
    return os.getenv("LOANHUB_DOCUMENT_INTELLIGENCE_ENABLED", "false").lower() == "true"


def _authorize(
    *, context: TenantContext, record: ManagedFile | None, db: Session
) -> None:
    """No cross-tenant, personal, shared-chat, or platform-wide bypass."""
    if not context.company_id or not context.staff or context.staff.role not in LENDING_ROLES:
        raise HTTPException(status_code=403, detail="Company lending access required")
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    if record.company_id != context.company_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if record.category not in _ALLOWED_CATEGORIES or not record.is_confidential:
        raise HTTPException(status_code=404, detail="Document not found")
    if record.scan_status != "clean" or not can_access_file(db, context, record):
        raise HTTPException(status_code=404, detail="Document not found")


@router.post("/managed-files/{file_id}/review")
def review_managed_document(
    file_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Preview extraction metadata only; no extracted personal text is returned."""
    if not _enabled():
        raise HTTPException(status_code=404, detail="Document analysis unavailable")
    record = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    _authorize(context=context, record=record, db=db)
    if record.size_bytes and record.size_bytes > MAX_INPUT_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds analysis limit")
    try:
        contents = read_file_bytes(record)
        if len(contents) > MAX_INPUT_BYTES:
            raise HTTPException(status_code=413, detail="Document exceeds analysis limit")
        result = read_document(contents, filename=record.original_name)
    except DocumentReadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # No OCR transcript or account/identity information in this initial route.
    response = {
        "file_id": str(file_id),
        "document_type": result.classification.value,
        "pages": len(result.pages),
        "review_required": True,
        "auto_approval_allowed": False,
        "page_reviews": [
            {"page": page.page_number,
             "orientation_correction": page.orientation_correction,
             "ocr_confidence": page.confidence,
             "review_required": page.review_required}
            for page in result.pages
        ],
        "checks": {"issuer_authenticity": "unverified"},
    }
    if result.classification == DocumentKind.BANK_STATEMENT and record.category == "borrower_bank_statement":
        try:
            statement = parse_nedbank_native_pdf(contents)
        except (NedbankStatementError, DocumentReadError):
            response["checks"]["bank_reconciliation"] = "manual_review"
        else:
            response["checks"]["bank_reconciliation"] = (
                "arithmetic_reconciled" if statement.reconciled else "manual_review"
            )
            response["checks"]["financial_transaction_count"] = len(statement.rows)
    if record.category == "borrower_payslip":
        response["checks"]["payslip_financials"] = "manual_review"
        response["checks"]["payslip_financial_reason"] = "itemised_scan_reconciliation_pending"
        try:
            local_today = datetime.now(ZoneInfo("Africa/Maseru")).date()
            preview = preview_payslip_stamp(
                contents, record.original_name, assessed_at=local_today,
            )
        except (DocumentReadError, ValueError):
            response["checks"]["stamp"] = "manual_review"
            response["checks"]["stamp_review_reasons"] = ["stamp_evidence_processing_failed"]
        else:
            response["checks"]["stamp"] = preview.status
            response["checks"]["stamp_date"] = preview.detected_stamp_date
            response["checks"]["stamp_candidates"] = preview.candidate_region_count
            response["checks"]["stamp_review_reasons"] = list(preview.review_reasons)
    return response
