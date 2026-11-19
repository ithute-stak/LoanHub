from datetime import date
from decimal import Decimal

import pytest

from payment_engine.principal_x_settlement import DatedCredit, quote_principal_x


DATES = (date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 31))


def quote(at, entries=(), *, contractual_total=Decimal("1392")):
    return quote_principal_x(
        principal=Decimal("1000"),
        rate_percent=Decimal("20"),
        due_dates=DATES,
        settlement_date=at,
        contractual_total=contractual_total,
        successful_credits=[DatedCredit(day, Decimal(str(amount))) for day, amount in entries],
    )


@pytest.mark.parametrize("entries,expected", [
    ([(date(2026, 11, 20), 100), (date(2026, 11, 25), 100)], Decimal("1000.00")),
    ([(date(2026, 11, 20), 200)], Decimal("1000.00")),
    ([(date(2026, 11, 30), 464)], Decimal("736.00")),
])
def test_first_period_partial_and_split_payments(entries, expected):
    assert quote(DATES[0], entries).collectible_due == expected


def test_same_day_split_payments_are_individually_credited():
    entries = [(date(2026, 11, 30), 200), (date(2026, 11, 30), 264)]
    result = quote(date(2026, 12, 15), entries)
    assert result.total_credited == Decimal("464.00")
    assert result.collectible_due == Decimal("883.20")


def test_partial_first_period_credit_reduces_next_period_base():
    result = quote(date(2026, 12, 15), [(date(2026, 11, 25), 200)])
    assert result.uncapped_due == Decimal("1200.00")
    assert result.collectible_due == Decimal("1192.00")


def test_second_period_payment_deducted_without_reapplying_rate():
    result = quote(date(2026, 12, 20), [
        (date(2026, 11, 30), 464),
        (date(2026, 12, 10), 200),
        (date(2026, 12, 20), 100),
    ])
    assert result.uncapped_due == Decimal("583.20")
    assert result.collectible_due == Decimal("583.20")


def test_payment_after_first_due_date_is_not_backdated_into_first_period():
    result = quote(date(2026, 12, 1), [(date(2026, 12, 1), 464)])
    assert result.uncapped_due == Decimal("976.00")
    assert result.collectible_due == Decimal("928.00")


def test_second_due_date_is_still_second_period():
    result = quote(DATES[1], [(DATES[0], 464)])
    assert result.period == 2
    assert result.collectible_due == Decimal("883.20")


def test_advance_payment_cannot_create_negative_collectible():
    result = quote(date(2026, 11, 25), [(date(2026, 11, 25), 1392)])
    assert result.collectible_due == Decimal("0.00")
    assert result.total_credited == Decimal("1392.00")


def test_no_payments_after_maturity_does_not_accrue_new_periods():
    result = quote(date(2027, 8, 1))
    assert result.period == 3
    assert result.uncapped_due == Decimal("1728.00")
    assert result.collectible_due == Decimal("1392.00")
