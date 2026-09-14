from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.cdas_booking import CdasBookingOpportunity
from database.session import get_db
from services.cdas_booking_calendar import build_booking_calendar
from services.cdas_booking_monitor import local_today, serialize_opportunity
from services.cdas_booking_priority import build_booking_priority_queue
from services.cdas_booking_storage import dedupe_serialized_opportunities
from services.cdas_max_loan_calculator import calculate_reference_max_principal
from services.cdas_what_if_simulator import simulate_what_if

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Booking Calendar"])


class CdasWhatIfRequest(BaseModel):
    opportunity_id: UUID
    proposed_installment: float | None = Field(default=None, gt=0, le=999_999_999)
    proposed_amount: float | None = Field(default=None, gt=0, le=999_999_999)
    term_months: int | None = Field(default=None, ge=1, le=240)
    annual_interest_rate: float | None = Field(default=None, ge=0, le=500)


class CdasMaxLoanRequest(BaseModel):
    monthly_capacity: float = Field(ge=0, le=999_999_999)
    term_months: int = Field(ge=1, le=240)
    annual_interest_rate: float = Field(ge=0, le=500)
    monthly_service_fee: float = Field(default=0, ge=0, le=999_999_999)
    insurance_percent: float = Field(default=0, ge=0, le=500)


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _company_opportunities(context: TenantContext, db: Session) -> list[dict]:
    rows = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(
        CdasBookingOpportunity.booking_open_date.asc().nullslast(),
        CdasBookingOpportunity.created_at.desc(),
    ).all()
    return dedupe_serialized_opportunities(
        [serialize_opportunity(row) for row in rows]
    )


def _company_opportunity_or_404(
    *,
    opportunity_id: UUID,
    context: TenantContext,
    db: Session,
) -> CdasBookingOpportunity:
    row = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.id == opportunity_id,
        CdasBookingOpportunity.company_id == context.company_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="CDAS booking opportunity not found")
    return row


@router.get("/calendar")
def get_cdas_booking_calendar(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return the tenant's automatically calculated CDAS booking calendar."""
    _require_company_member(context)
    opportunities = _company_opportunities(context, db)
    return build_booking_calendar(opportunities, today=local_today())


@router.get("/priorities")
def get_cdas_booking_priorities(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return an explainable, tenant-scoped 0-100 priority queue."""
    _require_company_member(context)
    opportunities = _company_opportunities(context, db)
    return build_booking_priority_queue(opportunities, today=local_today())


@router.post("/simulator")
def simulate_cdas_what_if(
    payload: CdasWhatIfRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Simulate a proposed installment against one saved tenant CDAS opportunity."""
    _require_company_member(context)
    row = _company_opportunity_or_404(
        opportunity_id=payload.opportunity_id,
        context=context,
        db=db,
    )

    try:
        return simulate_what_if(
            opportunity=serialize_opportunity(row),
            today=local_today(),
            proposed_installment=payload.proposed_installment,
            proposed_amount=payload.proposed_amount,
            term_months=payload.term_months,
            annual_interest_rate=payload.annual_interest_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/loan-capacity")
def calculate_cdas_max_loan_reference(
    payload: CdasMaxLoanRequest,
    context: TenantContext = Depends(get_tenant_context),
):
    """Return reference-only loan arithmetic from staff-entered values."""
    _require_company_member(context)
    try:
        return calculate_reference_max_principal(
            monthly_capacity=payload.monthly_capacity,
            term_months=payload.term_months,
            annual_interest_rate=payload.annual_interest_rate,
            monthly_service_fee=payload.monthly_service_fee,
            insurance_percent=payload.insurance_percent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
