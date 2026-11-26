"""Internal maker submission; no public endpoint or posting authorization."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.governance_control import ApprovalRequest
from payment_engine.principal_x_bound_reconciliation import BoundLedgerReview, validate_bound_ledger_review
from services.principal_x_financial_lock import lock_financial_loan
from services.principal_x_locked_source_revision import local_principal_x_source_revision
from services.principal_x_reviewer_authorization import require_independent_ledger_reviewers, MAKER_ROLES
from services.principal_x_review_digest import ledger_review_digest

REVIEW_ACTION = "principal_x_ledger_review"


def submit_ledger_review(
    db: Session, *, context: TenantContext, loan_id: UUID,
    checker_user_id: UUID, review_reference: str,
    trusted_review: BoundLedgerReview, max_age: timedelta,
) -> ApprovalRequest:
    """Persist a pending proposal, not a completed financial review.

    The calling service must obtain context from authentication and the
    review from independently verified server-side evidence. Never map
    client-provided attestations directly into trusted_review.
    The caller owns commit/rollback. No provider calls occur here.
    """
    if (context.staff is None or context.branch_id is not None
            or context.company_id is None or context.role not in MAKER_ROLES
            or context.staff.company_id != context.company_id
            or context.staff.user_id != context.user.id):
        raise ValueError("Authenticated company-wide maker required")
    company_id, maker_user_id = context.company_id, context.user.id
    if not isinstance(trusted_review, BoundLedgerReview):
        raise ValueError("Trusted financial review required")
    if not isinstance(review_reference, str) or not review_reference.strip() or len(review_reference) > 140:
        raise ValueError("Invalid review reference")
    if db.new or db.dirty or db.deleted:
        raise ValueError("Clean financial session required")
    with db.no_autoflush:
        lock_financial_loan(db, company_id=company_id, loan_id=loan_id)
        require_independent_ledger_reviewers(
            db, company_id=company_id, maker_user_id=maker_user_id,
            checker_user_id=checker_user_id,
        )
        db.expire_all()
        revision = local_principal_x_source_revision(
            db, company_id=company_id, loan_id=loan_id,
        )
        now = datetime.now(timezone.utc)
        completeness = validate_bound_ledger_review(
            trusted_review, company_id=company_id, loan_id=loan_id,
            current_revision=revision, now=now, max_age=max_age,
        )
        digest = ledger_review_digest(
            trusted_review, maker_user_id=maker_user_id,
            review_reference=review_reference,
        )
        payload = {
            "version": 1,
            "review_reference": review_reference,
            "checker_user_id": str(checker_user_id),
            "source_revision": revision,
            "reviewed_at": trusted_review.reviewed_at.astimezone(timezone.utc).isoformat(),
            "net_collected": format(completeness.net_collected, ".2f"),
            "attestations": [asdict(item) for item in sorted(
                trusted_review.attestations, key=lambda item: item.source_family
            )],
            "evidence_digest": digest,
        }
        key = "principal-x-review:" + review_reference
        existing = db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.company_id == company_id,
                ApprovalRequest.idempotency_key == key,
            ).with_for_update().execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if existing is not None:
            if (existing.action_type != REVIEW_ACTION
                    or existing.resource_type != REVIEW_ACTION
                    or existing.resource_id != str(loan_id)
                    or existing.requested_by_user_id != maker_user_id
                    or existing.branch_id is not None
                    or existing.payload != payload):
                raise ValueError("Review reference already bound to different evidence")
            return existing
        proposal = ApprovalRequest(
            company_id=company_id, branch_id=None, action_type=REVIEW_ACTION,
            resource_type=REVIEW_ACTION, resource_id=str(loan_id),
            payload=payload, status="pending", idempotency_key=key,
            requested_by_user_id=maker_user_id,
        )
        db.add(proposal)
        db.flush()
        return proposal
