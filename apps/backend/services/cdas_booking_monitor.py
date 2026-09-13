from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import UUID

from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.cdas_booking_monitor import CdasBookingMonitor
from database.models.company_staff import CompanyStaff
from database.models.enums import NotificationType
from database.models.notification import Notification


ALERT_DAYS_BEFORE_BOOKING = 3


def shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def booking_window_dates(expiry_date: date, booking_lead_months: int) -> tuple[date, date]:
    expiry_month = expiry_date.replace(day=1)
    booking_open = shift_month(expiry_month, -booking_lead_months).replace(day=1)
    return booking_open, booking_open - timedelta(days=ALERT_DAYS_BEFORE_BOOKING)


def monitor_phase(monitor: CdasBookingMonitor, *, as_of: date) -> str:
    if monitor.booked_at is not None:
        return "BOOKED"
    if as_of >= monitor.booking_open_date:
        return "BOOK_NOW"
    if as_of >= monitor.alert_start_date:
        return "ALERTING"
    return "UPCOMING"


def monitor_to_dict(monitor: CdasBookingMonitor, *, as_of: date | None = None) -> dict:
    today = as_of or datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    phase = monitor_phase(monitor, as_of=today)
    return {
        "id": str(monitor.id),
        "client_name": monitor.client_name,
        "client_reference": monitor.client_reference,
        "item_code": monitor.item_code,
        "agency_name": monitor.agency_name,
        "deduction_amount": float(monitor.deduction_amount or 0),
        "effective_date": monitor.effective_date,
        "expiry_date": monitor.expiry_date,
        "reference_no": monitor.reference_no,
        "source_status": monitor.source_status,
        "booking_lead_months": monitor.booking_lead_months,
        "booking_open_date": monitor.booking_open_date,
        "alert_start_date": monitor.alert_start_date,
        "phase": phase,
        "days_until_booking": max((monitor.booking_open_date - today).days, 0),
        "booked_at": monitor.booked_at,
        "created_at": monitor.created_at,
    }


def ensure_cdas_booking_alerts_for_user(db: Session, user_id: UUID) -> int:
    """Create at most one CDAS reminder per monitored client, user and day.

    Notification list/unread-count endpoints call this function, so reminders are
    refreshed through LoanHub's existing notification polling without adding a
    second scheduler or deployment service.
    """
    today = datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    memberships = (
        db.query(CompanyStaff)
        .filter(CompanyStaff.user_id == user_id, CompanyStaff.is_active.is_(True))
        .all()
    )
    if not memberships:
        return 0

    company_ids = {membership.company_id for membership in memberships}
    monitors = (
        db.query(CdasBookingMonitor)
        .filter(
            CdasBookingMonitor.company_id.in_(company_ids),
            CdasBookingMonitor.booked_at.is_(None),
            CdasBookingMonitor.alert_start_date <= today,
        )
        .all()
    )

    created = 0
    for monitor in monitors:
        dedupe_key = f"cdas-booking:{monitor.id}:{user_id}:{today.isoformat()}"
        exists = (
            db.query(Notification.id)
            .filter(Notification.deduplication_key == dedupe_key)
            .first()
        )
        if exists:
            continue

        phase = monitor_phase(monitor, as_of=today)
        if phase == "BOOK_NOW":
            title = "CDAS client ready to book"
            message = (
                f"{monitor.client_name} can be booked now. "
                "Keep following up until this opportunity is marked Booked."
            )
            action_url = "/company/cdas-booking?tab=book-now"
        else:
            days = max((monitor.booking_open_date - today).days, 0)
            title = "CDAS booking window approaching"
            message = (
                f"{monitor.client_name} can be booked from "
                f"{monitor.booking_open_date.strftime('%d %B %Y')} ({days} day(s) away)."
            )
            action_url = "/company/cdas-booking?tab=upcoming"

        db.add(
            Notification(
                user_id=user_id,
                company_id=monitor.company_id,
                title=title,
                message=message,
                notification_type=NotificationType.SYSTEM,
                event_type="cdas.booking_window",
                action="view",
                entity_type="cdas_booking_monitor",
                entity_id=str(monitor.id),
                action_url=action_url,
                icon="calendar-clock",
                priority="high",
                data={
                    "monitor_id": str(monitor.id),
                    "client_name": monitor.client_name,
                    "booking_open_date": monitor.booking_open_date.isoformat(),
                    "phase": phase,
                },
                deduplication_key=dedupe_key,
            )
        )
        created += 1

    if created:
        db.commit()
    return created
