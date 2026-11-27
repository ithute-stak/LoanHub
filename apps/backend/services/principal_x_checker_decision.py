"""Internal checker decision; no public endpoint or settlement posting."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hmac import compare_digest
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.governance_control import ApprovalRequest
from database.models.principal_x_ledger_review import PrincipalXLedgerReview
from payment_engine.principal_x_bound_reconciliation import BoundLedgerReview, validate_bound_ledger_review
from payment_engine.principal_x_ledger_source_attestation import LedgerSourceAttestation
from services.principal_x_financial_lock import lock_financial_loan
from services.principal_x_locked_source_revision import local_principal_x_source_revision
from services.principal_x_maker_submission import REVIEW_ACTION
from services.principal_x_reviewer_authorization import CHECKER_ROLES, require_independent_ledger_reviewers
from services.principal_x_review_digest import ledger_review_digest


def decide_ledger_review(
    db: Session, *, context: TenantContext, loan_id: UUID, approval_id: UUID,
    expected_digest: str, approved: bool, reason: str, max_age: timedelta,
) -> ApprovalRequest:
    """Revalidate the pending proposal and persist the decision atomically.

    Authentication must be established by the caller; the checker must have
    independently examined source evidence before approving. Neither a digest
    nor this decision proves external source authenticity. No commit here.
    """
    if (context.staff is None or context.branch_id is not None
            or context.company_id is None or context.role not in CHECKER_ROLES
            or context.staff.company_id != context.company_id
            or context.staff.user_id != context.user.id):
        raise ValueError("Authenticated company-wide checker required")
    if type(approved) is not bool or not isinstance(reason, str) or not 12 <= len(reason.strip()) <= 500:
        raise ValueError("Explicit decision and review reason required")
    if not isinstance(approval_id, UUID):
        raise ValueError("Verified approval identity required")
    if not isinstance(expected_digest, str) or len(expected_digest) != 64 or any(
        c not in "0123456789abcdef" for c in expected_digest
    ):
        raise ValueError("Expected evidence digest required")
    if db.new or db.dirty or db.deleted:
        raise ValueError("Clean financial session required")
    company_id, checker_id = context.company_id, context.user.id
    with db.no_autoflush:
        lock_financial_loan(db, company_id=company_id, loan_id=loan_id)
        db.expire_all()
        query = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.company_id == company_id,
            ApprovalRequest.resource_id == str(loan_id),
            ApprovalRequest.action_type == REVIEW_ACTION,
            ApprovalRequest.resource_type == REVIEW_ACTION,
        )
        proposal = db.execute(query).scalar_one_or_none()
        if proposal is None:
            raise ValueError("Scoped review proposal unavailable")
        maker_id = proposal.requested_by_user_id
        # Maintain the same loan -> reviewers -> approval lock order as maker submission.
        require_independent_ledger_reviewers(
            db, company_id=company_id, maker_user_id=maker_id,
            checker_user_id=checker_id,
        )
        proposal = db.execute(query.with_for_update().execution_options(
            populate_existing=True
        )).scalar_one_or_none()
        if (proposal is None or proposal.status != "pending"
                or proposal.branch_id is not None
                or proposal.requested_by_user_id != maker_id):
            raise ValueError("Review proposal is no longer pending or has changed")
        payload = proposal.payload
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("Unsupported review proposal")
        if payload.get("checker_user_id") != str(checker_id):
            raise ValueError("Only the designated independent checker may decide")
        try:
            reference = payload["review_reference"]
            review = BoundLedgerReview(
                company_id=company_id, loan_id=loan_id,
                source_revision=payload["source_revision"],
                reviewed_at=datetime.fromisoformat(payload["reviewed_at"]),
                net_collected=Decimal(payload["net_collected"]),
                attestations=tuple(LedgerSourceAttestation(**row) for row in payload["attestations"]),
            )
            actual_digest = ledger_review_digest(
                review, maker_user_id=maker_id, review_reference=reference,
            )
        except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError) as exc:
            raise ValueError("Invalid stored financial evidence") from exc
        if (proposal.idempotency_key != "principal-x-review:" + reference
                or payload.get("evidence_digest") != actual_digest
                or not compare_digest(expected_digest, actual_digest)):
            raise ValueError("Financial review digest mismatch")
        now = datetime.now(timezone.utc)
        if approved:
            revision = local_principal_x_source_revision(
                db, company_id=company_id, loan_id=loan_id,
            )
            completeness = validate_bound_ledger_review(
                review, company_id=company_id, loan_id=loan_id,
                current_revision=revision, now=now, max_age=max_age,
            )
            db.add(PrincipalXLedgerReview(
                company_id=company_id, loan_id=loan_id,
                maker_user_id=maker_id, checker_user_id=checker_id,
                review_reference=reference, source_revision=revision,
                evidence_digest=actual_digest, net_collected=completeness.net_collected,
                reviewed_at=review.reviewed_at, attestations=payload["attestations"],
            ))
        proposal.status = "approved" if approved else "rejected"
        proposal.decided_by_user_id = checker_id
        proposal.decision_reason = reason.strip()
        # ApprovalRequest stores a naive UTC timestamp.
        proposal.decided_at = now.replace(tzinfo=None)
        db.add(proposal)
        db.flush()
        return proposal
