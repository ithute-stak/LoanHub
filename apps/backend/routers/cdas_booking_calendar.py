from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.cdas_booking import CdasBookingOpportunity
from database.session import get_db
from services.cdas_booking_calendar import build_booking_calendar
from services.cdas_booking_monitor import local_today, serialize_opportunity
from services.cdas_booking_storage import dedupe_serialized_opportunities

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Booking Calendar"])


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


@router.get("/calendar")
def get_cdas_booking_calendar(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return the tenant's automatically calculated CDAS booking calendar."""
    _require_company_member(context)
    rows = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(
        CdasBookingOpportunity.booking_open_date.asc().nullslast(),
        CdasBookingOpportunity.created_at.desc(),
    ).all()
    opportunities = dedupe_serialized_opportunities(
        [serialize_opportunity(row) for row in rows]
    )
    return build_booking_calendar(opportunities, today=local_today())
