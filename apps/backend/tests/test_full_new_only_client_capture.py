"""Phase 84: full client capture must preserve every validated field."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from database.models.enums import EmploymentStatus, Gender
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from services.atomic_new_client_registration import (
    AtomicRegistrationUnavailable, _minimal_only,
)


def application():
    return {
        "branch_id": uuid4(),
        "phone": "59000001",
        "first_name": "Palesa",
        "middle_name": "M",
        "last_name": "Mokoena",
        "gender": Gender.FEMALE,
        "date_of_birth": date(1990, 2, 10),
        "national_id": "SYN-84-NATIONAL",
        "passport_number": "SYN-84-PASSPORT",
        "district": "Maseru",
        "town_or_village": "Roma",
        "physical_address": "Synthetic street",
        "employment_status": EmploymentStatus.EMPLOYED,
        "employer_name": "Synthetic Employer",
        "employment_type": "permanent",
        "job_title": "Administrator",
        "monthly_income": Decimal("6500.00"),
        "income_day": 25,
        "salary_date": "25",
        "has_existing_loans": True,
        "existing_loan_total": Decimal("1000.00"),
        "external_debts": [{
            "creditor": "Synthetic external creditor",
            "current_balance": Decimal("1000.00"),
            "installment_amount": Decimal("150.00"),
            "total_installments": 12,
            "installments_paid": 4,
            "status": "active",
        }],
        "consent_to_share_profile": True,
        "consent_to_credit_checks": False,
    }


def test_full_form_survives_validated_mapping_without_loss():
    request = FullNewOnlyClientCapture.model_validate(application())
    internal = request.to_internal_full_payload()
    assert internal.model_dump(mode="json", exclude_none=False) == (
        request.model_dump(mode="json", exclude_none=False))
    assert internal.external_debts[0].current_balance == Decimal("1000")
    assert internal.employer_name == "Synthetic Employer"
    assert internal.physical_address == "Synthetic street"
    with pytest.raises(AtomicRegistrationUnavailable, match="Unsupported"):
        _minimal_only(internal)


@pytest.mark.parametrize("field", [
    "monthly_income", "employment_type", "physical_address",
    "external_debts", "existing_loan_total", "employer_name",
    "salary_date", "consent_to_credit_checks",
])
def test_present_fields_not_dropped_by_capture_mapping(field):
    request = FullNewOnlyClientCapture.model_validate(application())
    internal = request.to_internal_full_payload()
    assert internal.model_dump(mode="json")[field] == (
        request.model_dump(mode="json")[field])


@pytest.mark.parametrize("invalid", [
    {"unexpected_account": "silent-data-loss"},
    {"password": "unsafe-injected-field"},
    {"bank_account": {"pan": "4111111111111111"}},
])
def test_unknown_and_unsafe_fields_rejected(invalid):
    with pytest.raises(ValidationError):
        FullNewOnlyClientCapture.model_validate({**application(), **invalid})


def test_debt_requires_explicit_existing_loan_flag():
    data = application()
    data["has_existing_loans"] = False
    with pytest.raises(ValidationError):
        FullNewOnlyClientCapture.model_validate(data)


def test_debt_requires_consistent_positive_declared_total():
    data = application()
    data["existing_loan_total"] = Decimal("0")
    with pytest.raises(ValidationError):
        FullNewOnlyClientCapture.model_validate(data)


def test_passport_only_is_accepted_without_national_id():
    data = application()
    data["national_id"] = None
    result = FullNewOnlyClientCapture.model_validate(data)
    assert result.passport_number == "SYN-84-PASSPORT"
    assert result.national_id is None


def test_empty_identity_rejected():
    data = application()
    data["national_id"] = " "
    data["passport_number"] = None
    with pytest.raises(ValidationError):
        FullNewOnlyClientCapture.model_validate(data)
