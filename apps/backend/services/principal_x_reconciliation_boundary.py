"""Internal reconciliation boundary; not a payment or posting endpoint."""
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from payment_engine.principal_x_bound_reconciliation import (
    BoundLedgerReview, validate_bound_ledger_review,
)
from payment_engine.principal_x_ledger_source_attestation import LedgerCompleteness
from services.principal_x_financial_lock import lock_financial_loan
from services.principal_x_locked_source_revision import local_principal_x_source_revision


class TrustedLedgerReviewReader(Protocol):
    """Server-configured reader of independently authenticated evidence only.

    Implementations must not manufacture reviews from diagnostic rows or
    accept borrower-supplied assertions. Read previously verified evidence;
    do not perform network calls or commit while the loan lock is held.
    """

    def read_verified_review(self, *, company_id: UUID, loan_id: UUID,
                             source_revision: str) -> BoundLedgerReview | None:
        ...


def reconcile_locked_financial_sources(
    db: Session, *, company_id: UUID, loan_id: UUID,
    reader: TrustedLedgerReviewReader | None,
    max_age: timedelta,
) -> LedgerCompleteness:
    """Reject absent, stale or mismatched evidence; leave transaction open.

    This boundary has no configured production reader and no posting route.
    A result is not a consent, payment, or settlement authorization.
    """
    if reader is None:
        raise ValueError("No trusted financial evidence reader configured")
    with db.no_autoflush:
        lock_financial_loan(db, company_id=company_id, loan_id=loan_id)
        # Refresh any financial records previously loaded into the identity map.
        if db.new or db.dirty or db.deleted:
            raise ValueError("Reconciliation requires a clean financial session")
        db.expire_all()
        revision = local_principal_x_source_revision(
            db, company_id=company_id, loan_id=loan_id,
        )
        review = reader.read_verified_review(
            company_id=company_id, loan_id=loan_id, source_revision=revision,
        )
        if not isinstance(review, BoundLedgerReview):
            raise ValueError("Independently verified ledger review unavailable")
        db.expire_all()
        current = local_principal_x_source_revision(
            db, company_id=company_id, loan_id=loan_id,
        )
        if current != revision:
            raise ValueError("Financial sources changed during reconciliation")
        return validate_bound_ledger_review(
            review, company_id=company_id, loan_id=loan_id,
            current_revision=current, now=datetime.now(timezone.utc),
            max_age=max_age,
        )
