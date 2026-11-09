"""Fail-closed prerequisites for a FUTURE Wacom contract-execution transaction.

This module does not sign PDFs, consume authorizations, or mutate contracts.
The caller must separately verify authenticated roles, authorize an exact field,
lock database rows, enforce uniqueness, and commit the signed file atomically.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timezone

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _utc(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _hash_equal(actual, expected):
    return (isinstance(actual, str) and isinstance(expected, str)
            and _SHA256.fullmatch(actual) is not None
            and _SHA256.fullmatch(expected) is not None
            and hmac.compare_digest(actual, expected))


def execution_preflight_blockers(
    *, intent, approval, packet, execution_authorization,
    executing_user_id, source_pdf, handwriting_png, now=None,
):
    """Return denial codes; empty list means *eligible for further validation*.

    A consumed archival approval is not itself an execution authorization.
    execution_authorization represents a separately authorized one-time permit,
    not yet implemented in the persistent database.
    """
    now = now or datetime.now(timezone.utc)
    reasons = []
    if _utc(now) is None:
        return ["invalid_clock"]
    now = _utc(now)

    if any(obj is None for obj in (intent, approval, packet, execution_authorization)):
        return ["missing_execution_records"]
    if executing_user_id is None:
        reasons.append("missing_executor")

    ids = (intent.company_id, approval.company_id, packet.company_id,
           execution_authorization.company_id)
    if any(value is None for value in ids) or len(set(ids)) != 1:
        reasons.append("company_mismatch")
    if (intent.id is None or approval.intent_id != intent.id
            or packet.intent_id != intent.id
            or execution_authorization.intent_id != intent.id):
        reasons.append("intent_mismatch")
    if (intent.contract_id is None or approval.contract_id != intent.contract_id
            or packet.contract_id != intent.contract_id
            or execution_authorization.contract_id != intent.contract_id):
        reasons.append("contract_mismatch")
    if packet.approval_id != approval.id:
        reasons.append("archived_approval_mismatch")

    if intent.status != "verified" or not intent.review_by or not intent.review_at:
        reasons.append("review_not_verified")
    if (not intent.consent_at or not intent.consent_reference
            or not intent.consent_commitment_sha256):
        reasons.append("consent_missing")
    if _utc(intent.expires_at) is None or _utc(intent.expires_at) <= now:
        reasons.append("intent_expired")
    if (approval.status != "consumed" or approval.consumed_at is None
            or not approval.decided_by or not approval.decision_reference):
        reasons.append("archival_approval_not_consumed")
    if (_utc(approval.decided_at) is None or _utc(approval.expires_at) is None
            or _utc(approval.decided_at) >= _utc(approval.expires_at)):
        reasons.append("archival_approval_invalid")
    if packet.archived_at is None or not packet.packet_file_id:
        reasons.append("packet_not_archived")

    if (execution_authorization.status != "approved"
            or execution_authorization.consumed_at is not None
            or not execution_authorization.authorized_by):
        reasons.append("execution_permit_unavailable")
    if (_utc(execution_authorization.expires_at) is None
            or _utc(execution_authorization.expires_at) <= now):
        reasons.append("execution_permit_expired")

    restricted = {
        intent.operator_user_id, intent.review_by, approval.requested_by,
        approval.decided_by, packet.created_by_user_id,
    }
    if (executing_user_id in restricted
            or execution_authorization.authorized_by in restricted
            or executing_user_id == execution_authorization.authorized_by):
        reasons.append("separation_of_duties_violation")

    for name in ("document_sha256", "evidence_sha256", "binding_sha256"):
        expected = getattr(intent, name, None)
        if not _hash_equal(expected, getattr(approval, name, None)):
            reasons.append(name + "_approval_mismatch")
        if not _hash_equal(expected, getattr(execution_authorization, name, None)):
            reasons.append(name + "_execution_mismatch")
    if not _hash_equal(intent.document_sha256, packet.source_sha256):
        reasons.append("archived_source_mismatch")
    if not _hash_equal(intent.evidence_sha256, packet.handwriting_sha256):
        reasons.append("archived_handwriting_mismatch")
    if (not isinstance(source_pdf, bytes)
            or not _hash_equal(hashlib.sha256(source_pdf).hexdigest(),
                               intent.document_sha256)):
        reasons.append("source_bytes_mismatch")
    if (not isinstance(handwriting_png, bytes)
            or not _hash_equal(hashlib.sha256(handwriting_png).hexdigest(),
                               intent.evidence_sha256)):
        reasons.append("handwriting_bytes_mismatch")
    return reasons
