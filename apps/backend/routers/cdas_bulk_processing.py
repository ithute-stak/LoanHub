from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.session import get_db
from routers.cdas_booking import CdasBookingAnalyseRequest, _analyze, _report_preparer
from services.cdas_analysis_history import save_or_get_analysis_record
from services.cdas_bulk_processing import (
    build_bulk_error_item,
    build_bulk_result_item,
    build_bulk_summary,
)

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Bulk Processing"])

MAX_BULK_ITEMS = 25
MAX_BULK_RAW_TEXT_CHARS = 1_000_000


class CdasBulkAnalyzeRequest(BaseModel):
    items: list[CdasBookingAnalyseRequest] = Field(min_length=1, max_length=MAX_BULK_ITEMS)


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


@router.post("/bulk-analyze")
def bulk_analyze_cdas(
    payload: CdasBulkAnalyzeRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Analyze and archive multiple CDAS records without auto-creating booking opportunities."""
    _require_company_member(context)

    total_raw_chars = sum(len(item.raw_text or "") for item in payload.items)
    if total_raw_chars > MAX_BULK_RAW_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail="The combined CDAS batch is too large. Split it into smaller batches.",
        )

    prepared_by, prepared_by_role = _report_preparer(context)
    results: list[dict] = []

    for index, item in enumerate(payload.items, start=1):
        try:
            analysis = jsonable_encoder(_analyze(item))
            record, created = save_or_get_analysis_record(
                db,
                company_id=context.company_id,
                analyzed_by_user_id=context.user.id,
                analyzed_by_name=prepared_by,
                analyzed_by_role=prepared_by_role,
                client_name=item.client_name,
                client_reference=item.client_reference,
                analysis=analysis,
            )
            results.append(
                build_bulk_result_item(
                    index=index,
                    client_name=item.client_name,
                    client_reference=item.client_reference,
                    analysis=analysis,
                    analysis_id=str(record.id),
                    archived_new=created,
                )
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "CDAS analysis failed"
            results.append(
                build_bulk_error_item(
                    index=index,
                    client_name=item.client_name,
                    client_reference=item.client_reference,
                    error=detail,
                )
            )

    return {
        "summary": build_bulk_summary(results),
        "items": results,
    }
