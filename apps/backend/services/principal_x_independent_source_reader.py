"""Compose approved local evidence with independent source verification.

No verifier is configured here. An implementation must read authenticated,
revocation-aware evidence from a trusted server-side store, not return
assertions based on the local proposal or borrower inputs. No network calls
or commits are permitted under the loan lock.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from payment_engine.principal_x_bound_reconciliation import BoundLedgerReview, validate_bound_ledger_review
from payment_engine.principal_x_ledger_source_attestation import REQUIRED_SOURCE_FAMILIES
from services.principal_x_evidence_repository import read_approved_local_review


@dataclass(frozen=True)
class IndependentSourceVerification:
    company_id: UUID
    loan_id: UUID
    source_revision: str
    source_family: str
    evidence_reference: str
    authenticated: bool
    revoked: bool
    complete: bool
    unresolved_count: int
    verified_at: datetime
    valid_until: datetime
    # Each source must bind to the same independently reconciled lifetime
    # total; these are not additive amounts.
    reconciled_net_collected: Decimal


class IndependentSourceVerifier(Protocol):
    def read_verified_source(
        self, *, company_id: UUID, loan_id: UUID, source_revision: str,
        source_family: str, evidence_reference: str,
    ) -> IndependentSourceVerification | None:
        ...


class IndependentlyVerifiedLedgerReader:
    """Fail-closed adapter for the locked reconciliation boundary."""

    def __init__(self, db: Session, *, verifier: IndependentSourceVerifier | None,
                 max_age: timedelta):
        if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
            raise ValueError("Positive evidence validity window required")
        self._db = db
        self._verifier = verifier
        self._max_age = max_age

    def read_verified_review(self, *, company_id: UUID, loan_id: UUID,
                             source_revision: str) -> BoundLedgerReview | None:
        if self._verifier is None:
            raise ValueError("Independent financial source verifier unavailable")
        if self._db.new or self._db.dirty or self._db.deleted:
            raise ValueError("Clean financial session required")
        review = read_approved_local_review(
            self._db, company_id=company_id, loan_id=loan_id,
            source_revision=source_revision,
        )
        if review is None:
            return None
        now = datetime.now(timezone.utc)
        completeness = validate_bound_ledger_review(
            review, company_id=company_id, loan_id=loan_id,
            current_revision=source_revision, now=now, max_age=self._max_age,
        )
        verified = set()
        with self._db.no_autoflush:
            for attestation in review.attestations:
                result = self._verifier.read_verified_source(
                    company_id=company_id, loan_id=loan_id,
                    source_revision=source_revision,
                    source_family=attestation.source_family,
                    evidence_reference=attestation.evidence_reference,
                )
                if self._db.new or self._db.dirty or self._db.deleted:
                    raise ValueError("Source verifier must not modify financial session")
                if not isinstance(result, IndependentSourceVerification):
                    raise ValueError("Independent financial source evidence unavailable")
                if (
                    result.company_id != company_id or result.loan_id != loan_id
                    or result.source_revision != source_revision
                    or result.source_family != attestation.source_family
                    or result.evidence_reference != attestation.evidence_reference
                    or result.authenticated is not True or result.revoked is not False
                    or result.complete is not True
                    or type(result.unresolved_count) is not int or result.unresolved_count != 0
                    or not isinstance(result.reconciled_net_collected, Decimal)
                    or not result.reconciled_net_collected.is_finite()
                    or result.reconciled_net_collected != completeness.net_collected
                ):
                    raise ValueError("Independent financial source evidence mismatch")
                if (
                    not isinstance(result.verified_at, datetime)
                    or not isinstance(result.valid_until, datetime)
                    or result.verified_at.utcoffset() is None
                    or result.valid_until.utcoffset() is None
                    or result.verified_at > now
                    or now - result.verified_at > self._max_age
                    or result.valid_until <= now
                ):
                    raise ValueError("Independent financial source evidence expired or invalid")
                verified.add(result.source_family)
        if verified != REQUIRED_SOURCE_FAMILIES:
            raise ValueError("Independent financial source coverage incomplete")
        return review
