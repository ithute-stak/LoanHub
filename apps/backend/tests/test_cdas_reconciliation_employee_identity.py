"""Require complete employee identity for CDAS deduction reconciliation."""
from types import SimpleNamespace

from services.cdas_operation_ledger import _deduction_matches


def operation(employee_no="EMP-1"):
    return SimpleNamespace(
        employee_no=employee_no,
        request_snapshot={
            "EmployeeNo": employee_no,
            "DeductionID": 50,
            "ReferenceNo": "REF-1",
            "ItemCode": "LOAN",
        },
        response_snapshot={},
    )


def test_reject_record_missing_employee_even_if_deduction_id_matches():
    assert not _deduction_matches(operation(), {"DeductionID": 50, "ReferenceNo": "REF-1"})


def test_reject_record_with_blank_employee_even_if_deduction_id_matches():
    assert not _deduction_matches(operation(), {"EmployeeNo": "  ", "DeductionID": 50})


def test_reject_operation_missing_employee_even_when_provider_matches_id():
    assert not _deduction_matches(operation(employee_no=""), {"EmployeeNo": "EMP-1", "DeductionID": 50})


def test_accept_matching_employee_and_deduction_id():
    assert _deduction_matches(operation(), {"EmployeeNo": "EMP-1", "DeductionID": 50})


def test_reject_other_employee_even_when_deduction_id_matches():
    assert not _deduction_matches(operation(), {"EmployeeNo": "EMP-2", "DeductionID": 50})
