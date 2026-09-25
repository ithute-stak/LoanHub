from decimal import Decimal

import pytest

from database.models.client_loan_company import (
    ClientCompanyLoan,
    _clear_stale_current_overdue_flag,
    loan_can_be_currently_overdue,
)
from database.models.enums import LoanStatus


@pytest.mark.parametrize(
    ("balance", "status"),
    [
        (Decimal("0.00"), LoanStatus.COMPLETED),
        (Decimal("0.00"), LoanStatus.ACTIVE),
        (Decimal("100.00"), LoanStatus.COMPLETED),
        (Decimal("100.00"), LoanStatus.CANCELLED),
        (Decimal("100.00"), LoanStatus.REJECTED),
    ],
)
def test_terminal_or_settled_loan_cannot_be_currently_overdue(balance, status):
    assert loan_can_be_currently_overdue(balance=balance, status=status) is False


def test_positive_active_balance_can_be_currently_overdue():
    assert loan_can_be_currently_overdue(
        balance=Decimal("100.00"),
        status=LoanStatus.ACTIVE,
    ) is True


def test_model_invariant_clears_stale_overdue_flag_for_settled_loan():
    loan = ClientCompanyLoan(
        balance=Decimal("0.00"),
        status=LoanStatus.COMPLETED,
        is_overdue=True,
    )

    _clear_stale_current_overdue_flag(None, None, loan)

    assert loan.is_overdue is False


def test_model_invariant_preserves_current_overdue_for_open_balance():
    loan = ClientCompanyLoan(
        balance=Decimal("100.00"),
        status=LoanStatus.ACTIVE,
        is_overdue=True,
    )

    _clear_stale_current_overdue_flag(None, None, loan)

    assert loan.is_overdue is True
