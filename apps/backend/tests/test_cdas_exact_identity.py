from __future__ import annotations

import pytest

from services.cdas_exact_identity import (
    CdasExactIdentityError,
    extract_provider_national_id,
    mask_national_id,
    normalize_national_id,
    validate_exact_provider_identity,
)


def test_national_id_normalization_is_formatting_insensitive_but_exact():
    assert normalize_national_id(" 04227-120 7029 ") == "042271207029"
    assert normalize_national_id("ab-12 34") == "AB1234"
    assert normalize_national_id("042271207028") != normalize_national_id("042271207029")


def test_national_id_is_masked_in_responses():
    assert mask_national_id("042271207029") == "********7029"
    assert mask_national_id("1234") == "****"


@pytest.mark.parametrize(
    "key",
    [
        "NationalID",
        "NationalId",
        "national_id",
        "IDNumber",
        "IdNumber",
        "id_number",
        "IdentityNumber",
        "identity_number",
    ],
)
def test_provider_national_id_variants_are_detected(key: str):
    assert extract_provider_national_id({key: "04227-1207029"}) == "042271207029"


def test_employee_number_is_required_to_match_exactly():
    with pytest.raises(CdasExactIdentityError) as raised:
        validate_exact_provider_identity(
            loanhub_national_id="042271207029",
            requested_employee_no="0019336",
            employee_details={"EmployeeNo": "0019337", "Name": "Different Person"},
        )
    assert raised.value.status_code == 409
    assert "different employee number" in raised.value.message.lower()


def test_provider_national_id_mismatch_is_a_hard_conflict():
    with pytest.raises(CdasExactIdentityError) as raised:
        validate_exact_provider_identity(
            loanhub_national_id="042271207029",
            requested_employee_no="0019336",
            employee_details={"EmployeeNo": "0019336", "NationalID": "042271207028"},
        )
    assert raised.value.status_code == 409
    assert "national id" in raised.value.message.lower()


def test_documented_v15_response_without_national_id_uses_exact_loanhub_id_plus_employee_no():
    result = validate_exact_provider_identity(
        loanhub_national_id="042271207029",
        requested_employee_no="0019336",
        employee_details={
            "EmployeeNo": "0019336",
            "Name": "TEBANG",
            "Surname": "MOSUNKUTHU",
            "DOB": "02/03/1979",
        },
    )
    assert result["basis"] == "EXACT_LOANHUB_NATIONAL_ID_PLUS_CDAS_EMPLOYEE_NO"
    assert result["provider_national_id_present"] is False


def test_names_and_dates_do_not_participate_in_exact_identifier_validation():
    result = validate_exact_provider_identity(
        loanhub_national_id="042271207029",
        requested_employee_no="0019336",
        employee_details={
            "EmployeeNo": "0019336",
            "Name": "SOME OTHER DISPLAY NAME",
            "Surname": "DISPLAY ONLY",
            "DOB": "01/01/1900",
        },
    )
    assert result["provider_employee_no"] == "0019336"
