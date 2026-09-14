from datetime import date

import pytest

from services.cdas_what_if_simulator import (
    calculate_monthly_installment,
    simulate_what_if,
)


TODAY = date(2026, 9, 14)


def _opportunity(*, capacity=1500.0, decision="BOOK_NOW", issues=0, deductions=None):
    return {
        "id": "opportunity-1",
        "client_name": "Test Client",
        "client_reference": "EMP-001",
        "opportunity_agency_name": "Example Agency",
        "analysis_snapshot": {
            "decision": decision,
            "data_quality_issue_count": issues,
            "capacity": {"assessed_available_amount": capacity},
            "deductions": deductions or [],
        },
    }


def _deduction(booking_date: str, amount: float, *, reference: str):
    return {
        "item_code": "2595",
        "agency_name": "Example Agency",
        "reference_no": reference,
        "deduction_amount": amount,
        "booking_open_date": booking_date,
        "expiry_date": "2027-03-01",
        "is_active": True,
        "excluded_from_booking": False,
        "booking_status": "WAIT",
    }


def test_direct_installment_that_fits_current_capacity_is_read_only_fit_now():
    result = simulate_what_if(
        opportunity=_opportunity(capacity=1500),
        today=TODAY,
        proposed_installment=1000,
    )

    assert result["calculation_method"] == "DIRECT_INSTALLMENT"
    assert result["scenario"]["proposed_installment"] == 1000
    assert result["current_capacity"] == 1500
    assert result["fits_now"] is True
    assert result["remaining_capacity"] == 500
    assert result["shortfall"] == 0
    assert result["status"] == "FITS_NOW"
    assert result["requires_waiting_for_release"] is False
    assert result["earliest_fit_date"] is None
    assert result["confidence"] == "HIGH"


def test_amortized_loan_scenario_calculates_monthly_payment():
    payment = calculate_monthly_installment(
        proposed_amount=10000,
        term_months=12,
        annual_interest_rate=12,
    )
    assert payment == 888.49

    result = simulate_what_if(
        opportunity=_opportunity(capacity=1000),
        today=TODAY,
        proposed_amount=10000,
        term_months=12,
        annual_interest_rate=12,
    )
    assert result["calculation_method"] == "AMORTIZED_PAYMENT"
    assert result["scenario"]["proposed_installment"] == 888.49
    assert result["fits_now"] is True
    assert result["remaining_capacity"] == 111.51


def test_future_release_windows_find_earliest_date_that_closes_shortfall():
    result = simulate_what_if(
        opportunity=_opportunity(
            capacity=500,
            deductions=[
                _deduction("2026-09-20", 300, reference="A"),
                _deduction("2026-10-01", 400, reference="B"),
            ],
        ),
        today=TODAY,
        proposed_installment=900,
    )

    assert result["fits_now"] is False
    assert result["shortfall"] == 400
    assert result["status"] == "FITS_AFTER_RELEASE"
    assert result["requires_waiting_for_release"] is True
    assert result["earliest_fit_date"] == "2026-10-01"
    assert result["earliest_fit_capacity"] == 1200
    assert [window["cumulative_release"] for window in result["release_windows"]] == [300, 700]
    assert result["confidence"] == "INDICATIVE"


def test_invalid_or_past_release_rows_do_not_create_fake_future_capacity():
    deductions = [
        _deduction("2026-09-13", 900, reference="PAST"),
        {**_deduction("2026-10-01", 900, reference="BAD"), "excluded_from_booking": True},
        {**_deduction("2026-10-02", 900, reference="INACTIVE"), "is_active": False},
    ]
    result = simulate_what_if(
        opportunity=_opportunity(capacity=200, deductions=deductions),
        today=TODAY,
        proposed_installment=1000,
    )

    assert result["release_windows"] == []
    assert result["status"] == "EXCEEDS_KNOWN_CAPACITY"
    assert result["earliest_fit_date"] is None


def test_review_required_and_quality_issues_lower_confidence_without_hiding_math():
    result = simulate_what_if(
        opportunity=_opportunity(capacity=2000, decision="REVIEW_REQUIRED", issues=2),
        today=TODAY,
        proposed_installment=500,
    )

    assert result["fits_now"] is True
    assert result["status"] == "FITS_NOW"
    assert result["confidence"] == "REVIEW_REQUIRED"
    assert len(result["warnings"]) == 2
    assert "requires review" in result["warnings"][0].lower()


def test_capacity_unknown_is_not_treated_as_zero_capacity():
    result = simulate_what_if(
        opportunity=_opportunity(capacity=None),
        today=TODAY,
        proposed_installment=500,
    )

    assert result["status"] == "CAPACITY_UNKNOWN"
    assert result["current_capacity"] is None
    assert result["remaining_capacity"] is None
    assert result["shortfall"] is None
    assert result["confidence"] == "LOW"


def test_scenario_requires_direct_installment_or_complete_loan_inputs():
    with pytest.raises(ValueError, match="Provide a proposed installment"):
        simulate_what_if(
            opportunity=_opportunity(),
            today=TODAY,
            proposed_amount=10000,
            term_months=12,
        )


def test_zero_interest_loan_uses_simple_principal_divided_by_term():
    assert calculate_monthly_installment(
        proposed_amount=12000,
        term_months=12,
        annual_interest_rate=0,
    ) == 1000
