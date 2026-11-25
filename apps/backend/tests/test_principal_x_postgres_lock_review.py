"""Guardrail tests for the read-only PostgreSQL Principal x lock adapter."""
from pathlib import Path
from uuid import uuid4

import pytest

from services.principal_x_postgres_lock_review import lock_principal_x_loan_for_review


class FakeBind:
    class dialect:
        name = "sqlite"


class FakeSession:
    def get_bind(self):
        return FakeBind()


def test_non_postgresql_adapter_rejected_before_query():
    with pytest.raises(ValueError, match="PostgreSQL required"):
        lock_principal_x_loan_for_review(
            FakeSession(), company_id=uuid4(), loan_id=uuid4()
        )


def test_invalid_tenant_identifiers_rejected():
    with pytest.raises(ValueError, match="UUID"):
        lock_principal_x_loan_for_review(
            FakeSession(), company_id="wrong", loan_id=uuid4()
        )


def test_review_adapter_never_claims_reconciliation():
    source = (
        Path(__file__).resolve().parents[1]
        / "services/principal_x_postgres_lock_review.py"
    ).read_text(encoding="utf-8")
    assert ".with_for_update()" in source
    assert "reconciled=False" in source
    assert "db.commit(" not in source
    assert "db.add(" not in source
    assert "db.execute(" not in source


def test_locked_source_review_orders_lock_before_evidence_queries(monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace
    from services import principal_x_postgres_lock_review as review
    from services.principal_x_transaction_coordinator import LockedLoanSnapshot

    company_id, loan_id = uuid4(), uuid4()
    events = []
    snapshot = LockedLoanSnapshot(
        company_id=company_id, loan_id=loan_id,
        original_principal=Decimal("1500"),
        authoritative_net_collected=Decimal("0"),
        live_policy_enabled=False, reconciled=False,
    )
    def lock(db, **kwargs):
        events.append("lock")
        assert kwargs == {"company_id": company_id, "loan_id": loan_id}
        return snapshot

    def audit(db, **kwargs):
        events.append("payment")
        return SimpleNamespace(payment_count=1, complete=False)

    def sources(db, **kwargs):
        events.append("cash_allocations_treasury")
        return SimpleNamespace(complete=False, orphan_allocation_count=1)

    monkeypatch.setattr(review, "lock_principal_x_loan_for_review", lock)
    monkeypatch.setattr(review, "inspect_loanhub_payment_evidence", audit)
    monkeypatch.setattr(review, "inspect_principal_x_collection_sources", sources)
    result = review.inspect_principal_x_sources_under_loan_lock(
        object(), company_id=company_id, loan_id=loan_id,
    )
    assert events == ["lock", "payment", "cash_allocations_treasury"]
    assert result.snapshot is snapshot
    assert result.payment_audit.payment_count == 1
    assert result.source_diagnostics.orphan_allocation_count == 1
    assert result.can_post is False


def test_locked_source_review_fails_before_evidence_queries_if_lock_fails(monkeypatch):
    from services import principal_x_postgres_lock_review as review

    calls = []
    def fail_lock(db, **kwargs):
        calls.append("lock")
        raise ValueError("Loan not found within company")

    def unexpected(db, **kwargs):
        calls.append("evidence")
        raise AssertionError("Should not inspect evidence without lock")

    monkeypatch.setattr(review, "lock_principal_x_loan_for_review", fail_lock)
    monkeypatch.setattr(review, "inspect_loanhub_payment_evidence", unexpected)
    monkeypatch.setattr(review, "inspect_principal_x_collection_sources", unexpected)
    with pytest.raises(ValueError, match="Loan not found"):
        review.inspect_principal_x_sources_under_loan_lock(
            object(), company_id=uuid4(), loan_id=uuid4(),
        )
    assert calls == ["lock"]


def test_locked_review_no_commit_and_never_certifies_payment():
    source = (
        Path(__file__).resolve().parents[1]
        / "services/principal_x_postgres_lock_review.py"
    ).read_text(encoding="utf-8")
    assert "with_for_update()" in source
    assert "inspect_loanhub_payment_evidence(" in source
    assert "inspect_principal_x_collection_sources(" in source
    assert "reconciled=False" in source
    assert "can_post=False" in source
    assert "db.commit(" not in source
    assert "db.flush(" not in source
    assert "db.add(" not in source



def test_scoped_claims_are_checked_only_after_locked_financial_review(monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace
    from services import principal_x_postgres_lock_review as review
    from services.principal_x_transaction_coordinator import LockedLoanSnapshot
    from payment_engine.principal_x_scoped_ledger_review import ScopedSourceAttestation
    from payment_engine.principal_x_ledger_source_attestation import REQUIRED_SOURCE_FAMILIES

    company_id, loan_id, revision = uuid4(), uuid4(), "a" * 64
    snapshot = LockedLoanSnapshot(
        company_id=company_id, loan_id=loan_id,
        original_principal=Decimal("1500"),
        authoritative_net_collected=Decimal("0"),
        live_policy_enabled=False, reconciled=False,
    )
    events = []
    def locked(db, **kwargs):
        events.append("lock_and_review")
        assert kwargs == {"company_id": company_id, "loan_id": loan_id}
        return review.LockedCollectionEvidenceReview(
            snapshot=snapshot,
            payment_audit=SimpleNamespace(complete=False),
            source_diagnostics=SimpleNamespace(complete=False),
            can_post=False,
        )

    original_validate = review.review_scoped_ledger_attestations
    def validate(**kwargs):
        events.append("scope_check")
        return original_validate(**kwargs)
    monkeypatch.setattr(review, "inspect_principal_x_sources_under_loan_lock", locked)
    monkeypatch.setattr(review, "review_scoped_ledger_attestations", validate)
    def server_revision(db, **kwargs):
        events.append("server_revision")
        assert kwargs == {"company_id": company_id, "loan_id": loan_id}
        return revision
    monkeypatch.setattr(review, "local_principal_x_source_revision", server_revision)
    attestations = tuple(
        ScopedSourceAttestation(
            family, company_id, loan_id, revision, "ref:" + family, True, 0,
        )
        for family in sorted(REQUIRED_SOURCE_FAMILIES)
    )
    result = review.inspect_scoped_principal_x_evidence_under_loan_lock(
        object(), company_id=company_id, loan_id=loan_id,
        snapshot_revision=revision, attestations=attestations,
    )
    assert events == ["lock_and_review", "server_revision", "scope_check", "server_revision"]
    assert result.scope_claims.independently_verified is False
    assert result.financial_sources.snapshot.reconciled is False
    assert result.can_post is False


def test_locked_scoped_review_rejects_mismatched_attestation_after_lock(monkeypatch):
    from decimal import Decimal
    from services import principal_x_postgres_lock_review as review
    from services.principal_x_transaction_coordinator import LockedLoanSnapshot
    from payment_engine.principal_x_scoped_ledger_review import ScopedSourceAttestation
    from payment_engine.principal_x_ledger_source_attestation import REQUIRED_SOURCE_FAMILIES

    company_id, loan_id, revision = uuid4(), uuid4(), "a" * 64
    snapshot = LockedLoanSnapshot(
        company_id=company_id, loan_id=loan_id,
        original_principal=Decimal("1500"),
        authoritative_net_collected=Decimal("0"),
        live_policy_enabled=False, reconciled=False,
    )
    calls = []
    def locked(db, **kwargs):
        calls.append("lock")
        return review.LockedCollectionEvidenceReview(
            snapshot=snapshot, payment_audit=None,
            source_diagnostics=None, can_post=False,
        )
    monkeypatch.setattr(review, "inspect_principal_x_sources_under_loan_lock", locked)
    monkeypatch.setattr(review, "local_principal_x_source_revision", lambda db, **kwargs: revision)
    attestations = tuple(
        ScopedSourceAttestation(
            family, uuid4() if i == 0 else company_id,
            loan_id, revision, "ref:" + family, True, 0,
        )
        for i, family in enumerate(sorted(REQUIRED_SOURCE_FAMILIES))
    )
    with pytest.raises(ValueError, match="Cross-tenant"):
        review.inspect_scoped_principal_x_evidence_under_loan_lock(
            object(), company_id=company_id, loan_id=loan_id,
            snapshot_revision=revision, attestations=attestations,
        )
    assert calls == ["lock"]


def test_locked_scoped_review_has_no_mutating_orm_calls():
    source = (
        Path(__file__).resolve().parents[1]
        / "services/principal_x_postgres_lock_review.py"
    ).read_text(encoding="utf-8")
    assert "inspect_scoped_principal_x_evidence_under_loan_lock" in source
    assert "review_scoped_ledger_attestations(" in source
    for forbidden in ("db.add(", "db.commit(", "db.flush(", "db.delete("):
        assert forbidden not in source



def test_caller_claims_cannot_override_server_revision_under_lock(monkeypatch):
    from decimal import Decimal
    from services import principal_x_postgres_lock_review as review
    from services.principal_x_transaction_coordinator import LockedLoanSnapshot
    from payment_engine.principal_x_scoped_ledger_review import ScopedSourceAttestation
    from payment_engine.principal_x_ledger_source_attestation import REQUIRED_SOURCE_FAMILIES

    company_id, loan_id, claimed = uuid4(), uuid4(), "a" * 64
    snapshot = LockedLoanSnapshot(
        company_id=company_id, loan_id=loan_id,
        original_principal=Decimal("1500"),
        authoritative_net_collected=Decimal("0"),
        live_policy_enabled=False, reconciled=False,
    )
    events = []
    def locked(db, **kwargs):
        events.append("lock")
        return review.LockedCollectionEvidenceReview(
            snapshot=snapshot, payment_audit=None,
            source_diagnostics=None, can_post=False,
        )
    def revision(db, **kwargs):
        events.append("server_revision")
        return "b" * 64
    def forbidden_validate(**kwargs):
        raise AssertionError("Should not validate untrusted claims against a stale revision")
    monkeypatch.setattr(review, "inspect_principal_x_sources_under_loan_lock", locked)
    monkeypatch.setattr(review, "local_principal_x_source_revision", revision)
    monkeypatch.setattr(review, "review_scoped_ledger_attestations", forbidden_validate)
    attestations = tuple(
        ScopedSourceAttestation(
            family, company_id, loan_id, claimed, "ref:" + family, True, 0,
        )
        for family in sorted(REQUIRED_SOURCE_FAMILIES)
    )
    with pytest.raises(ValueError, match="caller-supplied local source revision"):
        review.inspect_scoped_principal_x_evidence_under_loan_lock(
            object(), company_id=company_id, loan_id=loan_id,
            snapshot_revision=claimed, attestations=attestations,
        )
    assert events == ["lock", "server_revision"]



def test_revision_changing_during_scope_review_is_rejected(monkeypatch):
    from decimal import Decimal
    from services import principal_x_postgres_lock_review as review
    from services.principal_x_transaction_coordinator import LockedLoanSnapshot
    from payment_engine.principal_x_scoped_ledger_review import ScopedSourceAttestation
    from payment_engine.principal_x_ledger_source_attestation import REQUIRED_SOURCE_FAMILIES

    company_id, loan_id, claimed = uuid4(), uuid4(), "a" * 64
    snapshot = LockedLoanSnapshot(
        company_id=company_id, loan_id=loan_id,
        original_principal=Decimal("100.00"),
        authoritative_net_collected=Decimal("0.00"),
        live_policy_enabled=False, reconciled=False,
    )
    monkeypatch.setattr(
        review, "inspect_principal_x_sources_under_loan_lock",
        lambda db, **kwargs: review.LockedCollectionEvidenceReview(
            snapshot=snapshot, payment_audit=None,
            source_diagnostics=None, can_post=False,
        ),
    )
    revisions = iter([claimed, "b" * 64])
    monkeypatch.setattr(
        review, "local_principal_x_source_revision",
        lambda db, **kwargs: next(revisions),
    )
    attestations = tuple(
        ScopedSourceAttestation(
            family, company_id, loan_id, claimed, "audit:" + family, True, 0,
        )
        for family in sorted(REQUIRED_SOURCE_FAMILIES)
    )
    with pytest.raises(ValueError, match="changed during locked review"):
        review.inspect_scoped_principal_x_evidence_under_loan_lock(
            object(), company_id=company_id, loan_id=loan_id,
            snapshot_revision=claimed, attestations=attestations,
        )
