import pytest

from services.cdas_max_loan_calculator import (
    calculate_reference_max_principal,
    present_value_from_payment,
)


def test_zero_interest_present_value_is_payment_times_term():
    assert present_value_from_payment(
        monthly_payment=1000,
        term_months=12,
        annual_interest_rate=0,
    ) == 12000


def test_amortized_present_value_is_deterministic():
    assert present_value_from_payment(
        monthly_payment=1000,
        term_months=12,
        annual_interest_rate=12,
    ) == 11255.08


def test_reference_principal_uses_manual_capacity_less_fee_and_insurance():
    result = calculate_reference_max_principal(
        monthly_capacity=1000,
        term_months=12,
        annual_interest_rate=12,
        monthly_service_fee=100,
        insurance_percent=10,
    )

    assert result["status"] == "CALCULATED"
    assert result["inputs"]["monthly_capacity"] == 1000
    assert result["installment_budget"] == 900
    assert result["max_financed_balance"] == 10129.57
    assert result["max_principal"] == 9208.7
    assert result["insurance_amount"] == 920.87
    assert result["projected_monthly_total"] == 1000
    assert "not a credit decision" in result["calculation_note"].lower()


def test_fee_consuming_all_manual_capacity_returns_zero_reference_principal():
    result = calculate_reference_max_principal(
        monthly_capacity=500,
        term_months=12,
        annual_interest_rate=20,
        monthly_service_fee=500,
    )

    assert result["status"] == "NO_CAPACITY"
    assert result["installment_budget"] == 0
    assert result["max_principal"] == 0
    assert result["max_financed_balance"] == 0


def test_invalid_inputs_raise_clear_errors():
    with pytest.raises(ValueError, match="Monthly capacity"):
        calculate_reference_max_principal(
            monthly_capacity=-1,
            term_months=12,
            annual_interest_rate=20,
        )

    with pytest.raises(ValueError, match="Term months"):
        calculate_reference_max_principal(
            monthly_capacity=1000,
            term_months=0,
            annual_interest_rate=20,
        )

    with pytest.raises(ValueError, match="service fee"):
        calculate_reference_max_principal(
            monthly_capacity=1000,
            term_months=12,
            annual_interest_rate=20,
            monthly_service_fee=-1,
        )
