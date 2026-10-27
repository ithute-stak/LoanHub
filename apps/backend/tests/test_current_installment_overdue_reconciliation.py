"""Regression cases for current installment delinquency after late repayment."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from database.models.enums import InstallmentStatus
from services.maintenance_service import installment_is_currently_overdue


def installment(*, due="2026-10-21", paid="0", total="700", status=InstallmentStatus.PENDING, superseded=False):
    return SimpleNamespace(
        due_date=date.fromisoformat(due),
        paid_amount=Decimal(paid),
        total_due=Decimal(total),
        status=status,
        is_superseded=superseded,
    )


@pytest.mark.parametrize("row,expected", [
    (installment(paid="700", status=InstallmentStatus.PAID), False),
    (installment(paid="700", status=InstallmentStatus.OVERDUE), False),
    (installment(paid="400", status=InstallmentStatus.PARTIALLY_PAID), True),
    (installment(paid="0"), True),
    (installment(due="2026-11-21", paid="0"), False),
    (installment(paid="0", superseded=True), False),
    (installment(paid="0", status=InstallmentStatus.WAIVED), False),
])
def test_current_installment_overdue_state(row, expected):
    assert installment_is_currently_overdue(row, today=date(2026, 10, 27)) is expected


def test_payment_reversal_reopens_original_overdue_date():
    row = installment(paid="700", status=InstallmentStatus.PAID)
    assert not installment_is_currently_overdue(row, today=date(2026, 10, 27))
    row.paid_amount = Decimal("0")
    assert installment_is_currently_overdue(row, today=date(2026, 10, 27))
