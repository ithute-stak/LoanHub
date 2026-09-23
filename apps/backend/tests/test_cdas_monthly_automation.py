from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from services.cdas_lifecycle_automation import (
    SETTLEMENT_REASON_CONSOLIDATION,
    SETTLEMENT_REASON_PAID_BY_EMPLOYEE,
    automatic_settlement_reason,
    reconciliation_status_order,
)
from services.cdas_monthly_automation import (
    calculate_automatic_terms,
    is_monthly_automation_window,
    next_effective_month,
)
from services.cdas_sub1000_auto_modification import calculate_sub1000_modification


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


def test_sub1000_modification_uses_only_incremental_affordability():
    target, increase, installments = calculate_sub1000_modification(
        current_deduction=Decimal("650.00"),
        outstanding=Decimal("5000.00"),
        affordability=Decimal("350.00"),
    )
    assert target == Decimal("1000.00")
    assert increase == Decimal("350.00")
    assert installments == 5


def test_sub1000_modification_rejects_when_incremental_capacity_is_short():
    with pytest.raises(ValueError, match="Additional CDAS affordability"):
        calculate_sub1000_modification(
            current_deduction=Decimal("650.00"),
            outstanding=Decimal("5000.00"),
            affordability=Decimal("349.99"),
        )


def test_sub1000_modification_never_exceeds_remaining_balance():
    target, increase, installments = calculate_sub1000_modification(
        current_deduction=Decimal("500.00"),
        outstanding=Decimal("800.00"),
        affordability=Decimal("300.00"),
    )
    assert target == Decimal("800.00")
    assert increase == Decimal("300.00")
    assert installments == 1


def test_sub1000_modification_does_not_change_deduction_already_at_target():
    with pytest.raises(ValueError, match="does not require"):
        calculate_sub1000_modification(
            current_deduction=Decimal("1000.00"),
            outstanding=Decimal("5000.00"),
            affordability=Decimal("500.00"),
        )


def test_active_reconciliation_searches_current_then_forward_and_terminal_states():
    order = reconciliation_status_order("active", 5)
    assert order[0] == 5
    assert 10 in order
    assert 7 in order
    assert 8 in order
    assert len(order) == len(set(order))


def test_reconciliation_required_searches_all_documented_statuses_with_known_status_first():
    order = reconciliation_status_order("reconciliation_required", 4)
    assert order[0] == 4
    assert set(order) == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}


def test_fully_paid_zero_balance_is_automatically_settled_as_paid_by_employee():
    reason = automatic_settlement_reason(
        outstanding_balance=Decimal("0.00"),
        amount_paid=Decimal("5000.00"),
        total_repayable=Decimal("5000.00"),
        has_consolidation_successor=False,
    )
    assert reason == SETTLEMENT_REASON_PAID_BY_EMPLOYEE


def test_zero_balance_with_disbursed_topup_is_settled_as_consolidation():
    reason = automatic_settlement_reason(
        outstanding_balance=Decimal("0.00"),
        amount_paid=Decimal("1200.00"),
        total_repayable=Decimal("5000.00"),
        has_consolidation_successor=True,
    )
    assert reason == SETTLEMENT_REASON_CONSOLIDATION


def test_positive_balance_is_never_auto_settled():
    assert (
        automatic_settlement_reason(
            outstanding_balance=Decimal("0.01"),
            amount_paid=Decimal("5000.00"),
            total_repayable=Decimal("5000.00"),
            has_consolidation_successor=True,
        )
        is None
    )


def test_zero_balance_without_payment_or_consolidation_requires_manual_review():
    assert (
        automatic_settlement_reason(
            outstanding_balance=Decimal("0.00"),
            amount_paid=Decimal("1000.00"),
            total_repayable=Decimal("5000.00"),
            has_consolidation_successor=False,
        )
        is None
    )
