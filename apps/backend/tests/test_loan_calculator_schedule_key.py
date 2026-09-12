from decimal import Decimal

from database.models.enums import LoanCalculationMethod
from database.schemas.cash import LoanCalculationRequest
from routers.loans import loan_calculator


def test_loan_calculator_maps_internal_schedule_rows_to_public_schedule():
    payload = LoanCalculationRequest(
        principal=Decimal("1000.00"),
        rate_percent=Decimal("10.00"),
        months=3,
        processing_fee=Decimal("0.00"),
        interest_method=LoanCalculationMethod.MICRO_LOAN,
    )

    result = loan_calculator(payload)

    assert result["schedule"]
    assert len(result["schedule"]) == 3
    assert result["schedule"][0]["installment_number"] == 1
    assert result["schedule_amounts"][0] == Decimal(
        result["schedule"][0]["total_due"]
    )
