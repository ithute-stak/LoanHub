"""Phase 4: financial safety regression tests for Principal x% settlement.

The lifetime cap is a product-policy ceiling, not a statement of universal law.
"""
from datetime import date
from decimal import Decimal

import pytest

from payment_engine.principal_x_settlement import DatedCredit, quote_principal_x


DATES = (date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 31))


def quote(*, at=date(2027, 1, 31), rate=Decimal("100"), total=Decimal("9000"), credits=()):
    return quote_principal_x(
        principal=Decimal("1000"), rate_percent=rate,
        due_dates=DATES, settlement_date=at, contractual_total=total,
        enforce_contractual_ceiling=False,
        successful_credits=[DatedCredit(d, Decimal(str(v))) for d, v in credits],
    )


def test_high_rate_never_exceeds_two_times_original_principal():
    result = quote()
    assert result.uncapped_due == Decimal("8000.00")
    assert result.collectible_due == Decimal("2000.00")
    assert result.lifetime_cap_remaining == Decimal("2000.00")
    assert result.ceiling_reduction == Decimal("6000.00")


def test_prior_payments_reduce_lifetime_ceiling():
    payments = [(date(2026, 11, 15), 400), (date(2026, 12, 15), 300)]
    result = quote(credits=payments)
    assert result.total_credited == Decimal("700.00")
    assert result.lifetime_cap_remaining == Decimal("1300.00")
    assert result.collectible_due <= Decimal("1300.00")
    assert result.collectible_due + result.total_credited <= Decimal("2000.00")


def test_no_new_interest_cycles_after_maturity():
    at_maturity = quote()
    long_after = quote(at=date(2029, 12, 31))
    assert long_after.period == at_maturity.period
    assert long_after.uncapped_due == at_maturity.uncapped_due


def test_paid_up_to_lifetime_cap_has_zero_remaining_collectible():
    result = quote(credits=[(date(2026, 11, 20), 2000)])
    assert result.lifetime_cap_remaining == Decimal("0.00")
    assert result.collectible_due == Decimal("0.00")


def test_contractual_ceiling_is_additional_to_lifetime_ceiling():
    result = quote_principal_x(
        principal=Decimal("1000"), rate_percent=Decimal("100"),
        due_dates=DATES, settlement_date=date(2027, 1, 31),
        contractual_total=Decimal("1500"),
    )
    assert result.collectible_due == Decimal("1500.00")


def test_multiple_missed_periods_do_not_create_unbounded_debt():
    result = quote(at=date(2035, 1, 1))
    assert result.period == 3
    assert result.collectible_due == Decimal("2000.00")
