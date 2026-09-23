from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from services.cdas_monthly_automation import (
    calculate_automatic_terms,
    is_monthly_automation_window,
    next_effective_month,
)


MASERU = ZoneInfo("Africa/Maseru")


def test_monthly_window_runs_only_14_to_20_at_0600():
    assert not is_monthly_automation_window(datetime(2026, 9, 14, 5, 59, tzinfo=MASERU))
    assert is_monthly_automation_window(datetime(2026, 9, 14, 6, 0, tzinfo=MASERU))
    assert is_monthly_automation_window(datetime(2026, 9, 20, 6, 59, tzinfo=MASERU))
    assert not is_monthly_automation_window(datetime(2026, 9, 20, 7, 0, tzinfo=MASERU))
    assert not is_monthly_automation_window(datetime(2026, 9, 21, 6, 0, tzinfo=MASERU))


def test_positive_partial_affordability_reterms_current_balance():
    deduction, installments = calculate_automatic_terms(
        outstanding=Decimal("1000.00"),
        affordability=Decimal("300.00"),
    )
    assert deduction == Decimal("300.00")
    assert installments == 4


def test_affordability_above_balance_caps_at_balance():
    deduction, installments = calculate_automatic_terms(
        outstanding=Decimal("250.00"),
        affordability=Decimal("900.00"),
    )
    assert deduction == Decimal("250.00")
    assert installments == 1


def test_zero_affordability_is_not_eligible():
    with pytest.raises(ValueError, match="positive outstanding balance"):
        calculate_automatic_terms(outstanding=Decimal("500.00"), affordability=Decimal("0.00"))


def test_automatic_term_respects_provider_safety_limit():
    with pytest.raises(ValueError, match="600-installment"):
        calculate_automatic_terms(outstanding=Decimal("1000.00"), affordability=Decimal("1.00"))


def test_next_effective_month_rolls_year():
    assert next_effective_month(datetime(2026, 11, 15).date()) == "2026-12"
    assert next_effective_month(datetime(2026, 12, 15).date()) == "2027-01"
