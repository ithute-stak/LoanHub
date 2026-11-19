from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payment_engine.principal_x_provider_finality import ProviderFinalityEvidence
from services.principal_x_evidence_bound_coordinator import coordinate_evidence_bound_collection
from services.principal_x_transaction_coordinator import LockedLoanSnapshot, VerifiedCollection


COMPANY, LOAN = uuid4(), uuid4()


def instruction():
    return VerifiedCollection(
        company_id=COMPANY, loan_id=LOAN, amount=Decimal("500"),
        idempotency_key="idem-1", provider_reference="provider-1",
        verification_reference="verified-1",
    )


class TransactionDouble:
    def __init__(self):
        self.calls = []
        self.snapshot = LockedLoanSnapshot(
            company_id=COMPANY, loan_id=LOAN,
            original_principal=Decimal("1000"),
            authoritative_net_collected=Decimal("1500"),
            live_policy_enabled=True, reconciled=True,
        )
        self.evidence = ProviderFinalityEvidence(
            company_id=COMPANY, loan_id=LOAN,
            provider="mpesa", provider_reference="provider-1",
            verification_reference="verified-1", idempotency_key="idem-1",
            amount=Decimal("500"), currency="LSL", final_status="succeeded",
            verified_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            independently_verified=True,
        )

    def __enter__(self):
        self.calls.append("begin")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.calls.append("rollback" if exc_type else "commit")
        return False

    def lock_loan_and_reconcile(self, **kwargs):
        self.calls.append("lock")
        return self.snapshot

    def obtain_verified_provider_evidence(self, **kwargs):
        self.calls.append("verify")
        return self.evidence

    def reserve_unique_collection(self, **kwargs):
        self.calls.append("reserve")

    def persist_collection(self, **kwargs):
        self.calls.append("persist")
        return "payment-1"


def test_valid_provider_evidence_then_reservation():
    tx = TransactionDouble()
    result = coordinate_evidence_bound_collection(transaction=tx, instruction=instruction())
    assert result.payment_reference == "payment-1"
    assert tx.calls == ["begin", "lock", "verify", "reserve", "persist", "commit"]


@pytest.mark.parametrize("changes", [
    {"independently_verified": False},
    {"final_status": "pending"},
    {"amount": Decimal("499.99")},
    {"company_id": uuid4()},
    {"provider_reference": "wrong"},
    {"idempotency_key": "wrong"},
    {"verification_reference": "wrong"},
])
def test_invalid_evidence_rolls_back_before_reservation(changes):
    tx = TransactionDouble()
    tx.evidence = replace(tx.evidence, **changes)
    with pytest.raises(ValueError):
        coordinate_evidence_bound_collection(transaction=tx, instruction=instruction())
    assert tx.calls == ["begin", "lock", "verify", "rollback"]


def test_ceiling_rejection_prevents_reservation():
    tx = TransactionDouble()
    tx.snapshot = replace(tx.snapshot, authoritative_net_collected=Decimal("1800"))
    with pytest.raises(ValueError, match="ceiling"):
        coordinate_evidence_bound_collection(transaction=tx, instruction=instruction())
    assert tx.calls == ["begin", "lock", "verify", "rollback"]


def test_duplicate_reservation_fails_closed():
    tx = TransactionDouble()

    def duplicate(**kwargs):
        tx.calls.append("reserve")
        raise ValueError("Unique constraint violation")

    tx.reserve_unique_collection = duplicate
    with pytest.raises(ValueError, match="Unique"):
        coordinate_evidence_bound_collection(transaction=tx, instruction=instruction())
    assert tx.calls == ["begin", "lock", "verify", "reserve", "rollback"]
