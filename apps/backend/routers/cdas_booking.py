from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.config.config import settings
from database.models.cdas_booking_monitor import CdasBookingMonitor
from database.models.notification import Notification
from database.session import get_db
from services.cdas_booking_analyzer import analyse_cdas_booking
from services.cdas_booking_monitor import booking_window_dates, monitor_to_dict


router = APIRouter(prefix="/cdas-booking", tags=["CDAS Booking Analyzer"])


class CdasBookingAnalyseRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=100_000)
    booking_lead_months: int = Field(default=6, ge=0, le=60)
    own_item_codes: list[str] = Field(default_factory=list)
    own_agency_names: list[str] = Field(default_factory=list)
    as_of: date | None = None


class CdasBookingMonitorCreate(BaseModel):
    client_name: str = Field(min_length=2, max_length=200)
    client_reference: str | None = Field(default=None, max_length=120)
    item_code: str = Field(min_length=1, max_length=80)
    agency_name: str = Field(min_length=1, max_length=255)
    deduction_amount: Decimal = Field(ge=0)
    effective_date: date
    expiry_date: date
    reference_no: str | None = Field(default=None, max_length=255)
    source_status: str = Field(default="Active", max_length=80)
    booking_lead_months: int = Field(default=6, ge=0, le=60)


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


@router.post("/analyze")
def analyze_cdas_booking(
    payload: CdasBookingAnalyseRequest,
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_member(context)
    as_of = payload.as_of or datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    try:
        return analyse_cdas_booking(
            payload.raw_text,
            as_of=as_of,
            booking_lead_months=payload.booking_lead_months,
            own_item_codes=payload.own_item_codes,
            own_agency_names=payload.own_agency_names,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/monitors")
def list_cdas_booking_monitors(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    today = datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    rows = (
        db.query(CdasBookingMonitor)
        .filter(CdasBookingMonitor.company_id == context.company_id)
        .order_by(CdasBookingMonitor.booked_at.asc().nullsfirst(), CdasBookingMonitor.booking_open_date.asc())
        .all()
    )
    return [monitor_to_dict(row, as_of=today) for row in rows]


@router.post("/monitors", status_code=201)
def create_cdas_booking_monitor(
    payload: CdasBookingMonitorCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    duplicate = (
        db.query(CdasBookingMonitor)
        .filter(
            CdasBookingMonitor.company_id == context.company_id,
            CdasBookingMonitor.reference_no == payload.reference_no,
            CdasBookingMonitor.expiry_date == payload.expiry_date,
            CdasBookingMonitor.booked_at.is_(None),
        )
        .first()
    )
    if duplicate and payload.reference_no:
        raise HTTPException(status_code=409, detail="This CDAS opportunity is already being monitored")

    booking_open, alert_start = booking_window_dates(payload.expiry_date, payload.booking_lead_months)
    row = CdasBookingMonitor(
        company_id=context.company_id,
        client_name=payload.client_name.strip(),
        client_reference=(payload.client_reference or "").strip() or None,
        item_code=payload.item_code.strip(),
        agency_name=payload.agency_name.strip(),
        deduction_amount=payload.deduction_amount,
        effective_date=payload.effective_date,
        expiry_date=payload.expiry_date,
        reference_no=(payload.reference_no or "").strip() or None,
        source_status=payload.source_status.strip() or "Active",
        booking_lead_months=payload.booking_lead_months,
        booking_open_date=booking_open,
        alert_start_date=alert_start,
        created_by_user_id=context.staff.user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return monitor_to_dict(row)


@router.patch("/monitors/{monitor_id}/booked")
def mark_cdas_booking_monitor_booked(
    monitor_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    row = (
        db.query(CdasBookingMonitor)
        .filter(
            CdasBookingMonitor.id == monitor_id,
            CdasBookingMonitor.company_id == context.company_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="CDAS booking monitor not found")

    if row.booked_at is None:
        now = datetime.utcnow()
        row.booked_at = now
        row.booked_by_user_id = context.staff.user_id
        notifications = db.query(Notification).filter(
            Notification.entity_type == "cdas_booking_monitor",
            Notification.entity_id == str(row.id),
            Notification.user_id == context.staff.user_id,
            Notification.is_archived.is_(False),
        )
        notifications.update(
            {Notification.is_read: True, Notification.read_at: now, Notification.is_archived: True, Notification.archived_at: now},
            synchronize_session=False,
        )
        db.commit()
        db.refresh(row)
    return monitor_to_dict(row)
