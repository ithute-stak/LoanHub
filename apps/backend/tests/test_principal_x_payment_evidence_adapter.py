"""Contract tests for the real LoanHub payment evidence adapter."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from services.principal_x_payment_evidence_adapter import inspect_loanhub_payment_evidence


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return FakeQuery(self.rows)


def payment(purpose, direction, status):
    return SimpleNamespace(
        id=uuid4(), purpose=purpose, direction=direction, status=status,
        amount=Decimal("100.00"), currency="LSL",
    )


def test_succeeded_repayment_remains_unverified():
    result = inspect_loanhub_payment_evidence(
        FakeSession([payment(PaymentPurpose.LOAN_REPAYMENT,
                             PaymentDirection.INBOUND, PaymentStatus.SUCCEEDED)]),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.payment_count == 1
    assert result.preview.net_collected is None
    assert result.complete is False


def test_succeeded_refund_requires_original_payment_link():
    result = inspect_loanhub_payment_evidence(
        FakeSession([payment(PaymentPurpose.REFUND,
                             PaymentDirection.OUTBOUND, PaymentStatus.SUCCEEDED)]),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert len(result.unresolved_payment_ids) == 1
    assert result.preview.net_collected is None


@pytest.mark.parametrize("status", [
    PaymentStatus.PENDING, PaymentStatus.PROCESSING,
    PaymentStatus.FAILED, PaymentStatus.CANCELLED, PaymentStatus.REVERSED,
])
def test_non_successful_statuses_never_authorize_posting(status):
    result = inspect_loanhub_payment_evidence(
        FakeSession([payment(PaymentPurpose.LOAN_REPAYMENT,
                             PaymentDirection.INBOUND, status)]),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.preview.net_collected is None
    assert result.complete is False


def test_empty_history_is_not_certified():
    result = inspect_loanhub_payment_evidence(
        FakeSession([]), company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.payment_count == 0
    assert result.complete is False
