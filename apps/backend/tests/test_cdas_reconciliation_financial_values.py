"""Read-only CDAS reconciliation rejects mismatched financial evidence."""

from types import SimpleNamespace

import pytest

from services.cdas_operation_ledger import _modified_values_match, _provider_status_matches


def operation():
    return SimpleNamespace(
        employee_no="TEST-200",
        response_snapshot={"DeductionID": 901},
        request_snapshot={
            "EmployeeNo": "TEST-200",
            "DeductionID": 901,
            "DeductionAmount": "500.00",
            "PrincipalAmount": "6000.00",
            "TotalInstallment": 12,
        },
    )


def record():
    return {
        "EmployeeNo": "TEST-200",
        "DeductionID": 901,
        "DeductionAmount": "500.00",
        "PrincipalAmount": "6000.00",
        "TotalInstallment": 12,
    }


@pytest.mark.parametrize("field,bad_value", [
    ("DeductionAmount", None),
    ("DeductionAmount", ""),
    ("DeductionAmount", "501.00"),
    ("DeductionAmount", "not-money"),
    ("PrincipalAmount", None),
    ("PrincipalAmount", ""),
    ("PrincipalAmount", "5999.99"),
    ("PrincipalAmount", "not-money"),
    ("TotalInstallment", None),
    ("TotalInstallment", 13),
    ("EmployeeNo", "OTHER"),
    ("DeductionID", 902),
])
def test_modify_reconciliation_rejects_missing_or_mismatched_fields(field, bad_value):
    response = record()
    response[field] = bad_value
    assert _modified_values_match(operation(), response) is False


def test_modify_reconciliation_accepts_equal_decimal_representation():
    response = record()
    response["DeductionAmount"] = 500
    response["PrincipalAmount"] = "6000.0"
    assert _modified_values_match(operation(), response) is True


@pytest.mark.parametrize("status", [None, "", True, False, 4, "invalid"])
def test_lifecycle_status_mismatch_is_not_confirmed(status):
    assert _provider_status_matches({"DeductionStatus": status}, 3) is False


def test_lifecycle_status_can_match_numeric_string():
    assert _provider_status_matches({"DeductionStatus": "3"}, 3) is True
