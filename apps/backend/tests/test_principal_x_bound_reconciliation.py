"""Negative and positive tests for scope-bound ledger review validation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payment_engine.principal_x_bound_reconciliation import (
    BoundLedgerReview, validate_bound_ledger_review,
)
from payment_engine.principal_x_ledger_source_attestation import (
    LedgerSourceAttestation, REQUIRED_SOURCE_FAMILIES,
)


@pytest.fixture
def review():
    return BoundLedgerReview(
        company_id=uuid4(), loan_id=uuid4(), source_revision="a" * 64,
        reviewed_at=datetime(2026, 11, 26, 9, tzinfo=timezone.utc),
        net_collected=Decimal("696.00"),
        attestations=tuple(
            LedgerSourceAttestation(family, True, "audit:" + family, 0)
            for family in sorted(REQUIRED_SOURCE_FAMILIES)
        ),
    )


def validate(review, **overrides):
    context = dict(company_id=review.company_id, loan_id=review.loan_id,
                   current_revision="a" * 64,
                   now=datetime(2026, 11, 26, 9, 5, tzinfo=timezone.utc),
                   max_age=timedelta(minutes=10))
    context.update(overrides)
    return validate_bound_ledger_review(review, **context)


def test_complete_bound_review(review):
    result = validate(review)
    assert result.reconciled is True
    assert result.source_count == 8
    assert result.net_collected == Decimal("696.00")


@pytest.mark.parametrize("field", ["company_id", "loan_id"])
def test_wrong_scope(review, field):
    with pytest.raises(ValueError, match="scope mismatch"):
        validate(review, **{field: uuid4()})


@pytest.mark.parametrize("revision", ["b" * 64, "A" * 64, "a" * 63, None])
def test_stale_or_invalid_revision(review, revision):
    with pytest.raises(ValueError):
        validate(review, current_revision=revision)


@pytest.mark.parametrize("minutes", [-1, 11])
def test_future_or_expired_review(review, minutes):
    with pytest.raises(ValueError, match="validity window"):
        validate(review, now=review.reviewed_at + timedelta(minutes=minutes))


def test_naive_timestamp_rejected(review):
    with pytest.raises(ValueError, match="Timezone-aware"):
        validate(replace(review, reviewed_at=review.reviewed_at.replace(tzinfo=None)))


@pytest.mark.parametrize("age", [timedelta(0), timedelta(seconds=-1), None])
def test_invalid_validity_window(review, age):
    with pytest.raises(ValueError, match="Positive review"):
        validate(review, max_age=age)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "incomplete", "unresolved", "same_reference"])
def test_invalid_evidence(review, kind):
    rows = review.attestations
    if kind == "missing":
        rows = rows[:-1]
    elif kind == "duplicate":
        rows = rows + (rows[0],)
    elif kind == "incomplete":
        rows = (replace(rows[0], complete=False),) + rows[1:]
    elif kind == "unresolved":
        rows = (replace(rows[0], unresolved_count=1),) + rows[1:]
    else:
        rows = (replace(rows[0], evidence_reference=rows[1].evidence_reference),) + rows[1:]
    with pytest.raises(ValueError):
        validate(replace(review, attestations=rows))


@pytest.mark.parametrize("amount", ["-1", "0.001", "NaN", "Infinity"])
def test_invalid_net_collection(review, amount):
    with pytest.raises(ValueError):
        validate(replace(review, net_collected=Decimal(amount)))
