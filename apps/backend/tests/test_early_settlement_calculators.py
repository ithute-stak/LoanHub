from datetime import date
from decimal import Decimal

import pytest

from database.models.enums import LoanCalculationMethod
from services.early_settlement_service import (
    calculate_method_earned_interest,
    chargeable_months,
)
from services.interest_calculation_service import (
    calculate_daily_accrued_interest,
    calculate_loan_terms,
    generate_monthly_due_dates,
)


MONTHLY_METHODS = [
    LoanCalculationMethod.MICRO_LOAN,
    LoanCalculationMethod.SIMPLE_INTEREST,
    LoanCalculationMethod.FLAT_RATE,
    LoanCalculationMethod.COMPOUND_INTEREST,
    LoanCalculationMethod.REDUCING_BALANCE,
]


@pytest.mark.parametrize("method", MONTHLY_METHODS)
def test_early_settlement_reuses_original_calculator_with_shortened_term(method):
    principal = Decimal("1200")
    rate = Decimal("10") if method == LoanCalculationMethod.MICRO_LOAN else Decimal("36")
    start = date(2026, 1, 1)
    original_dates = generate_monthly_due_dates(start, 3)

    earned, periods, audit = calculate_method_earned_interest(
        method=method,
        principal=principal,
        rate_percent=rate,
        original_term_months=3,
        start_date=start,
        due_dates=original_dates,
        settlement_date=date(2026, 1, 20),
    )
    _, _, one_month = calculate_loan_terms(
        principal=principal,
        rate_percent=rate,
        term_months=1,
        processing_fee=Decimal("0"),
        interest_method=method,
        start_date=start,
        due_dates=original_dates[:1],
    )
    _, _, original = calculate_loan_terms(
        principal=principal,
        rate_percent=rate,
        term_months=3,
        processing_fee=Decimal("0"),
        interest_method=method,
        start_date=start,
        due_dates=original_dates,
    )

    assert periods == 1
    assert earned == Decimal(one_month["total_interest"])
    assert earned < Decimal(original["total_interest"])
    assert audit["basis"] == "same_calculator_shortened_term"
    assert audit["calculator"] == method.value


def test_daily_settlement_uses_actual_days_not_a_monthly_proxy():
    start = date(2026, 1, 1)
    settlement_date = date(2026, 1, 20)
    due_dates = generate_monthly_due_dates(start, 3)

    earned, periods, audit = calculate_method_earned_interest(
        method=LoanCalculationMethod.DAILY_ACCRUAL_REDUCING,
        principal=Decimal("1200"),
        rate_percent=Decimal("12"),
        original_term_months=3,
        start_date=start,
        due_dates=due_dates,
        settlement_date=settlement_date,
    )
    expected, _ = calculate_daily_accrued_interest(
        Decimal("1200"),
        Decimal("12"),
        start,
        settlement_date,
    )

    assert periods == 1
    assert earned == expected == Decimal("7.35")
    assert audit["basis"] == "actual_days_on_outstanding_principal"


@pytest.mark.parametrize(
    ("settlement_date", "expected_periods"),
    [
        (date(2026, 1, 1), 1),
        (date(2026, 2, 1), 1),
        (date(2026, 2, 2), 2),
        (date(2026, 3, 1), 2),
        (date(2026, 3, 2), 3),
        (date(2027, 1, 1), 3),
    ],
)
def test_chargeable_period_boundary_is_auditable(settlement_date, expected_periods):
    start = date(2026, 1, 1)
    assert chargeable_months(
        settlement_date=settlement_date,
        start_date=start,
        due_dates=generate_monthly_due_dates(start, 3),
        original_term_months=3,
    ) == expected_periods


def test_three_month_simple_loan_settled_in_month_one_rebates_two_months_interest():
    principal = Decimal("1200")
    start = date(2026, 1, 1)
    dates = generate_monthly_due_dates(start, 3)
    earned, periods, _ = calculate_method_earned_interest(
        method=LoanCalculationMethod.SIMPLE_INTEREST,
        principal=principal,
        rate_percent=Decimal("12"),
        original_term_months=3,
        start_date=start,
        due_dates=dates,
        settlement_date=date(2026, 1, 31),
    )
    _, _, original = calculate_loan_terms(
        principal=principal,
        rate_percent=Decimal("12"),
        term_months=3,
        processing_fee=Decimal("0"),
        interest_method=LoanCalculationMethod.SIMPLE_INTEREST,
        start_date=start,
        due_dates=dates,
    )

    assert periods == 1
    assert earned == Decimal("12.00")
    assert Decimal(original["total_interest"]) - earned == Decimal("24.00")
