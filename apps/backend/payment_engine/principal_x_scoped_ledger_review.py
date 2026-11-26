"""Non-postable review of loan-scoped authoritative source attestations.

This module checks provenance *claims*, not authenticity. Independent provider
and ledger adapters must verify the underlying records inside a controlled
transaction before anyone can certify lifetime net collections. This review
can never authorize a payment.
"""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from payment_engine.principal_x_ledger_source_attestation import REQUIRED_SOURCE_FAMILIES


@dataclass(frozen=True)
class ScopedSourceAttestation:
    source_family: str
    company_id: UUID
    loan_id: UUID
    snapshot_revision: str
    evidence_reference: str
    complete: bool
    unresolved_count: int


@dataclass(frozen=True)
class ScopedLedgerReview:
    company_id: UUID
    loan_id: UUID
    snapshot_revision: str
    source_count: int
    scope_claims_consistent: bool = True
    independently_verified: Literal[False] = False
    can_post: Literal[False] = False


def review_scoped_ledger_attestations(
    *, company_id: UUID, loan_id: UUID, snapshot_revision: str,
    attestations: tuple[ScopedSourceAttestation, ...],
) -> ScopedLedgerReview:
    """Fail closed on reused, wrong-tenant, wrong-loan or stale scope claims.

    A passing review means only that the supplied statements are internally
    consistent. It does NOT attest real provider or historical evidence.
    """
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified company and loan UUIDs required")
    if (
        not isinstance(snapshot_revision, str)
        or len(snapshot_revision) != 64
        or any(c not in "0123456789abcdef" for c in snapshot_revision)
    ):
        raise ValueError("Canonical SHA-256 snapshot revision required")

    seen_sources: set[str] = set()
    seen_references: set[str] = set()
    for item in attestations:
        if item.company_id != company_id or item.loan_id != loan_id:
            raise ValueError("Cross-tenant or cross-loan attestation")
        if item.snapshot_revision != snapshot_revision:
            raise ValueError("Stale or unrelated attestation snapshot")
        if item.source_family not in REQUIRED_SOURCE_FAMILIES:
            raise ValueError("Unknown ledger source family")
        if item.source_family in seen_sources:
            raise ValueError("Duplicate ledger source family")
        if item.complete is not True:
            raise ValueError("Incomplete ledger source")
        if type(item.unresolved_count) is not int or item.unresolved_count != 0:
            raise ValueError("Unresolved ledger source")
        if not isinstance(item.evidence_reference, str) or not item.evidence_reference.strip():
            raise ValueError("Source evidence reference required")
        reference = item.evidence_reference.strip()
        if reference in seen_references:
            raise ValueError("Duplicate source evidence reference")
        seen_references.add(reference)
        seen_sources.add(item.source_family)

    if seen_sources != REQUIRED_SOURCE_FAMILIES:
        raise ValueError("Missing required ledger source families")
    return ScopedLedgerReview(
        company_id=company_id, loan_id=loan_id,
        snapshot_revision=snapshot_revision,
        source_count=len(seen_sources),
        scope_claims_consistent=True,
        independently_verified=False,
        can_post=False,
    )
