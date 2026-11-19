from datetime import date
from decimal import Decimal

import pytest

from payment_engine.principal_x_settlement import DatedCredit, quote_principal_x


DATES = [date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 31)]


def quote(on, payments=(), ceiling=True):
    return quote_principal_x(
        principal=Decimal("1000"),
        rate_percent=Decimal("20"),
        contractual_total=Decimal("1392"),
        due_dates=DATES,
        settlement_date=on,
        successful_credits=[DatedCredit(day, Decimal(str(amount))) for day, amount in payments],
        enforce_contractual_ceiling=ceiling,
    )


def test_first_period_inclusive_boundary():
    assert quote(DATES[0]).collectible_due == Decimal("1200.00")


def test_second_period_after_first_instalment():
    result = quote(date(2026, 12, 15), [(DATES[0], 464)])
    assert result.period == 2
    assert result.collectible_due == Decimal("883.20")


def test_separate_second_period_payments_do_not_trigger_new_interest():
    result = quote(date(2026, 12, 20), [
        (DATES[0], 464), (date(2026, 12, 10), 300),
        (date(2026, 12, 20), Decimal("583.20")),
    ])
    assert result.collectible_due == 0


def test_missed_first_payment_is_capped_to_contract():
    result = quote(date(2026, 12, 15))
    assert result.uncapped_due == Decimal("1440.00")
    assert result.collectible_due == Decimal("1392.00")


def test_third_period_roll_forward_and_cap():
    result = quote(date(2027, 1, 15), [(DATES[0], 464), (DATES[1], 464)])
    assert result.uncapped_due == Decimal("503.04")
    assert result.collectible_due == Decimal("464.00")


def test_multiple_payments_before_first_due_date():
    result = quote(date(2026, 11, 23), [
        (date(2026, 11, 18), 464), (date(2026, 11, 20), 464),
        (date(2026, 11, 23), 464),
    ])
    assert result.collectible_due == 0
    assert result.total_credited == Decimal("1392.00")


def test_two_times_principal_lifetime_cap_even_without_contract_ceiling():
    result = quote(date(2027, 2, 1), ceiling=False)
    assert result.uncapped_due == Decimal("1728.00")
    assert result.collectible_due == Decimal("1728.00")
    result = quote(date(2027, 2, 1), [(DATES[0], 1000)], ceiling=False)
    assert result.collectible_due <= Decimal("1000.00")


def test_reject_future_credit_and_negative_credit():
    with pytest.raises(ValueError):
        quote(date(2026, 11, 20), [(date(2026, 11, 21), 100)])
    with pytest.raises(ValueError):
        quote(date(2026, 11, 20), [(date(2026, 11, 19), -100)])


def test_reject_unsorted_dates():
    with pytest.raises(ValueError):
        quote_principal_x(
            principal=Decimal("1000"), rate_percent=Decimal("20"),
            contractual_total=Decimal("1392"), settlement_date=DATES[0],
            due_dates=list(reversed(DATES)),
        )
