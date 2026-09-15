from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.config.config import settings
from database.models.cdas_booking import (
    CdasAnalysisRecord,
    CdasBookingFailure,
    CdasBookingOpportunity,
    CdasOpportunityContact,
)
from database.session import get_db
from services.cdas_booking_calendar import build_booking_calendar
from services.cdas_booking_failures import build_failure_workspace
from services.cdas_booking_monitor import local_today, serialize_opportunity
from services.cdas_booking_priority import build_booking_priority_queue
from services.cdas_booking_storage import dedupe_serialized_opportunities
from services.cdas_change_detection import build_change_detection
from services.cdas_client_profiles import build_client_profiles
from services.cdas_contact_followups import build_follow_up_workspace
from services.cdas_data_quality import build_data_quality_centre
from services.cdas_duplicate_detection import build_duplicate_detection
from services.cdas_forecast import build_cdas_forecast
from services.cdas_management_dashboard import build_management_dashboard
from services.cdas_opportunity_pipeline import build_opportunity_pipeline

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Management Dashboard"])


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).replace(tzinfo=None)


@router.get("/management-dashboard")
def get_cdas_management_dashboard(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return aggregate company-scoped CDAS operating intelligence for management review."""
    _require_company_member(context)
    today = local_today()
    now = _now()

    opportunity_rows = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(CdasBookingOpportunity.created_at.desc()).all()
    opportunities = dedupe_serialized_opportunities(
        [serialize_opportunity(row, today=today) for row in opportunity_rows]
    )
    calendar_opportunities = [
        item for item in opportunities if str(item.get("state") or "").upper() != "FAILED"
    ]

    analyses = db.query(CdasAnalysisRecord).filter(
        CdasAnalysisRecord.company_id == context.company_id
    ).order_by(CdasAnalysisRecord.created_at.desc()).all()
    profiles = build_client_profiles(analyses, [], include_detail=True)

    contacts = db.query(CdasOpportunityContact).filter(
        CdasOpportunityContact.company_id == context.company_id
    ).order_by(CdasOpportunityContact.contacted_at.desc()).all()
    failure_rows = db.query(CdasBookingFailure).filter(
        CdasBookingFailure.company_id == context.company_id
    ).order_by(CdasBookingFailure.failed_at.desc()).all()

    calendar = build_booking_calendar(calendar_opportunities, today=today)
    priorities = build_booking_priority_queue(calendar_opportunities, today=today)
    pipeline = build_opportunity_pipeline(opportunities)
    followups = build_follow_up_workspace(opportunities, contacts, now=now)
    failures = build_failure_workspace(opportunities, failure_rows, now=now)
    quality = build_data_quality_centre(profiles)
    duplicates = build_duplicate_detection(profiles)
    changes = build_change_detection(analyses)
    forecast = build_cdas_forecast(profiles, today=today, horizon_months=12)

    return build_management_dashboard(
        calendar=calendar,
        priorities=priorities,
        pipeline=pipeline,
        followups=followups,
        failures=failures,
        quality=quality,
        duplicates=duplicates,
        changes=changes,
        forecast=forecast,
    )
