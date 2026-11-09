"""Fail-closed Wacom execution-commit gate (no signing side effects).

This policy is a prerequisite for a future atomic DB transaction, not an
execution endpoint. The intended transaction must hold locks on approval,
intent, packet, authorization, receipt and contract, verify stored ciphertext,
and avoid treating object storage writes as PostgreSQL-transactional.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from services.wacom_execution_receipt_policy import reserve_execution_blockers
from services.wacom_approved_field import stored_field_matches


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _digest_matches(data, expected):
    if not isinstance(data, bytes) or not isinstance(expected, str) or len(expected) != 64:
        return False
    return hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected)


def execution_commit_blockers(
    *, intent, approval, packet, execution_authorization, receipt,
    contract, source, evidence, candidate_file, executing_user_id,
    source_pdf, handwriting_png, candidate_pdf, candidate_sha256, now=None,
):
    """Pure checks only. [] is NOT proof of legal contract execution."""
    now = now or datetime.now(timezone.utc)
    if (_utc(now) is None or any(
        row is None for row in (
            intent, approval, packet, execution_authorization, receipt,
            contract, source, evidence, candidate_file,
        )
    )):
        return ["missing_commit_context"]
    now = _utc(now)
    reasons = reserve_execution_blockers(
        intent=intent, approval=approval, packet=packet,
        execution_authorization=execution_authorization,
        contract=contract, source=source, evidence=evidence,
        executing_user_id=executing_user_id,
        source_pdf=source_pdf, handwriting_png=handwriting_png,
        existing_receipt=None, now=now,
    )
    if (receipt.company_id != intent.company_id
            or receipt.contract_id != intent.contract_id
            or receipt.intent_id != intent.id
            or receipt.authorization_id != execution_authorization.id
            or receipt.packet_id != packet.id):
        reasons.append("execution_receipt_scope_mismatch")
    if receipt.status != "reserved" or receipt.executed_file_id is not None or receipt.executed_at is not None:
        reasons.append("execution_receipt_not_reserved")
    if receipt.reserved_by != executing_user_id or _utc(receipt.reserved_at) is None:
        reasons.append("execution_reservation_owner_changed")
    if any(
        getattr(receipt, name, None) != getattr(intent, name, None)
        for name in ("document_sha256", "evidence_sha256", "binding_sha256")
    ):
        reasons.append("execution_receipt_hashes_changed")
    if (getattr(receipt, "field_binding_sha256", None)
            != getattr(execution_authorization, "field_binding_sha256", None)):
        reasons.append("execution_receipt_field_changed")
    if not stored_field_matches(
        authorization=execution_authorization,
        source_pdf=source_pdf, expected_sha256=intent.document_sha256,
    ):
        reasons.append("approved_field_changed")
    if (not isinstance(candidate_pdf, bytes)
            or not candidate_pdf.startswith(b"%PDF-")
            or not _digest_matches(candidate_pdf, candidate_sha256)):
        reasons.append("rendered_candidate_hash_mismatch")
    if (candidate_file.company_id != intent.company_id
            or candidate_file.id is None
            or candidate_file.is_deleted or not candidate_file.is_encrypted
            or not candidate_file.is_confidential
            or candidate_file.scan_status != "clean"
            or candidate_file.mime_type != "application/pdf"
            or candidate_file.category != "wacom_execution_candidate"
            or candidate_file.checksum_sha256 != candidate_sha256):
        reasons.append("candidate_storage_not_verified")
    if (candidate_file.id == intent.source_file_id
            or candidate_file.id == packet.packet_file_id):
        reasons.append("candidate_overwrites_original")
    if _utc(execution_authorization.authorized_at) is None:
        reasons.append("execution_authorizer_missing_timestamp")
    if (getattr(execution_authorization, "consumed_at", None) is not None
            or getattr(execution_authorization, "status", None) != "approved"):
        reasons.append("execution_authorization_already_consumed")
    return reasons
