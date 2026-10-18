"""Executable domain-math checks for pre-due, due-day, and paid top-ups.

These are deterministic financial examples, not text searches. They exercise
the same interest calculator and settlement-principal helper as production.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from database.models.enums import LoanCalculationMethod
from services.early_settlement_service import calculate_method_earned_interest
from services.interest_calculation_service import calculate_loan_terms
from services.top_up_settlement import replacement_principal


ORIGINAL_PRINCIPAL = Decimal("1000.00")
RATE = Decimal("20")
DUE_DATES = [date(2026, 10, 20), date(2026, 11, 20)]


def _earned(settlement_date: date) -> Decimal:
    earned, _, _ = calculate_method_earned_interest(
        method=LoanCalculationMethod.MICRO_LOAN,
        principal=ORIGINAL_PRINCIPAL,
        rate_percent=RATE,
        original_term_months=2,
        start_date=date(2026, 10, 1),
        due_dates=DUE_DATES,
        settlement_date=settlement_date,
    )
    return Decimal(earned)


@pytest.mark.parametrize(
    ("date_of_settlement", "cash_paid_to_date", "expected_settlement", "expected_new_principal"),
    [
        (date(2026, 10, 19), Decimal("0"), Decimal("1000.00"), Decimal("1200.00")),
        (date(2026, 10, 20), Decimal("0"), Decimal("1200.00"), Decimal("1400.00")),
        (date(2026, 10, 20), Decimal("660.00"), Decimal("540.00"), Decimal("740.00")),
    ],
)
def test_micro_topup_due_boundary_and_real_payments(
    date_of_settlement, cash_paid_to_date, expected_settlement, expected_new_principal
):
    # Successful repayments reduce actual settlement, without crediting
    # unearned scheduled interest or pretending a top-up was cash repayment.
    settlement = ORIGINAL_PRINCIPAL + _earned(date_of_settlement) - cash_paid_to_date
    assert settlement == expected_settlement
    new_principal = replacement_principal(
        SimpleNamespace(settlement_amount=settlement), Decimal("200.00")
    )
    assert new_principal == expected_new_principal


def test_pre_due_topup_recalculates_two_instalments_not_original_balance():
    principal = replacement_principal(
        SimpleNamespace(settlement_amount=Decimal("1000")), Decimal("200")
    )
    monthly, total, terms = calculate_loan_terms(
        principal=principal,
        rate_percent=RATE,
        term_months=2,
        processing_fee=Decimal("0"),
        interest_method=LoanCalculationMethod.MICRO_LOAN,
        start_date=date(2026, 10, 19),
        due_dates=DUE_DATES,
    )
    assert principal == Decimal("1200.00")
    assert monthly == Decimal("792.00")
    assert total == Decimal("1584.00")


@pytest.mark.parametrize("cash", [Decimal("0"), Decimal("-0.01")])
def test_topup_rejects_zero_or_negative_cash(cash):
    with pytest.raises(HTTPException) as error:
        replacement_principal(
            SimpleNamespace(settlement_amount=Decimal("1000")), cash
        )
    assert error.value.status_code == 422
