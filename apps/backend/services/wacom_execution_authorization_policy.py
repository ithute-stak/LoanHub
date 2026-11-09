"""Fail-closed authorization state checks before any future signing operation."""
from __future__ import annotations

import hmac
import re
from datetime import datetime, timezone

_HASH = re.compile(r"^[0-9a-f]{64}$")


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _same_hash(left, right):
    return (isinstance(left, str) and isinstance(right, str)
            and _HASH.fullmatch(left) is not None
            and _HASH.fullmatch(right) is not None
            and hmac.compare_digest(left, right))


def authorization_request_blockers(*, intent, approval, packet, requester_id, now=None):
    now = _utc(now or datetime.now(timezone.utc))
    if now is None or any(x is None for x in (intent, approval, packet)):
        return ["invalid_authorization_context"]
    reasons = []
    if len({intent.company_id, approval.company_id, packet.company_id}) != 1:
        reasons.append("company_mismatch")
    if intent.id != approval.intent_id or intent.id != packet.intent_id:
        reasons.append("intent_mismatch")
    if intent.contract_id != approval.contract_id or intent.contract_id != packet.contract_id:
        reasons.append("contract_mismatch")
    if packet.approval_id != approval.id:
        reasons.append("packet_approval_mismatch")
    if (intent.status != "verified" or not intent.review_by or not intent.review_at
            or not intent.consent_at or not intent.consent_reference):
        reasons.append("review_or_consent_missing")
    if _utc(intent.expires_at) is None or _utc(intent.expires_at) <= now:
        reasons.append("intent_expired")
    if approval.status != "consumed" or approval.consumed_at is None or not approval.decided_by:
        reasons.append("archival_approval_unavailable")
    if not packet.packet_file_id or _utc(packet.archived_at) is None:
        reasons.append("packet_unavailable")
    for attr in ("document_sha256", "evidence_sha256", "binding_sha256"):
        if not _same_hash(getattr(intent, attr, None), getattr(approval, attr, None)):
            reasons.append(attr + "_approval_changed")
    if not _same_hash(intent.document_sha256, packet.source_sha256):
        reasons.append("packet_source_changed")
    if not _same_hash(intent.evidence_sha256, packet.handwriting_sha256):
        reasons.append("packet_handwriting_changed")
    if requester_id is None or requester_id in {
        intent.operator_user_id, intent.review_by, approval.decided_by,
        approval.requested_by, packet.created_by_user_id,
    }:
        reasons.append("requester_not_independent")
    return reasons


def authorization_decision_blockers(*, intent, approval, packet, authorization, approver_id, now=None):
    now = _utc(now or datetime.now(timezone.utc))
    if now is None or authorization is None:
        return ["invalid_authorization_context"]
    reasons = authorization_request_blockers(
        intent=intent, approval=approval, packet=packet,
        requester_id=authorization.requested_by, now=now,
    )
    if authorization.company_id != intent.company_id or authorization.intent_id != intent.id:
        reasons.append("authorization_scope_mismatch")
    if authorization.contract_id != intent.contract_id or authorization.packet_id != packet.id:
        reasons.append("authorization_binding_mismatch")
    for attr in ("document_sha256", "evidence_sha256", "binding_sha256"):
        if not _same_hash(getattr(intent, attr, None), getattr(authorization, attr, None)):
            reasons.append(attr + "_authorization_changed")
    if (authorization.status != "pending" or authorization.authorized_by is not None
            or authorization.consumed_at is not None):
        reasons.append("authorization_already_closed")
    if (_utc(authorization.expires_at) is None or _utc(authorization.expires_at) <= now
            or _utc(authorization.requested_at) is None):
        reasons.append("authorization_expired")
    if (approver_id is None or approver_id == authorization.requested_by
            or approver_id in {
                intent.operator_user_id, intent.review_by, approval.requested_by,
                approval.decided_by, packet.created_by_user_id,
            }):
        reasons.append("approver_not_independent")
    return reasons
