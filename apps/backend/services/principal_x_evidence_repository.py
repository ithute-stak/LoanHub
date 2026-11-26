"""Read approved local evidence without asserting independent provider authenticity."""
from dataclasses import asdict
from datetime import timezone
from hmac import compare_digest
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.governance_control import ApprovalRequest
from database.models.principal_x_ledger_review import PrincipalXLedgerReview
from payment_engine.principal_x_bound_reconciliation import BoundLedgerReview
from payment_engine.principal_x_ledger_source_attestation import LedgerSourceAttestation
from services.principal_x_maker_submission import REVIEW_ACTION
from services.principal_x_review_digest import ledger_review_digest


def read_approved_local_review(
    db: Session, *, company_id: UUID, loan_id: UUID, source_revision: str,
) -> BoundLedgerReview | None:
    """Check immutable storage against its approval record.

    Caller must hold the scoped loan lock. This is deliberately NOT an
    implementation of TrustedLedgerReviewReader: independent source
    authenticity and revocation still require a separate verifier.
    """
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified review scope required")
    if not isinstance(source_revision, str) or len(source_revision) != 64 or any(
        c not in "0123456789abcdef" for c in source_revision
    ):
        raise ValueError("Invalid financial revision")
    with db.no_autoflush:
        rows = db.execute(
            select(PrincipalXLedgerReview).where(
                PrincipalXLedgerReview.company_id == company_id,
                PrincipalXLedgerReview.loan_id == loan_id,
                PrincipalXLedgerReview.source_revision == source_revision,
            ).limit(2).execution_options(populate_existing=True)
        ).scalars().all()
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError("Ambiguous approved ledger reviews")
        row = rows[0]
        if row.maker_user_id == row.checker_user_id:
            raise ValueError("Review independence violated")
        approval = db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.company_id == company_id,
                ApprovalRequest.idempotency_key == "principal-x-review:" + row.review_reference,
            ).with_for_update(read=True).execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if (approval is None or approval.status != "approved"
                or approval.action_type != REVIEW_ACTION
                or approval.resource_type != REVIEW_ACTION
                or approval.resource_id != str(loan_id)
                or approval.branch_id is not None
                or approval.requested_by_user_id != row.maker_user_id
                or approval.decided_by_user_id != row.checker_user_id
                or approval.decided_at is None
                or not isinstance(approval.decision_reason, str)
                or len(approval.decision_reason.strip()) < 12):
            raise ValueError("Approved review decision missing or inconsistent")
        try:
            review = BoundLedgerReview(
                company_id=company_id, loan_id=loan_id,
                source_revision=source_revision,
                reviewed_at=row.reviewed_at, net_collected=row.net_collected,
                attestations=tuple(LedgerSourceAttestation(**item) for item in row.attestations),
            )
            digest = ledger_review_digest(
                review, maker_user_id=row.maker_user_id,
                review_reference=row.review_reference,
            )
            expected_payload = {
                "version": 1,
                "review_reference": row.review_reference,
                "checker_user_id": str(row.checker_user_id),
                "source_revision": source_revision,
                "reviewed_at": row.reviewed_at.astimezone(timezone.utc).isoformat(),
                "net_collected": format(row.net_collected, ".2f"),
                "attestations": [asdict(item) for item in sorted(
                    review.attestations, key=lambda item: item.source_family
                )],
                "evidence_digest": digest,
            }
            decided = approval.decided_at
            if decided.utcoffset() is None:
                decided = decided.replace(tzinfo=timezone.utc)
            if decided < row.reviewed_at:
                raise ValueError("Invalid approval chronology")
            if not compare_digest(row.evidence_digest, digest) or approval.payload != expected_payload:
                raise ValueError("Stored evidence and approval digest mismatch")
        except (TypeError, ValueError, ArithmeticError, AttributeError) as exc:
            raise ValueError("Stored review evidence integrity failure") from exc
        return review
