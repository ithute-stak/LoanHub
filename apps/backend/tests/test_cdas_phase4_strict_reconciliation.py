"""CDAS reconciliation must never confirm another employee's deduction."""
from types import SimpleNamespace

from services.cdas_operation_ledger import _deduction_matches


def operation(deduction_id=50):
    return SimpleNamespace(
        employee_no="EMP-1",
        request_snapshot={
            "EmployeeNo": "EMP-1", "DeductionID": deduction_id,
            "ItemCode": "LOAN", "ReferenceNo": "REF-1",
        },
        response_snapshot={},
    )


def test_reconciliation_rejects_wrong_deduction_even_with_same_reference():
    assert not _deduction_matches(operation(), {
        "EmployeeNo": "EMP-1", "DeductionID": 99,
        "ReferenceNo": "REF-1", "ItemCode": "LOAN",
    })


def test_reconciliation_rejects_missing_deduction_id_when_expected():
    assert not _deduction_matches(operation(), {
        "EmployeeNo": "EMP-1", "ReferenceNo": "REF-1", "ItemCode": "LOAN",
    })


def test_reconciliation_rejects_other_employee_with_same_deduction_id():
    assert not _deduction_matches(operation(), {
        "EmployeeNo": "EMP-2", "DeductionID": 50,
        "ReferenceNo": "REF-1",
    })


def test_reconciliation_accepts_matching_employee_and_deduction_id():
    assert _deduction_matches(operation(), {
        "EmployeeNo": "EMP-1", "DeductionID": 50,
    })


def test_registration_without_known_id_can_still_use_reference():
    assert _deduction_matches(operation(deduction_id=0), {
        "EmployeeNo": "EMP-1", "ReferenceNo": "REF-1",
    })
