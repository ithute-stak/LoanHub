from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.cdas_booking import CdasBookingOpportunity
from database.models.company_staff import CompanyStaff
from database.models.enums import NotificationType
from database.models.notification import Notification
from database.models.user import User


def local_today() -> date:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()


def opportunity_state(item: CdasBookingOpportunity, today: date | None = None) -> str:
    if item.status == "booked":
        return "BOOKED"
    today = today or local_today()
    if item.booking_open_date and today >= item.booking_open_date:
        return "BOOK_NOW"
    return "UPCOMING"


def serialize_opportunity(item: CdasBookingOpportunity, today: date | None = None) -> dict:
    today = today or local_today()
    state = opportunity_state(item, today)
    days_until_booking = None
    if item.booking_open_date:
        days_until_booking = max(0, (item.booking_open_date - today).days)
    return {
        "id": str(item.id),
        "client_name": item.client_name,
        "client_reference": item.client_reference,
        "status": item.status,
        "state": state,
        "booking_lead_months": item.booking_lead_months,
        "alert_lead_days": item.alert_lead_days,
        "booking_open_date": item.booking_open_date,
        "alert_start_date": item.alert_start_date,
        "days_until_booking": days_until_booking,
        "opportunity_agency_name": item.opportunity_agency_name,
        "opportunity_item_code": item.opportunity_item_code,
        "opportunity_reference_no": item.opportunity_reference_no,
        "opportunity_effective_date": item.opportunity_effective_date,
        "opportunity_expiry_date": item.opportunity_expiry_date,
        "opportunity_deduction_amount": float(item.opportunity_deduction_amount or 0),
        "total_monthly_deductions": float(item.total_monthly_deductions or 0),
        "own_monthly_deductions": float(item.own_monthly_deductions or 0),
        "competitor_monthly_deductions": float(item.competitor_monthly_deductions or 0),
        "analysis_snapshot": item.analysis_snapshot or {},
        "booked_at": item.booked_at,
        "booked_by_user_id": str(item.booked_by_user_id) if item.booked_by_user_id else None,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def create_opportunity_from_analysis(
    db: Session,
    *,
    company_id,
    client_name: str | None,
    client_reference: str | None,
    alert_lead_days: int,
    analysis: dict,
) -> CdasBookingOpportunity:
    row = analysis.get("opportunity") or (analysis.get("own_bookings") or [None])[0]
    booking_open = None
    if analysis.get("next_possible_booking_date"):
        booking_open = date.fromisoformat(str(analysis["next_possible_booking_date"])[:10])
    elif row and row.get("booking_open_date"):
        booking_open = date.fromisoformat(str(row["booking_open_date"])[:10])
    if analysis.get("decision") == "BOOK_NOW" and booking_open is None:
        booking_open = local_today()

    alert_start = booking_open - timedelta(days=alert_lead_days) if booking_open else None
    booked = analysis.get("decision") == "ALREADY_BOOKED"
    item = CdasBookingOpportunity(
        company_id=company_id,
        client_name=(client_name or "").strip() or None,
        client_reference=(client_reference or "").strip() or None,
        status="booked" if booked else "monitoring",
        booking_lead_months=int(analysis.get("booking_lead_months") or 0),
        alert_lead_days=alert_lead_days,
        booking_open_date=booking_open,
        alert_start_date=alert_start,
        opportunity_agency_name=row.get("agency_name") if row else None,
        opportunity_item_code=row.get("item_code") if row else None,
        opportunity_reference_no=row.get("reference_no") if row else None,
        opportunity_effective_date=date.fromisoformat(str(row["effective_date"])[:10]) if row and row.get("effective_date") else None,
        opportunity_expiry_date=date.fromisoformat(str(row["expiry_date"])[:10]) if row and row.get("expiry_date") else None,
        opportunity_deduction_amount=Decimal(str(row.get("deduction_amount") or 0)) if row else None,
        total_monthly_deductions=Decimal(str(analysis.get("total_monthly_deductions") or 0)),
        own_monthly_deductions=Decimal(str(analysis.get("own_monthly_deductions") or 0)),
        competitor_monthly_deductions=Decimal(str(analysis.get("competitor_monthly_deductions") or 0)),
        analysis_snapshot=analysis,
        booked_at=datetime.utcnow() if booked else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def generate_due_cdas_booking_alerts(db: Session, user: User) -> int:
    today = local_today()
    company_ids = [row[0] for row in db.query(CompanyStaff.company_id).filter(CompanyStaff.user_id == user.id, CompanyStaff.is_active.is_(True)).distinct().all()]
    if not company_ids:
        return 0
    due = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id.in_(company_ids),
        CdasBookingOpportunity.status == "monitoring",
        CdasBookingOpportunity.alert_start_date.isnot(None),
        CdasBookingOpportunity.alert_start_date <= today,
    ).all()
    created = 0
    for item in due:
        key = f"cdas-booking:{item.id}:{user.id}:{today.isoformat()}"
        exists = db.query(Notification.id).filter(Notification.user_id == user.id, Notification.deduplication_key == key).first()
        if exists:
            continue
        ready = bool(item.booking_open_date and today >= item.booking_open_date)
        days = max(0, (item.booking_open_date - today).days) if item.booking_open_date else 0
        client = item.client_name or item.client_reference or item.opportunity_reference_no or "CDAS client"
        title = "CDAS client can be booked now" if ready else f"CDAS booking opens in {days} day(s)"
        message = f"{client}: booking window {'is open now' if ready else f'opens on {item.booking_open_date:%d %b %Y}'}. This reminder continues daily until the opportunity is marked booked."
        db.add(Notification(
            user_id=user.id,
            company_id=item.company_id,
            title=title,
            message=message,
            notification_type=NotificationType.SYSTEM,
            event_type="cdas.booking.ready" if ready else "cdas.booking.upcoming",
            action="view",
            entity_type="cdas_booking_opportunity",
            entity_id=str(item.id),
            action_url="/company/cdas-booking",
            icon="calendar-clock",
            priority="high",
            data={"opportunity_id": str(item.id), "booking_open_date": item.booking_open_date.isoformat() if item.booking_open_date else None},
            deduplication_key=key,
        ))
        created += 1
    if created:
        db.commit()
    return created
