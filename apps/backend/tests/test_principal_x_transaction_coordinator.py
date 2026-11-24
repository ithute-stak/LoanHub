from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from services.principal_x_transaction_coordinator import (
    LockedLoanSnapshot, VerifiedCollection, coordinate_principal_x_collection,
)


COMPANY, LOAN = uuid4(), uuid4()


class FakeTransaction:
    """Test double only; NOT a database implementation."""

    def __init__(self, *, collected="1500", live=True, reconciled=True, provider_final=True):
        self.snapshot = LockedLoanSnapshot(
            company_id=COMPANY, loan_id=LOAN,
            original_principal=Decimal("1000"),
            authoritative_net_collected=Decimal(collected),
            live_policy_enabled=live, reconciled=reconciled,
        )
        self.provider_final = provider_final
        self.calls = []
        self.rolled_back = False

    def __enter__(self):
        self.calls.append("begin")
        return self

    def __exit__(self, kind, value, traceback):
        self.rolled_back = kind is not None
        self.calls.append("rollback" if kind else "commit")
        return False

    def lock_loan_and_reconcile(self, **kwargs):
        self.calls.append("lock")
        return self.snapshot

    def assert_provider_final(self, **kwargs):
        self.calls.append("verify")
        if not self.provider_final:
            raise ValueError("Provider not final")

    def reserve_unique_collection(self, **kwargs):
        self.calls.append("reserve")

    def persist_collection(self, **kwargs):
        self.calls.append("persist")
        return "payment-123"


def instruction(amount="500"):
    return VerifiedCollection(
        company_id=COMPANY, loan_id=LOAN, amount=Decimal(amount),
        idempotency_key="unique-1", provider_reference="provider-1",
        verification_reference="verified-1",
    )


def test_coordinator_order_and_ceiling():
    tx = FakeTransaction()
    result = coordinate_principal_x_collection(transaction=tx, instruction=instruction())
    assert result.payment_reference == "payment-123"
    assert result.ceiling.remaining_allowance == Decimal("500.00")
    assert tx.calls == ["begin", "lock", "verify", "reserve", "persist", "commit"]


def test_over_cap_rolls_back_without_reservation():
    tx = FakeTransaction()
    with pytest.raises(ValueError, match="ceiling"):
        coordinate_principal_x_collection(transaction=tx, instruction=instruction("500.01"))
    assert tx.calls == ["begin", "lock", "verify", "rollback"]


def test_provider_not_final_rolls_back():
    tx = FakeTransaction(provider_final=False)
    with pytest.raises(ValueError, match="Provider not final"):
        coordinate_principal_x_collection(transaction=tx, instruction=instruction())
    assert tx.calls == ["begin", "lock", "verify", "rollback"]


@pytest.mark.parametrize("options", [
    {"live": False}, {"reconciled": False},
])
def test_disabled_or_unreconciled_fails_closed(options):
    tx = FakeTransaction(**options)
    with pytest.raises(ValueError, match="required"):
        coordinate_principal_x_collection(transaction=tx, instruction=instruction())
    assert "reserve" not in tx.calls
    assert tx.rolled_back


def test_cross_tenant_snapshot_rejected():
    tx = FakeTransaction()
    tx.snapshot = replace(tx.snapshot, company_id=uuid4())
    with pytest.raises(ValueError, match="mismatch"):
        coordinate_principal_x_collection(transaction=tx, instruction=instruction())
    assert tx.rolled_back


def test_missing_provider_evidence_fails_before_transaction():
    tx = FakeTransaction()
    with pytest.raises(ValueError, match="evidence"):
        coordinate_principal_x_collection(
            transaction=tx,
            instruction=replace(instruction(), verification_reference=""),
        )
    assert tx.calls == []


def test_reservation_failure_rolls_back_before_post():
    tx = FakeTransaction()

    def reject(**kwargs):
        tx.calls.append("reserve")
        raise ValueError("Unique key already exists")

    tx.reserve_unique_collection = reject
    with pytest.raises(ValueError, match="Unique key"):
        coordinate_principal_x_collection(transaction=tx, instruction=instruction())
    assert tx.calls == ["begin", "lock", "verify", "reserve", "rollback"]
