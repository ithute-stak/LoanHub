from datetime import date

import pytest
from pydantic import ValidationError

from database.schemas.company_clients import AssistedCompanyClientCreate


def _payload() -> dict:
    return {
        "phone": "+26650000000",
        "temporary_password": "Temporary-123",
        "first_name": "Test",
        "last_name": "Borrower",
        "gender": "male",
        "date_of_birth": date(1990, 1, 1),
        "national_id": "123456789012",
        "district": "Maseru",
        "employment_status": "employed",
        "has_existing_loans": False,
        "existing_loan_total": 0,
        "consent_to_share_profile": True,
        "consent_to_credit_checks": True,
    }


def test_assisted_registration_accepts_secure_banking_profile() -> None:
    payload = _payload()
    payload["bank_account"] = {
        "account_holder": "Test Borrower",
        "bank_name": "Example Bank",
        "branch_name": "Maseru",
        "branch_code": "001",
        "account_type": "savings",
        "currency": "LSL",
        "account_number": "1234567890",
        "salary_account": True,
        "verification_status": "unverified",
        "masked_card_number": "**** 4832",
        "card_brand": "Visa",
        "card_expiry_month": 8,
        "card_expiry_year": 2030,
    }

    model = AssistedCompanyClientCreate.model_validate(payload)

    assert model.bank_account is not None
    assert model.bank_account.account_number == "1234567890"
    assert model.bank_account.masked_card_number == "**** 4832"


@pytest.mark.parametrize("forbidden_field", ["cvv", "cvc", "security_code", "card_number"])
def test_assisted_registration_rejects_raw_card_secret_fields(forbidden_field: str) -> None:
    payload = _payload()
    bank = {
        "account_holder": "Test Borrower",
        "bank_name": "Example Bank",
        "account_number": "1234567890",
        forbidden_field: "123",
    }
    payload["bank_account"] = bank

    with pytest.raises(ValidationError):
        AssistedCompanyClientCreate.model_validate(payload)


def test_assisted_registration_rejects_full_pan_in_masked_card_field() -> None:
    payload = _payload()
    payload["bank_account"] = {
        "account_holder": "Test Borrower",
        "bank_name": "Example Bank",
        "account_number": "1234567890",
        "masked_card_number": "4111111111111111",
    }

    with pytest.raises(ValidationError):
        AssistedCompanyClientCreate.model_validate(payload)
