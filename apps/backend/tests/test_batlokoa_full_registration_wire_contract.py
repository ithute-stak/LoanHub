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
