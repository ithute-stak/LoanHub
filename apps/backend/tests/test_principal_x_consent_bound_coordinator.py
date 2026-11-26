from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payment_engine.principal_x_provider_finality import ProviderFinalityEvidence
from payment_engine.principal_x_settlement import PrincipalXQuote
from payment_engine.principal_x_settlement_consent import (
    BorrowerAcceptance, issue_settlement_offer,
)
from services.principal_x_consent_bound_coordinator import (
    coordinate_consent_bound_principal_x_settlement,
)
from services.principal_x_settlement_preview_service import PrincipalXSnapshotQuote
from services.principal_x_transaction_coordinator import (
    LockedLoanSnapshot, VerifiedCollection,
)


COMPANY, LOAN = uuid4(), uuid4()
NOW = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)
REV = "a" * 64
DATE = date(2026, 11, 24)


def inputs():
    quote = PrincipalXQuote(
        period=2, uncapped_due=Decimal("1324.80"),
        collectible_due=Decimal("1324.80"),
        contractual_remaining=Decimal("1392.00"),
        lifetime_cap_remaining=Decimal("2304.00"),
        total_credited=Decimal("696.00"),
        ceiling_reduction=Decimal("0.00"),
    )
    offer = issue_settlement_offer(
        loan_id=LOAN, company_id=COMPANY, quote=quote,
        issued_at=NOW, expires_at=NOW + timedelta(minutes=20),
        ledger_revision="verified-ledger-v1",
    )
    acceptance = BorrowerAcceptance(
        loan_id=LOAN, company_id=COMPANY,
        accepted_amount=Decimal("1324.80"),
        accepted_at=NOW + timedelta(minutes=2),
        ledger_revision="verified-ledger-v1",
        verified_identity=True,
        consent_evidence_id="consent-1",
    )
    instruction = VerifiedCollection(
        company_id=COMPANY, loan_id=LOAN, amount=Decimal("1324.80"),
        idempotency_key="idem-1", provider_reference="provider-1",
        verification_reference="verified-1",
    )
    return offer, acceptance, instruction


class TransactionDouble:
    def __init__(self, offer):
        self.calls = []
        self.snapshot = LockedLoanSnapshot(
            company_id=COMPANY, loan_id=LOAN,
            original_principal=Decimal("1500.00"),
            authoritative_net_collected=Decimal("696.00"),
            live_policy_enabled=True, reconciled=True,
        )
        self.ledger_revision = "verified-ledger-v1"
        self.quote = PrincipalXSnapshotQuote(quote=offer.quote, snapshot_revision=REV)
        self.evidence = ProviderFinalityEvidence(
            company_id=COMPANY, loan_id=LOAN,
            provider="mpesa", provider_reference="provider-1",
            verification_reference="verified-1", idempotency_key="idem-1",
            amount=Decimal("1324.80"), currency="LSL", final_status="succeeded",
            verified_at=datetime.now(timezone.utc) - timedelta(minutes=1),
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

    def read_authoritative_ledger_revision(self, **kwargs):
        self.calls.append("ledger")
        return self.ledger_revision

    def read_current_quote_under_lock(self, **kwargs):
        self.calls.append("quote")
        return self.quote

    def verify_borrower_acceptance_evidence(self, **kwargs):
        self.calls.append("consent")

    def obtain_verified_provider_evidence(self, **kwargs):
        self.calls.append("provider")
        return self.evidence

    def reserve_unique_collection(self, **kwargs):
        self.calls.append("reserve")

    def persist_collection(self, **kwargs):
        self.calls.append("persist")
        return "payment-1"


def run(tx, offer, acceptance, instruction, **kwargs):
    args = dict(
        transaction=tx, offer=offer, acceptance=acceptance,
        instruction=instruction, quoted_snapshot_revision=REV,
        settlement_date=DATE, now=NOW + timedelta(minutes=3),
    )
    args.update(kwargs)
    return coordinate_consent_bound_principal_x_settlement(**args)


def test_full_consent_bound_contract_checks_before_reserving():
    offer, acceptance, instruction = inputs()
    tx = TransactionDouble(offer)
    result = run(tx, offer, acceptance, instruction)
    assert result.payment_reference == "payment-1"
    assert result.ceiling.permitted is True
    assert tx.calls == [
        "begin", "lock", "ledger", "quote", "consent",
        "provider", "reserve", "persist", "commit",
    ]


@pytest.mark.parametrize("problem", [
    "stale_quote", "stale_ledger", "missing_consent", "wrong_provider",
    "disabled", "cap", "duplicate",
])
def test_rejected_evidence_or_duplicate_never_persists(problem):
    offer, acceptance, instruction = inputs()
    tx = TransactionDouble(offer)
    if problem == "stale_quote":
        tx.quote = replace(tx.quote, snapshot_revision="b" * 64)
    elif problem == "stale_ledger":
        tx.ledger_revision = "verified-ledger-v2"
    elif problem == "missing_consent":
        def invalid(**kwargs):
            tx.calls.append("consent")
            raise ValueError("Consent evidence not verified")
        tx.verify_borrower_acceptance_evidence = invalid
    elif problem == "wrong_provider":
        tx.evidence = replace(tx.evidence, amount=Decimal("1324.79"))
    elif problem == "disabled":
        tx.snapshot = replace(tx.snapshot, live_policy_enabled=False)
    elif problem == "cap":
        tx.snapshot = replace(tx.snapshot, authoritative_net_collected=Decimal("2000"))
    elif problem == "duplicate":
        def duplicate(**kwargs):
            tx.calls.append("reserve")
            raise ValueError("Duplicate idempotency key")
        tx.reserve_unique_collection = duplicate
    with pytest.raises(ValueError):
        run(tx, offer, acceptance, instruction)
    assert "persist" not in tx.calls
    assert tx.calls[-1] == "rollback"


def test_pre_transaction_mismatch_never_enters_adapter():
    offer, acceptance, instruction = inputs()
    tx = TransactionDouble(offer)
    with pytest.raises(ValueError, match="must equal"):
        run(tx, offer, acceptance, replace(instruction, amount=Decimal("1284.00")))
    assert tx.calls == []
