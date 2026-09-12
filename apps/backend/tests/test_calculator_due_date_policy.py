from datetime import date
from decimal import Decimal

import pytest

from database.models.enums import LoanCalculationMethod
from database.schemas.cash import LoanCalculationRequest
from routers.loans import loan_calculator
from services.interest_calculation_service import calculate_loan_terms


def test_public_calculator_proposes_month_end_dates_when_dates_are_omitted():
    result = loan_calculator(
        LoanCalculationRequest(
            principal=Decimal("1000.00"),
            rate_percent=Decimal("10.00"),
            months=3,
            processing_fee=Decimal("0.00"),
            interest_method=LoanCalculationMethod.MICRO_LOAN,
            interest_start_date=date(2026, 1, 31),
        )
    )

    assert [row["due_date"] for row in result["schedule"]] == [
        "2026-02-28",
        "2026-03-31",
        "2026-04-30",
    ]


def test_core_calculation_requires_the_agreed_schedule():
    with pytest.raises(ValueError, match="Enter exactly 3 installment due dates"):
        calculate_loan_terms(
            principal=Decimal("1000.00"),
            rate_percent=Decimal("10.00"),
            term_months=3,
            processing_fee=Decimal("0.00"),
            interest_method=LoanCalculationMethod.MICRO_LOAN,
            start_date=date(2026, 1, 31),
        )
