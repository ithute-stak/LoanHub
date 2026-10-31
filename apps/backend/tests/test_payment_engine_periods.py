from decimal import Decimal

import pytest

from payment_engine.periods import PeriodInput, preview_periods
from payment_engine.policy import ArrearsPolicy, ArrearsRule


def test_partial_payment_then_missing_period_then_partial_repayment():
    results = preview_periods([
        PeriodInput(Decimal("1000"), Decimal("600")),
        PeriodInput(Decimal("1000"), Decimal("0")),
        PeriodInput(Decimal("1000"), Decimal("900")),
    ], policy=ArrearsPolicy())
    assert [row.total_collectible_due for row in results] == [
        Decimal("1000.00"), Decimal("1400.00"), Decimal("2400.00"),
    ]
    assert [row.closing_arrears for row in results] == [
        Decimal("400.00"), Decimal("1400.00"), Decimal("1500.00"),
    ]


def test_fixed_schedule_does_not_hide_arrears_or_double_count():
    results = preview_periods([
        PeriodInput(Decimal("1000"), Decimal("600")),
        PeriodInput(Decimal("1000"), Decimal("0")),
    ], policy=ArrearsPolicy(rule=ArrearsRule.FIXED_SCHEDULE))
    assert results[-1].scheduled_due == Decimal("1000.00")
    assert results[-1].total_collectible_due == Decimal("1400.00")
    assert results[-1].separately_tracked_arrears == Decimal("1400.00")
    assert results[-1].carried_into_next_schedule == Decimal("0.00")


def test_early_payment_held_as_credit_then_applied_once():
    results = preview_periods([
        PeriodInput(Decimal("1000"), Decimal("1500")),
        PeriodInput(Decimal("1000"), Decimal("200")),
    ], policy=ArrearsPolicy())
    assert results[0].unapplied_credit == Decimal("500.00")
    assert results[1].amount_applied == Decimal("700.00")
    assert results[1].closing_arrears == Decimal("300.00")


def test_interest_accrual_not_activated_before_component_ledger():
    with pytest.raises(ValueError, match="component-level"):
        preview_periods([PeriodInput(Decimal("1000"), Decimal("600"))], policy=ArrearsPolicy(
            rule=ArrearsRule.CARRY_WITH_INTEREST,
            periodic_arrears_rate_percent=Decimal("10"),
            additional_interest_authorized=True,
        ))


@pytest.mark.parametrize("amount", ["-1", "-0.01"])
def test_negative_money_rejected(amount):
    with pytest.raises(ValueError, match="nonnegative"):
        preview_periods([PeriodInput(Decimal("1000"), Decimal(amount))], policy=ArrearsPolicy())
