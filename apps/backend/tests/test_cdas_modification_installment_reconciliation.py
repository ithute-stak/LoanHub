"""CDAS modification reconciliation must fail closed on missing installments."""

from types import SimpleNamespace

import pytest

from services.cdas_operation_ledger import _modified_values_match


@pytest.mark.parametrize("returned", [None, "", False, 11, "invalid"])
def test_requested_installments_require_matching_readback(returned):
    operation = SimpleNamespace(
        employee_no="TEST-17",
        response_snapshot={"DeductionID": 700},
        request_snapshot={
            "EmployeeNo": "TEST-17",
            "DeductionID": 700,
            "TotalInstallment": 12,
            "DeductionAmount": "100.00",
        },
    )
    record = {
        "EmployeeNo": "TEST-17",
        "DeductionID": 700,
        "DeductionAmount": "100.00",
        "TotalInstallment": returned,
    }
    assert _modified_values_match(operation, record) is False


def test_matching_installment_count_can_confirm_modification():
    operation = SimpleNamespace(
        employee_no="TEST-17",
        response_snapshot={"DeductionID": 700},
        request_snapshot={"EmployeeNo": "TEST-17", "DeductionID": 700, "TotalInstallment": 12},
    )
    record = {"EmployeeNo": "TEST-17", "DeductionID": 700, "TotalInstallment": 12}
    assert _modified_values_match(operation, record) is True
