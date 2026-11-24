from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from payment_engine.principal_x_schedule_adapter import quote_from_approved_schedule
from payment_engine.principal_x_settlement import DatedCredit


def rows():
    return [
        SimpleNamespace(due_date=date(2026, 11, 30), total_due=Decimal("464"), is_superseded=False),
        SimpleNamespace(due_date=date(2026, 12, 31), total_due=Decimal("464"), is_superseded=False),
        SimpleNamespace(due_date=date(2027, 1, 31), total_due=Decimal("464"), is_superseded=False),
    ]


def test_approved_schedule_is_read_without_mutation():
    schedule = rows()
    snapshot = [(r.due_date, r.total_due) for r in schedule]
    result = quote_from_approved_schedule(
        principal=Decimal("1000"), rate_percent=Decimal("20"),
        schedule_rows=schedule, settlement_date=date(2026, 12, 15),
        successful_credits=[DatedCredit(date(2026, 11, 30), Decimal("464"))],
    )
    assert result.collectible_due == Decimal("883.20")
    assert [(r.due_date, r.total_due) for r in schedule] == snapshot


def test_reject_superseded_schedule():
    schedule = rows()
    schedule[0].is_superseded = True
    with pytest.raises(ValueError, match="Superseded"):
        quote_from_approved_schedule(
            principal=Decimal("1000"), rate_percent=Decimal("20"),
            schedule_rows=schedule, settlement_date=date(2026, 12, 15),
        )


def test_reject_duplicate_due_dates():
    schedule = rows()
    schedule[1].due_date = schedule[0].due_date
    with pytest.raises(ValueError, match="unique"):
        quote_from_approved_schedule(
            principal=Decimal("1000"), rate_percent=Decimal("20"),
            schedule_rows=schedule, settlement_date=date(2026, 12, 15),
        )
