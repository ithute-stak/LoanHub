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
