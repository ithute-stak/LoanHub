"""Read-only bridge from approved LoanHub schedule to Principal x% quotes.

This adapter never calls or modifies the LoanHub origination calculator.
Only persisted, agreed schedule rows may be supplied by the caller.
"""
from datetime import date
from decimal import Decimal
from typing import Iterable

from payment_engine.principal_x_settlement import (
    DatedCredit,
    PrincipalXQuote,
    quote_principal_x,
)


def quote_from_approved_schedule(
    *,
    principal: Decimal,
    rate_percent: Decimal,
    schedule_rows: Iterable[object],
    settlement_date: date,
    successful_credits: Iterable[DatedCredit] = (),
) -> PrincipalXQuote:
    """Consume existing schedule rows without recomputing their instalments.

    Rows must expose due_date and total_due, as LoanHub's ScheduleRow does.
    The caller is responsible for reading the approved/persisted schedule,
    authenticating ledger credits, and requiring settlement consent.
    """
    rows = list(schedule_rows)
    if not rows:
        raise ValueError("An approved repayment schedule is required")
    if any(getattr(row, 'is_superseded', False) for row in rows):
        raise ValueError('Superseded repayment schedules cannot be used for settlement')
    dates = [row.due_date for row in rows]
    if any(not isinstance(d, date) for d in dates):
        raise ValueError("Schedule due dates must be dates")
    if dates != sorted(set(dates)):
        raise ValueError("Repayment due dates must be unique and ascending")
    if any(Decimal(str(row.total_due)) < 0 for row in rows):
        raise ValueError("Repayment amounts cannot be negative")
    total = sum((Decimal(str(row.total_due)) for row in rows), Decimal("0"))
    return quote_principal_x(
        principal=Decimal(str(principal)),
        rate_percent=Decimal(str(rate_percent)),
        due_dates=dates,
        settlement_date=settlement_date,
        successful_credits=tuple(successful_credits),
        contractual_total=total,
    )
