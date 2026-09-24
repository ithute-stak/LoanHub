from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Iterable
from uuid import UUID
from zoneinfo import ZoneInfo


AUTHORIZATION_BASIS = "LOAN_LEVEL_CDAS_COLLECTION_SELECTION"
COLLECTION_METHOD = "cdas_payroll"
COLLECTION_MODE = "automatic_monthly_payroll"
CDAS_TIMEZONE = "Africa/Maseru"
PROCESSING_WINDOW_START_DAY = 14
PROCESSING_WINDOW_END_DAY = 20
PROCESSING_HOUR = 6


def _add_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def cdas_payroll_timing(selected_at: datetime) -> dict[str, str]:
    """Return the next viable CDAS provider window and payroll month.

    CDAS provider writes run at 06:00 Africa/Maseru from the 14th through the
    20th. A selection made after the final 06:00 hour on the 20th must wait
    for the following month's provider window. Deductions written in a window
    become effective in the following payroll month.
    """
    maseru = ZoneInfo(CDAS_TIMEZONE)
    if selected_at.tzinfo is None:
        local_selected = selected_at.replace(tzinfo=timezone.utc).astimezone(maseru)
    else:
        local_selected = selected_at.astimezone(maseru)

    processing_month = date(local_selected.year, local_selected.month, 1)
    final_window_close = datetime.combine(
        date(local_selected.year, local_selected.month, PROCESSING_WINDOW_END_DAY),
        time(PROCESSING_HOUR + 1, 0),
        tzinfo=maseru,
    )
    if local_selected >= final_window_close:
        processing_month = _add_month(processing_month)

    processing_start = date(
        processing_month.year,
        processing_month.month,
        PROCESSING_WINDOW_START_DAY,
    )
    processing_end = date(
        processing_month.year,
        processing_month.month,
        PROCESSING_WINDOW_END_DAY,
    )
    effective_month = _add_month(processing_month)
    return {
        "processing_window_start": processing_start.isoformat(),
        "processing_window_end": processing_end.isoformat(),
        "processing_time": f"{PROCESSING_HOUR:02d}:00",
        "timezone": CDAS_TIMEZONE,
        "effective_month": f"{effective_month.year:04d}-{effective_month.month:02d}",
        "first_expected_collection_month": f"{effective_month.year:04d}-{effective_month.month:02d}",
    }


def build_cdas_collection_plan(
    *,
    enabled: bool,
    installment_due_dates: Iterable[date | str],
    term_count: int,
    selected_by_user_id: UUID | None,
    selected_at: datetime | None = None,
) -> dict:
    """Build the server-owned plan persisted on an application or loan.

    Clients select only whether the loan is collected through CDAS. Provider
    fields such as ItemCode, LoanPolicy and DeductionID remain server/provider
    controlled and are deliberately excluded from this plan.
    """
    if not enabled:
        return {}

    normalized_dates = [
        value.isoformat() if isinstance(value, date) else str(value)
        for value in installment_due_dates
    ]
    plan = {
        "method": COLLECTION_METHOD,
        "mode": COLLECTION_MODE,
        "authorization_basis": AUTHORIZATION_BASIS,
        "term_count": int(term_count),
        "installment_due_dates": normalized_dates,
        "first_payment_date": normalized_dates[0] if normalized_dates else None,
        "selected_by_user_id": str(selected_by_user_id) if selected_by_user_id else None,
    }
    if selected_at is not None:
        plan["selected_at"] = selected_at.isoformat()
        plan.update(cdas_payroll_timing(selected_at))
    return plan
