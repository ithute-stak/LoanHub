"""Scope and freshness checks for trusted reconciliation evidence.

This is a structural gate, not an independent evidence verifier. Only a
future trusted server-side evidence adapter may construct reviewed evidence.
Never deserialize borrower-provided attestations into this contract.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from hmac import compare_digest
from uuid import UUID

from payment_engine.principal_x_ledger_source_attestation import (
    LedgerCompleteness,
    LedgerSourceAttestation,
    require_authoritative_ledger_attestations,
)


@dataclass(frozen=True)
class BoundLedgerReview:
    company_id: UUID
    loan_id: UUID
    source_revision: str
    reviewed_at: datetime
    net_collected: Decimal
    attestations: tuple[LedgerSourceAttestation, ...]


def validate_bound_ledger_review(
    review: BoundLedgerReview, *, company_id: UUID, loan_id: UUID,
    current_revision: str, now: datetime, max_age: timedelta,
) -> LedgerCompleteness:
    """Validate a trusted review against the current locked financial state.

    The caller must read the current revision under the shared loan lock.
    This function cannot establish the authenticity of underlying evidence
    or guarantee that every financial writer honors that lock.
    """
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified company and loan scope required")
    if review.company_id != company_id or review.loan_id != loan_id:
        raise ValueError("Ledger review scope mismatch")
    for revision in (review.source_revision, current_revision):
        if not isinstance(revision, str) or len(revision) != 64 or any(
            c not in "0123456789abcdef" for c in revision
        ):
            raise ValueError("Invalid financial source revision")
    if not compare_digest(review.source_revision, current_revision):
        raise ValueError("Ledger review is stale")
    if not isinstance(now, datetime) or not isinstance(review.reviewed_at, datetime):
        raise ValueError("Review chronology required")
    if now.utcoffset() is None or review.reviewed_at.utcoffset() is None:
        raise ValueError("Timezone-aware review chronology required")
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise ValueError("Positive review validity window required")
    age = now - review.reviewed_at
    if age < timedelta(0) or age > max_age:
        raise ValueError("Ledger review is outside its validity window")
    return require_authoritative_ledger_attestations(
        net_collected=review.net_collected, attestations=review.attestations,
    )
