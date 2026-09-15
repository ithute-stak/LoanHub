from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.config.config import settings
from database.models.cdas_booking import CdasBookingFailure, CdasBookingOpportunity, CdasOpportunityContact
from database.models.company_staff import CompanyStaff
from database.session import get_db
from services.cdas_booking_failures import serialize_failure
from services.cdas_booking_monitor import serialize_opportunity
from services.cdas_booking_storage import dedupe_serialized_opportunities
from services.cdas_contact_followups import serialize_contact
from services.cdas_officer_performance import build_officer_performance

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Officer Performance"])


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).replace(tzinfo=None)


def _staff_payload(row: CompanyStaff) -> dict:
    user = row.user
    person = getattr(user, "person", None) if user else None
    name = str(getattr(person, "full_name", "") or "").strip()
    if not name and user:
        name = str(user.email or user.phone or "").strip()
    return {
        "user_id": str(row.user_id),
        "name": name or "Company staff",
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "role": getattr(row.role, "value", str(row.role)),
        "is_active": bool(row.is_active),
    }


@router.get("/officer-performance")
def get_cdas_officer_performance(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return transparent company-scoped CDAS workload and workflow activity by officer."""
    _require_company_member(context)

    rows = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(CdasBookingOpportunity.created_at.desc()).all()
    opportunities = []
    for row in rows:
        item = serialize_opportunity(row)
        item["assigned_to_user_id"] = str(row.assigned_to_user_id) if row.assigned_to_user_id else None
        opportunities.append(item)
    opportunities = dedupe_serialized_opportunities(opportunities)

    contacts = db.query(CdasOpportunityContact).filter(
        CdasOpportunityContact.company_id == context.company_id
    ).order_by(CdasOpportunityContact.contacted_at.desc()).all()
    failures = db.query(CdasBookingFailure).filter(
        CdasBookingFailure.company_id == context.company_id
    ).order_by(CdasBookingFailure.failed_at.desc()).all()
    staff = db.query(CompanyStaff).filter(
        CompanyStaff.company_id == context.company_id
    ).order_by(CompanyStaff.is_active.desc(), CompanyStaff.created_at.asc()).all()

    return build_officer_performance(
        [_staff_payload(row) for row in staff],
        opportunities,
        [serialize_contact(row) for row in contacts],
        [serialize_failure(row) for row in failures],
        now=_now(),
    )
