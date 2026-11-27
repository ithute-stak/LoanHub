from dataclasses import replace
from uuid import uuid4

import pytest

from payment_engine.principal_x_ledger_source_attestation import REQUIRED_SOURCE_FAMILIES
from payment_engine.principal_x_scoped_ledger_review import (
    ScopedSourceAttestation, review_scoped_ledger_attestations,
)


def case():
    company_id, loan_id, revision = uuid4(), uuid4(), "a" * 64
    rows = tuple(
        ScopedSourceAttestation(
            source_family=family, company_id=company_id,
            loan_id=loan_id, snapshot_revision=revision,
            evidence_reference="evidence:" + family, complete=True,
            unresolved_count=0,
        )
        for family in sorted(REQUIRED_SOURCE_FAMILIES)
    )
    return company_id, loan_id, revision, rows


def test_complete_consistent_claims_are_never_postable_or_verified():
    company_id, loan_id, revision, rows = case()
    result = review_scoped_ledger_attestations(
        company_id=company_id, loan_id=loan_id,
        snapshot_revision=revision, attestations=rows,
    )
    assert result.scope_claims_consistent is True
    assert result.independently_verified is False
    assert result.can_post is False
    assert result.source_count == len(REQUIRED_SOURCE_FAMILIES)


@pytest.mark.parametrize("field,value", [
    ("company_id", uuid4()),
    ("loan_id", uuid4()),
    ("snapshot_revision", "b" * 64),
    ("complete", False),
    ("unresolved_count", 1),
    ("unresolved_count", True),
    ("evidence_reference", ""),
    ("source_family", "unknown_source"),
])
def test_invalid_or_cross_tenant_source_claims_fail_closed(field, value):
    company_id, loan_id, revision, rows = case()
    altered = (replace(rows[0], **{field: value}),) + rows[1:]
    with pytest.raises(ValueError):
        review_scoped_ledger_attestations(
            company_id=company_id, loan_id=loan_id,
            snapshot_revision=revision, attestations=altered,
        )


def test_reused_evidence_reference_fails_closed():
    company_id, loan_id, revision, rows = case()
    altered = (replace(rows[0], evidence_reference=" " + rows[1].evidence_reference + " "),) + rows[1:]
    with pytest.raises(ValueError, match="Duplicate"):
        review_scoped_ledger_attestations(
            company_id=company_id, loan_id=loan_id,
            snapshot_revision=revision, attestations=altered,
        )


def test_missing_and_duplicate_family_fail_closed():
    company_id, loan_id, revision, rows = case()
    for candidates in (rows[:-1], rows + (rows[0],)):
        with pytest.raises(ValueError):
            review_scoped_ledger_attestations(
                company_id=company_id, loan_id=loan_id,
                snapshot_revision=revision, attestations=candidates,
            )


@pytest.mark.parametrize("revision", ["A" * 64, "z" * 64, "a" * 63, None])
def test_noncanonical_revision_fails_closed(revision):
    company_id, loan_id, _, rows = case()
    with pytest.raises(ValueError):
        review_scoped_ledger_attestations(
            company_id=company_id, loan_id=loan_id,
            snapshot_revision=revision, attestations=rows,
        )


def test_empty_history_cannot_claim_complete_sources():
    with pytest.raises(ValueError, match="Missing required"):
        review_scoped_ledger_attestations(
            company_id=uuid4(), loan_id=uuid4(),
            snapshot_revision="a" * 64, attestations=(),
        )
