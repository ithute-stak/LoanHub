from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from database.models.enums import UserRole


def _app_timezone() -> ZoneInfo:
    from database.config.config import settings
    return ZoneInfo(settings.APP_TIMEZONE)


def current_payment_date() -> date:
    return datetime.now(_app_timezone()).date()


def resolve_payment_date(role: UserRole, requested: date | None, *, today: date | None = None) -> date:
    current = today or current_payment_date()
    effective = requested or current
    if effective > current:
        raise HTTPException(status_code=422, detail="Payment date cannot be in the future")
    if effective < current and role != UserRole.COMPANY_OWNER:
        raise HTTPException(status_code=403, detail="Only the Company Owner can backdate payments")
    return effective


def payment_date_to_utc(value: date) -> datetime:
    local_midnight = datetime.combine(value, time.min, tzinfo=_app_timezone())
    return local_midnight.astimezone(timezone.utc)
