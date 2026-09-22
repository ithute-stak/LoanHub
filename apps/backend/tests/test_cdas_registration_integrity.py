from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import LoanStatus, RepaymentType
from services.cdas_deduction_lifecycle import CdasLifecycleError
from services.cdas_registration_workflow import (
    _parse_cdas_date,
    _validate_employee_identity,
    _validate_loan_terms,
)


def _loan(**overrides):
    person = SimpleNamespace(
        first_name="Theko",
        last_name="Koetlisi",
        date_of_birth=date(1990, 5, 14),
    )
    values = {
        "branch_id": uuid4(),
        "status": LoanStatus.APPROVED,
        "repayment_type": RepaymentType.MONTHLY,
        "installment_amount": Decimal("500.00"),
        "principal_amount": Decimal("6000.00"),
        "repayment_period": 12,
        "borrower": SimpleNamespace(user=SimpleNamespace(person=person)),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_registration_terms_must_match_approved_loanhub_loan():
    loan = _loan()
    _validate_loan_terms(
        loan,
        branch_id=loan.branch_id,
        deduction_amount=Decimal("500.00"),
        principal_amount=Decimal("6000.00"),
        total_installment=12,
        effective_month="2099-10",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("deduction_amount", Decimal("501.00")),
        ("principal_amount", Decimal("5999.99")),
        ("total_installment", 11),
    ],
)
def test_registration_rejects_browser_terms_that_differ_from_loan(field: str, value):
    loan = _loan()
    payload = {
        "branch_id": loan.branch_id,
        "deduction_amount": Decimal("500.00"),
        "principal_amount": Decimal("6000.00"),
        "total_installment": 12,
        "effective_month": "2099-10",
    }
    payload[field] = value

    with pytest.raises(CdasLifecycleError) as raised:
        _validate_loan_terms(loan, **payload)

    assert raised.value.status_code == 422


def test_registration_rejects_pending_or_non_monthly_loan():
    with pytest.raises(CdasLifecycleError):
        _validate_loan_terms(
            _loan(status=LoanStatus.PENDING),
            branch_id=None,
            deduction_amount=Decimal("500.00"),
            principal_amount=Decimal("6000.00"),
            total_installment=12,
            effective_month="2099-10",
        )

    with pytest.raises(CdasLifecycleError):
        _validate_loan_terms(
            _loan(repayment_type=RepaymentType.WEEKLY),
            branch_id=None,
            deduction_amount=Decimal("500.00"),
            principal_amount=Decimal("6000.00"),
            total_installment=12,
            effective_month="2099-10",
        )


def test_registration_rejects_cross_branch_loan():
    loan = _loan()
    with pytest.raises(CdasLifecycleError) as raised:
        _validate_loan_terms(
            loan,
            branch_id=uuid4(),
            deduction_amount=Decimal("500.00"),
            principal_amount=Decimal("6000.00"),
            total_installment=12,
            effective_month="2099-10",
        )
    assert raised.value.status_code == 403


def test_cdas_employee_identity_must_match_borrower():
    loan = _loan()
    _validate_employee_identity(
        loan,
        "EMP001",
        {
            "EmployeeNo": "EMP001",
            "Name": "Theko Mohau",
            "Surname": "Koetlisi",
            "DOB": "1990-05-14",
        },
    )


def test_cdas_employee_identity_rejects_wrong_name_or_dob():
    loan = _loan()
    with pytest.raises(CdasLifecycleError) as name_error:
        _validate_employee_identity(
            loan,
            "EMP001",
            {
                "EmployeeNo": "EMP001",
                "Name": "Someone Else",
                "Surname": "Koetlisi",
                "DOB": "1990-05-14",
            },
        )
    assert name_error.value.status_code == 409

    with pytest.raises(CdasLifecycleError) as dob_error:
        _validate_employee_identity(
            loan,
            "EMP001",
            {
                "EmployeeNo": "EMP001",
                "Name": "Theko",
                "Surname": "Koetlisi",
                "DOB": "1991-05-14",
            },
        )
    assert dob_error.value.status_code == 409


def test_cdas_date_parser_accepts_common_provider_formats():
    expected = date(1990, 5, 14)
    assert _parse_cdas_date("1990-05-14") == expected
    assert _parse_cdas_date("1990-05-14T00:00:00") == expected
    assert _parse_cdas_date("14/05/1990") == expected
    assert _parse_cdas_date("14-05-1990") == expected
