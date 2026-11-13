"""Pure checks for exactly-once reviewed Wacom PDF archive operation.

No approval by itself authorizes loan-contract execution.
"""
from datetime import datetime, timezone


def _utc(value):
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def packet_blockers(*, approval, intent, executor_id, now=None):
    now = now or datetime.now(timezone.utc)
    reasons = []
    if (approval.company_id != intent.company_id or approval.intent_id != intent.id or
            approval.contract_id != intent.contract_id):
        reasons.append("approval_scope_changed")
    if (approval.status != "approved" or approval.decided_by is None or
            approval.consumed_at is not None or not approval.decision_reference):
        reasons.append("approval_unavailable")
    if _utc(approval.expires_at) is None or _utc(approval.expires_at) <= now:
        reasons.append("approval_expired")
    if intent.status != "verified":
        reasons.append("reviewed_evidence_unavailable")
    if (approval.document_sha256 != intent.document_sha256 or
            approval.evidence_sha256 != intent.evidence_sha256 or
            approval.binding_sha256 != intent.binding_sha256):
        reasons.append("approved_document_changed")
    if executor_id in {intent.operator_user_id, intent.review_by, 
                       approval.requested_by, approval.decided_by}:
        reasons.append("independent_archiver_required")
    return reasons
