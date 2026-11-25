"""Check Batlokoa's five-step JSON shapes against LoanHub's real capture schema.

Synthetic test payloads only. No transaction, API route or production write.
"""
from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture


def sample():
    return {
        "branch_id": str(uuid4()),
        "first_name": "Synthetic",
        "middle_name": "Test",
        "last_name": "Applicant",
        "phone": "59000001",
        "date_of_birth": "1991-05-01",
        "gender": "female",
        "national_id": "TEST-ONLY-NOT-REAL-001",
        "passport_number": None,
        "marital_status": "single",
        "nationality": "Mosotho",
        "district": "Maseru",
        "town_or_village": "Maseru West",
        "physical_address": "Synthetic residential address",
        "employment_status": "employed",
        "employment_type": "full_time",
        "employer_name": "Synthetic Employer",
        "job_title": "Clerk",
        "income_day": 25,
        "monthly_income": "6000.00",
        "salary_date": None,
        "has_existing_loans": True,
        "existing_loan_total": "500.00",
        "external_debts": [{
            "creditor": "Synthetic Lender",
            "current_balance": "500.00",
            "installment_amount": "100.00",
            "remaining_installments": 5,
        }],
        "consent_to_share_profile": True,
        "consent_to_credit_checks": True,
        "bank_account": {
            "bank_name": "FNB",
            "account_holder": "Synthetic Applicant",
            "account_number": None,
            "account_type": "savings",
            "salary_account": True,
        },
    }


def test_batlokoa_full_registration_json_is_accepted_without_losing_fields():
    captured = FullNewOnlyClientCapture.model_validate(sample())
    assert captured.first_name == "Synthetic"
    assert captured.middle_name == "Test"
    assert captured.income_day == 25
    assert captured.has_existing_loans is True
    assert len(captured.external_debts) == 1
    assert captured.external_debts[0].remaining_installments == 5
    assert str(captured.external_debts[0].current_balance) == "500.00"
    assert captured.bank_account is not None
    assert captured.bank_account.salary_account is True
    assert captured.consent_to_credit_checks is True
    internal = captured.to_internal_full_payload()
    assert len(internal.external_debts) == 1
    assert internal.bank_account is not None
    assert internal.bank_account.account_holder == "Synthetic Applicant"


@pytest.mark.parametrize("invalid", [
    {"external_debts": [], "has_existing_loans": True, "existing_loan_total": "0"},
    {"external_debts": [{
        "creditor": "Synthetic", "current_balance": "500.00",
        "installment_amount": "100.00", "remaining_installments": 5,
    }], "has_existing_loans": False},
    {"branch_id": None},
    {"independently_approved_release": True},
])
def test_batlokoa_full_registration_rejects_invalid_or_untrusted_capture(invalid):
    data = sample()
    data.update(invalid)
    with pytest.raises(ValidationError):
        FullNewOnlyClientCapture.model_validate(data)



def test_batlokoa_real_form_supported_sandbox_payload_is_lossless():
    """Mirror the actual Batlokoa Flutter mapping, not an arbitrary minimal DTO."""
    from services.full_new_only_client_staging import _reject_unsafe_fields

    wire = {
        "branch_id": str(uuid4()),
        "first_name": "Synthetic",
        "middle_name": "Test",
        "last_name": "Applicant",
        "phone": "59000001",
        "date_of_birth": "1991-05-01",
        "gender": "female",
        "national_id": "SYNTHETIC-NOT-REAL",
        "passport_number": None,
        "marital_status": "single",
        "nationality": "Mosotho",
        "district": "Maseru",
        "town_or_village": "Maseru West",
        "physical_address": "Synthetic address",
        "employment_status": "employed",
        "employment_type": None,
        "cdas_employee_number": None,
        "employer_name": "Synthetic employer",
        "employer_group_id": None,
        "job_title": None,
        "income_day": 25,
        "monthly_income": "6000.00",
        "salary_date": None,
        "has_existing_loans": True,
        "existing_loan_total": "500.00",
        "external_debts": [{
            "creditor": "Synthetic lender",
            "current_balance": "500.00",
            "installment_amount": "100.00",
            "remaining_installments": 5,
        }],
        "consent_to_share_profile": True,
        "consent_to_credit_checks": True,
        "bank_account": {
            "bank_name": "FNB",
            "account_holder": "Synthetic Applicant",
            "account_number": "61234567890",
            "account_type": "savings",
            "salary_account": True,
        },
    }
    captured = FullNewOnlyClientCapture.model_validate(wire)
    _reject_unsafe_fields(captured)
    assert captured.model_dump(mode="json")["bank_account"]["account_number"] == "61234567890"
    assert captured.middle_name == "Test"
    assert captured.monthly_income == 6000
    assert captured.external_debts[0].creditor == "Synthetic lender"
    assert captured.external_debts[0].current_balance == 500
    assert captured.consent_to_share_profile is True
    assert captured.consent_to_credit_checks is True


@pytest.mark.parametrize("unsupported", [
    {"cdas_employee_number": "SYNTHETIC-PAYROLL"},
    {"employer_group_id": str(uuid4())},
    {"email": "synthetic@example.invalid"},
    {"temporary_password": "SyntheticTemporary123!"},
])
def test_advanced_batlokoa_fields_require_separate_save_certification(unsupported):
    """No silent dropping of unsupported or credential-bearing form details."""
    from services.full_new_only_client_staging import (
        FullNewOnlyStagingUnavailable, _reject_unsafe_fields,
    )

    data = sample()
    data.update(unsupported)
    captured = FullNewOnlyClientCapture.model_validate(data)
    with pytest.raises(FullNewOnlyStagingUnavailable):
        _reject_unsafe_fields(captured)
