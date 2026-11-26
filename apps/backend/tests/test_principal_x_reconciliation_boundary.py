"""Unit tests for the internal locked reconciliation boundary."""
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from payment_engine.principal_x_bound_reconciliation import BoundLedgerReview
from payment_engine.principal_x_ledger_source_attestation import (
    LedgerSourceAttestation, REQUIRED_SOURCE_FAMILIES,
)
from services import principal_x_reconciliation_boundary as boundary


@pytest.fixture
def scenario(monkeypatch):
    company_id, loan_id = uuid4(), uuid4()
    calls = []
    db = SimpleNamespace(
        no_autoflush=nullcontext(), new=[], dirty=[], deleted=[],
        expire_all=lambda: calls.append("expire"),
    )
    review = BoundLedgerReview(
        company_id=company_id, loan_id=loan_id, source_revision="a" * 64,
        reviewed_at=datetime.now(timezone.utc),
        net_collected=Decimal("696.00"),
        attestations=tuple(
            LedgerSourceAttestation(family, True, "evidence:" + family, 0)
            for family in sorted(REQUIRED_SOURCE_FAMILIES)
        ),
    )
    def lock(session, **scope):
        assert session is db
        assert scope == dict(company_id=company_id, loan_id=loan_id)
        calls.append("lock")

    def fingerprint(session, **scope):
        assert session is db
        assert scope == dict(company_id=company_id, loan_id=loan_id)
        calls.append("fingerprint")
        return "a" * 64

    def read(**scope):
        assert scope == dict(company_id=company_id, loan_id=loan_id,
                             source_revision="a" * 64)
        calls.append("read")
        return review

    monkeypatch.setattr(boundary, "lock_financial_loan", lock)
    monkeypatch.setattr(boundary, "local_principal_x_source_revision", fingerprint)
    return SimpleNamespace(
        db=db, review=review, calls=calls, company_id=company_id, loan_id=loan_id,
        reader=SimpleNamespace(read_verified_review=read),
    )


def run(scenario, **kwargs):
    args = dict(company_id=scenario.company_id, loan_id=scenario.loan_id,
                reader=scenario.reader, max_age=timedelta(minutes=5))
    args.update(kwargs)
    return boundary.reconcile_locked_financial_sources(scenario.db, **args)


def test_complete_review_is_validated_after_two_locked_reads(scenario):
    result = run(scenario)
    assert result.net_collected == Decimal("696.00")
    assert result.source_count == 8
    assert scenario.calls == ["lock", "expire", "fingerprint", "read", "expire", "fingerprint"]


def test_no_reader_fails_closed(scenario):
    with pytest.raises(ValueError, match="No trusted"):
        run(scenario, reader=None)
    assert scenario.calls == []


@pytest.mark.parametrize("field", ["new", "dirty", "deleted"])
def test_pending_mutations_rejected(scenario, field):
    setattr(scenario.db, field, [object()])
    with pytest.raises(ValueError, match="clean financial session"):
        run(scenario)
    assert "read" not in scenario.calls


@pytest.mark.parametrize("value", [None, {}, True])
def test_missing_or_untyped_review_rejected(scenario, value):
    scenario.reader.read_verified_review = lambda **kw: value
    with pytest.raises(ValueError, match="review unavailable"):
        run(scenario)


def test_changed_sources_during_review_rejected(scenario, monkeypatch):
    revisions = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(boundary, "local_principal_x_source_revision",
                        lambda *a, **kw: next(revisions))
    with pytest.raises(ValueError, match="changed during reconciliation"):
        run(scenario)


@pytest.mark.parametrize("field", ["company_id", "loan_id", "source_revision", "reviewed_at", "attestations"])
def test_invalid_review_rejected(scenario, field):
    values = dict(company_id=uuid4(), loan_id=uuid4(), source_revision="b" * 64,
                  reviewed_at=datetime.now(timezone.utc) - timedelta(hours=1),
                  attestations=())
    scenario.reader.read_verified_review = lambda **kw: replace(
        scenario.review, **{field: values[field]}
    )
    with pytest.raises(ValueError):
        run(scenario)


def test_reader_failure_propagates_without_result(scenario):
    def fail(**kw):
        raise RuntimeError("Evidence repository unavailable")
    scenario.reader.read_verified_review = fail
    with pytest.raises(RuntimeError, match="repository unavailable"):
        run(scenario)
