"""Contract guarantees for future employee new-only registration requests."""
from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from database.models.enums import EmploymentStatus, Gender
from database.schemas.new_only_client_registration import StrictNewOnlyClientRegistration
from services.atomic_new_client_registration import _minimal_only


def valid_request():
    return {
        "branch_id": uuid4(),
        "first_name": "  Palesa ",
        "last_name": " Mokoena ",
        "phone": " 59000001 ",
        "gender": Gender.FEMALE,
        "date_of_birth": date(1992, 3, 4),
        "national_id": " SYN-REG-123 ",
        "district": " Maseru ",
        "employment_status": EmploymentStatus.EMPLOYED,
        "consent_to_share_profile": False,
        "consent_to_credit_checks": True,
    }


def test_exact_supported_fields_preserved_by_internal_mapping():
    request = StrictNewOnlyClientRegistration.model_validate(valid_request())
    internal = request.to_internal_assisted_payload()
    minimum = _minimal_only(internal)
    assert request.first_name == "Palesa"
    assert request.national_id == "SYN-REG-123"
    assert minimum.first_name == request.first_name
    assert minimum.last_name == request.last_name
    assert minimum.phone == request.phone
    assert minimum.national_id == request.national_id
    assert minimum.district == request.district
    assert minimum.employment_status == request.employment_status
    assert minimum.consent_to_share_profile is False
    assert minimum.consent_to_credit_checks is True
    assert internal.branch_id == request.branch_id


@pytest.mark.parametrize("field,value", [
    ("bank_account", {"bank_name": "fake bank", "account_number": "123"}),
    ("monthly_income", "5000.00"),
    ("has_existing_loans", True),
    ("external_debts", []),
    ("employer_name", "Employer"),
    ("email", "someone@example.test"),
    ("physical_address", "Some address"),
    ("salary_date", "2026-11-20"),
    ("temporary_password", "synthetic-secret"),
    ("unexpected_field", "never silently ignore"),
])
def test_unsupported_and_unknown_fields_fail_instead_of_being_dropped(field, value):
    payload = valid_request()
    payload[field] = value
    with pytest.raises(ValidationError, match=field):
        StrictNewOnlyClientRegistration.model_validate(payload)


@pytest.mark.parametrize("remove", [
    "branch_id", "first_name", "last_name", "phone", "gender",
    "date_of_birth", "district", "employment_status",
    "consent_to_share_profile", "consent_to_credit_checks",
])
def test_required_fields_and_explicit_consent_are_not_defaulted(remove):
    payload = valid_request()
    payload.pop(remove)
    with pytest.raises(ValidationError):
        StrictNewOnlyClientRegistration.model_validate(payload)


@pytest.mark.parametrize("invalid", [None, "  ", ""])
def test_missing_both_identity_documents_is_rejected(invalid):
    payload = valid_request()
    payload["national_id"] = invalid
    payload["passport_number"] = invalid
    with pytest.raises(ValidationError):
        StrictNewOnlyClientRegistration.model_validate(payload)


def test_passport_only_preserved_without_creating_a_national_id():
    payload = valid_request()
    payload["national_id"] = None
    payload["passport_number"] = " PASS-0002 "
    internal = StrictNewOnlyClientRegistration.model_validate(
        payload).to_internal_assisted_payload()
    assert internal.passport_number == "PASS-0002"
    assert internal.national_id is None


def test_no_future_dob():
    payload = valid_request()
    payload["date_of_birth"] = date(2099, 1, 1)
    with pytest.raises(ValidationError):
        StrictNewOnlyClientRegistration.model_validate(payload)
