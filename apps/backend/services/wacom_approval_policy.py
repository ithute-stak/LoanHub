"""Pure, fail-closed separation-of-duties policy for Wacom approval."""
from __future__ import annotations
from datetime import datetime, timezone


def _aware(value):
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def approval_blockers(*, intent, approval, approver_id, now=None):
    now = now or datetime.now(timezone.utc)
    reasons = []
    if approval.company_id != intent.company_id or approval.intent_id != intent.id or approval.contract_id != intent.contract_id:
        reasons.append("approval_scope_changed")
    if (approval.document_sha256 != intent.document_sha256 or
            approval.evidence_sha256 != intent.evidence_sha256 or
            approval.binding_sha256 != intent.binding_sha256):
        reasons.append("approval_document_or_evidence_changed")
    if intent.status != "verified":
        reasons.append("evidence_not_verified")
    if approval.status != "pending" or approval.decided_by is not None or approval.consumed_at is not None:
        reasons.append("approval_already_closed")
    expiry = _aware(approval.expires_at)
    if expiry is None or expiry <= now:
        reasons.append("approval_expired")
    if approver_id in {approval.requested_by, intent.operator_user_id, intent.review_by}:
        reasons.append("independent_approver_required")
    return reasons
