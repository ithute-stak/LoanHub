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


def test_corrupt_amount_fails_closed_without_raising():
    broken = payment(PaymentPurpose.LOAN_REPAYMENT,
                     PaymentDirection.INBOUND, PaymentStatus.SUCCEEDED)
    broken.amount = "not-a-number"
    result = inspect_loanhub_payment_evidence(
        FakeSession([broken]), company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.preview.net_collected is None
    assert any("invalid_amount" in reason for reason in result.preview.unresolved)


def test_duplicate_payment_ids_are_unresolved():
    original = payment(PaymentPurpose.LOAN_REPAYMENT,
                       PaymentDirection.INBOUND, PaymentStatus.SUCCEEDED)
    result = inspect_loanhub_payment_evidence(
        FakeSession([original, original]), company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.preview.net_collected is None
    assert "missing_or_duplicate_payment_id" in result.preview.unresolved


def test_refund_and_reversal_counts_do_not_certify_ledger():
    refunded = payment(PaymentPurpose.REFUND, PaymentDirection.OUTBOUND, PaymentStatus.SUCCEEDED)
    reversed_payment = payment(PaymentPurpose.LOAN_REPAYMENT, PaymentDirection.INBOUND, PaymentStatus.REVERSED)
    result = inspect_loanhub_payment_evidence(
        FakeSession([refunded, reversed_payment]),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.refund_payment_count == 1
    assert result.reversed_payment_count == 1
    assert result.nonfinal_refund_count == 0
    assert result.preview.net_collected is None
    assert result.complete is False


@pytest.mark.parametrize("status,direction", [
    (PaymentStatus.PENDING, PaymentDirection.OUTBOUND),
    (PaymentStatus.FAILED, PaymentDirection.OUTBOUND),
    (PaymentStatus.SUCCEEDED, PaymentDirection.INBOUND),
])
def test_unfinished_or_wrong_direction_refunds_are_explicitly_counted(status, direction):
    result = inspect_loanhub_payment_evidence(
        FakeSession([payment(PaymentPurpose.REFUND, direction, status)]),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.refund_payment_count == 1
    assert result.nonfinal_refund_count == 1
    assert result.complete is False
