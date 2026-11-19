from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from services.principal_x_posting_snapshot_gate import PostingSnapshot, assess_principal_x_posting


COMPANY = uuid4()
LOAN = uuid4()


def payment(**overrides):
    data = dict(
        company_id=COMPANY, loan_id=LOAN, idempotency_key="payment-1",
        direction=PaymentDirection.INBOUND,
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        status=PaymentStatus.SUCCEEDED, amount=Decimal("1500.00"),
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def gate(transactions=None, **overrides):
    data = dict(
        snapshot=PostingSnapshot(
            company_id=COMPANY, loan_id=LOAN,
            original_principal=Decimal("1000"),
            transactions=tuple([payment()] if transactions is None else transactions),
            reconciled_adjustments=True,
        ),
        proposed_amount=Decimal("500"),
        idempotency_key="payment-2", provider_confirmed=True,
        lock_held=True, live_policy_enabled=True,
    )
    data.update(overrides)
    return assess_principal_x_posting(**data)


def test_exact_ceiling_allowed():
    result = gate()
    assert result.remaining_allowance == Decimal("500.00")
    assert result.permitted


def test_over_ceiling_rejected():
    with pytest.raises(ValueError, match="ceiling"):
        gate(proposed_amount=Decimal("500.01"))


@pytest.mark.parametrize("change", [
    {"lock_held": False},
    {"provider_confirmed": False},
    {"live_policy_enabled": False},
])
def test_required_gates(change):
    with pytest.raises(ValueError, match="required"):
        gate(**change)


def test_unreconciled_adjustments_rejected():
    snapshot = PostingSnapshot(
        company_id=COMPANY, loan_id=LOAN, original_principal=Decimal("1000"),
        transactions=(payment(),), reconciled_adjustments=False,
    )
    with pytest.raises(ValueError, match="reconciliation"):
        gate(snapshot=snapshot)


@pytest.mark.parametrize("changed", [
    {"company_id": uuid4()},
    {"loan_id": uuid4()},
    {"status": PaymentStatus.REVERSED},
    {"status": PaymentStatus.PENDING},
    {"direction": PaymentDirection.OUTBOUND},
    {"purpose": PaymentPurpose.REFUND},
    {"amount": Decimal("NaN")},
])
def test_unsafe_history_rejected(changed):
    with pytest.raises(ValueError):
        gate(transactions=[payment(**changed)])


def test_duplicate_historical_idempotency_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        gate(transactions=[payment(), payment()])


def test_replay_key_rejected():
    with pytest.raises(ValueError, match="Existing idempotency"):
        gate(idempotency_key="payment-1")
