from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.config.config import settings
from database.models.cdas_booking import CdasBookingFailure, CdasBookingOpportunity
from database.session import get_db
from services.cdas_booking_failures import (
    build_failure_workspace,
    record_booking_failure,
    reopen_failed_opportunity,
    serialize_failure,
)
from services.cdas_booking_monitor import serialize_opportunity
from services.cdas_booking_storage import dedupe_serialized_opportunities

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Booking Failures"])


class CdasBookingFailureRequest(BaseModel):
    reason_code: str
    reason_details: str | None = Field(default=None, max_length=4000)
    failed_at: datetime | None = None
    retry_eligible: bool = False
    retry_after: datetime | None = None


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).replace(tzinfo=None)


def _company_opportunity(
    db: Session,
    *,
    opportunity_id: UUID,
    company_id: UUID,
) -> CdasBookingOpportunity:
    item = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.id == opportunity_id,
        CdasBookingOpportunity.company_id == company_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="CDAS booking opportunity not found")
    return item


def _latest_failure(
    db: Session,
    *,
    opportunity_id: UUID,
    company_id: UUID,
) -> CdasBookingFailure | None:
    return db.query(CdasBookingFailure).filter(
        CdasBookingFailure.company_id == company_id,
        CdasBookingFailure.opportunity_id == opportunity_id,
    ).order_by(
        CdasBookingFailure.failed_at.desc(),
        CdasBookingFailure.created_at.desc(),
    ).first()


@router.get("/failures")
def get_cdas_booking_failures(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    rows = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(CdasBookingOpportunity.created_at.desc()).all()
    opportunities = dedupe_serialized_opportunities(
        [serialize_opportunity(row) for row in rows]
    )
    failures = db.query(CdasBookingFailure).filter(
        CdasBookingFailure.company_id == context.company_id
    ).order_by(
        CdasBookingFailure.failed_at.desc(),
        CdasBookingFailure.created_at.desc(),
    ).all()
    return build_failure_workspace(opportunities, failures, now=_now())


@router.post("/opportunities/{opportunity_id}/failures")
def create_cdas_booking_failure(
    opportunity_id: UUID,
    payload: CdasBookingFailureRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    item = _company_opportunity(
        db,
        opportunity_id=opportunity_id,
        company_id=context.company_id,
    )
    now = _now()
    failed_at = payload.failed_at or now
    if failed_at > now:
        raise HTTPException(status_code=422, detail="Failure time cannot be in the future")
    try:
        row = record_booking_failure(
            db,
            item=item,
            company_id=context.company_id,
            user_id=context.user.id,
            reason_code=payload.reason_code,
            reason_details=payload.reason_details,
            failed_at=failed_at,
            retry_eligible=payload.retry_eligible,
            retry_after=payload.retry_after,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_failure(row)


@router.get("/opportunities/{opportunity_id}/failures")
def list_cdas_booking_failure_history(
    opportunity_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    _company_opportunity(
        db,
        opportunity_id=opportunity_id,
        company_id=context.company_id,
    )
    rows = db.query(CdasBookingFailure).filter(
        CdasBookingFailure.company_id == context.company_id,
        CdasBookingFailure.opportunity_id == opportunity_id,
    ).order_by(
        CdasBookingFailure.failed_at.desc(),
        CdasBookingFailure.created_at.desc(),
    ).all()
    return {"items": [serialize_failure(row) for row in rows], "total": len(rows)}


@router.post("/opportunities/{opportunity_id}/retry-failed")
def retry_failed_cdas_booking(
    opportunity_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    item = _company_opportunity(
        db,
        opportunity_id=opportunity_id,
        company_id=context.company_id,
    )
    latest = _latest_failure(
        db,
        opportunity_id=opportunity_id,
        company_id=context.company_id,
    )
    try:
        reopened = reopen_failed_opportunity(
            db,
            item=item,
            latest_failure=latest,
            user_id=context.user.id,
            now=_now(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_opportunity(reopened)
