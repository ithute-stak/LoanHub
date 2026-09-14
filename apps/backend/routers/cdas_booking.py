from __future__ import annotations

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.config.config import settings
from database.models.cdas_booking import CdasBookingOpportunity
from database.session import get_db
from services.cdas_booking_analyzer import analyse_cdas_booking, parse_cdas_screen_context
from services.cdas_booking_autofill import parse_cdas_autofill_context
from services.cdas_booking_monitor import local_today, serialize_opportunity
from services.cdas_booking_policy import apply_capacity_booking_policy
from services.cdas_booking_storage import (
    dedupe_serialized_opportunities,
    save_or_update_opportunity_from_analysis,
)

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Booking Analyzer"])


class CdasBookingAnalyseRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=100_000)
    booking_lead_months: int = Field(default=6, ge=0, le=60)
    own_item_codes: list[str] = Field(default_factory=list)
    own_agency_names: list[str] = Field(default_factory=list)
    amount_owing: float | None = Field(default=None, gt=0, le=999_999_999)
    as_of: date | None = None


class CdasBookingMonitorRequest(CdasBookingAnalyseRequest):
    client_name: str | None = Field(default=None, max_length=200)
    client_reference: str | None = Field(default=None, max_length=200)
    alert_lead_days: int = Field(default=3, ge=0, le=31)


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _analyze(payload: CdasBookingAnalyseRequest) -> dict:
    as_of = payload.as_of or datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    try:
        screen_context = parse_cdas_screen_context(payload.raw_text, as_of=as_of)
        autofill_context = parse_cdas_autofill_context(payload.raw_text)

        screen_application = screen_context.get("application_context") or {}
        autofill_application = autofill_context.get("application_context") or {}
        detected_agency_code = (
            autofill_application.get("new_deduction_agency_code")
            or screen_application.get("new_deduction_agency_code")
        )
        detected_agency_name = (
            autofill_application.get("new_deduction_agency_name")
            or screen_application.get("new_deduction_agency_name")
        )

        own_agency_names = list(payload.own_agency_names)
        if detected_agency_name and detected_agency_name not in own_agency_names:
            own_agency_names.append(detected_agency_name)

        analysis = analyse_cdas_booking(
            payload.raw_text,
            as_of=as_of,
            booking_lead_months=payload.booking_lead_months,
            own_item_codes=payload.own_item_codes,
            own_agency_names=own_agency_names,
        )

        robust_profile = autofill_context.get("profile") or {}
        analysis_profile = analysis.setdefault("profile", {})
        for key, value in robust_profile.items():
            if value:
                analysis_profile[key] = value

        analysis_application_context = analysis.setdefault("application_context", {})
        if autofill_application.get("new_deduction_agency_code"):
            analysis_application_context["new_deduction_agency_code"] = autofill_application[
                "new_deduction_agency_code"
            ]
        if autofill_application.get("new_deduction_agency_name"):
            analysis_application_context["new_deduction_agency_name"] = autofill_application[
                "new_deduction_agency_name"
            ]
        analysis_application_context["current_cdas_agency_code"] = detected_agency_code
        analysis_application_context["current_cdas_agency_name"] = detected_agency_name
        analysis_application_context["agency_auto_detected"] = bool(detected_agency_name)

        return apply_capacity_booking_policy(
            analysis,
            as_of=as_of,
            amount_owing=payload.amount_owing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/analyze")
def analyze_cdas_booking(payload: CdasBookingAnalyseRequest, context: TenantContext = Depends(get_tenant_context)):
    _require_company_member(context)
    return _analyze(payload)


@router.post("/opportunities")
def save_cdas_booking_opportunity(
    payload: CdasBookingMonitorRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    analysis = jsonable_encoder(_analyze(payload))
    if analysis.get("decision") == "REVIEW_REQUIRED":
        raise HTTPException(
            status_code=422,
            detail="This CDAS analysis contains Active deduction data that cannot be used safely for booking timing. Correct or verify the flagged row before saving a booking monitor.",
        )
    item = save_or_update_opportunity_from_analysis(
        db,
        company_id=context.company_id,
        client_name=payload.client_name,
        client_reference=payload.client_reference,
        alert_lead_days=payload.alert_lead_days,
        analysis=analysis,
    )
    if item.status == "booked":
        item.booked_by_user_id = context.user.id
        db.commit()
        db.refresh(item)
    return serialize_opportunity(item)


@router.get("/opportunities")
def list_cdas_booking_opportunities(
    state: str | None = Query(default=None),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    items = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(CdasBookingOpportunity.booking_open_date.asc().nullslast(), CdasBookingOpportunity.created_at.desc()).all()
    values = dedupe_serialized_opportunities([serialize_opportunity(item) for item in items])
    if state:
        wanted = state.upper()
        values = [item for item in values if item["state"] == wanted]
    return {"items": values, "total": len(values)}


@router.patch("/opportunities/{opportunity_id}/booked")
def mark_cdas_booking_opportunity_booked(
    opportunity_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    item = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.id == opportunity_id,
        CdasBookingOpportunity.company_id == context.company_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="CDAS booking opportunity not found")
    if item.status != "booked":
        item.status = "booked"
        item.booked_at = datetime.utcnow()
        item.booked_by_user_id = context.user.id
        db.commit()
        db.refresh(item)
    return serialize_opportunity(item, today=local_today())
