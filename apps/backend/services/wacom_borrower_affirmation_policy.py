"""Fail-closed authenticated borrower affirmation of an exact PDF candidate.

Explicitly accepting an on-screen candidate does NOT prove physical STU-540
handwriting, verified identity beyond account authentication, or legal signing.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from services.wacom_execution_preflight import _hash_equal, _utc


def borrower_affirmation_blockers(
    *, challenge, borrower, authorization, receipt, candidate_file,
    user_id, candidate_pdf: bytes, displayed_candidate_sha256: str,
    displayed_field_sha256: str, now: datetime | None = None,
) -> list[str]:
    now = _utc(now or datetime.now(timezone.utc))
    if now is None:
        return ["invalid_clock"]
    if any(obj is None for obj in (
        challenge, borrower, authorization, receipt, candidate_file,
    )):
        return ["borrower_affirmation_context_missing"]
    reasons = []
    if borrower.user_id != user_id or challenge.borrower_id != borrower.id:
        reasons.append("authenticated_borrower_mismatch")
    if any(getattr(item, "company_id", None) != challenge.company_id for item in (
        authorization, receipt, candidate_file,
    )):
        reasons.append("borrower_affirmation_company_mismatch")
    if (
        authorization.id != challenge.authorization_id
        or receipt.id != challenge.receipt_id
        or receipt.contract_id != challenge.contract_id
        or receipt.intent_id != challenge.intent_id
        or receipt.authorization_id != authorization.id
        or receipt.executed_file_id != candidate_file.id
    ):
        reasons.append("borrower_affirmation_reference_changed")
    if (
        challenge.status != "pending" or challenge.verified_at is not None
        or challenge.consumed_at is not None
        or getattr(challenge, "borrower_affirmed_at", None) is not None
        or getattr(challenge, "borrower_affirmed_user_id", None) is not None
        or getattr(challenge, "borrower_affirmation_sha256", None) is not None
        or _utc(challenge.expires_at) is None
        or now >= _utc(challenge.expires_at)
        or _utc(challenge.requested_at) is None
        or now < _utc(challenge.requested_at)
        or authorization.status != "approved"
        or authorization.consumed_at is not None
        or receipt.status != "reserved" or receipt.executed_at is not None
    ):
        reasons.append("borrower_affirmation_challenge_unavailable")
    if (
        getattr(challenge, "workstation_proof_at", None) is None
        or getattr(challenge, "workstation_proof_sha256", None) is None
        or getattr(challenge, "workstation_proof_by", None) is None
    ):
        reasons.append("workstation_key_proof_missing")
    if not (
        _hash_equal(displayed_candidate_sha256, challenge.candidate_sha256)
        and _hash_equal(receipt.executed_pdf_sha256, challenge.candidate_sha256)
        and _hash_equal(candidate_file.checksum_sha256, challenge.candidate_sha256)
        and _hash_equal(displayed_field_sha256, challenge.field_binding_sha256)
        and _hash_equal(authorization.field_binding_sha256, challenge.field_binding_sha256)
    ):
        reasons.append("borrower_affirmation_document_mismatch")
    if (
        candidate_file.is_deleted or not candidate_file.is_encrypted
        or not candidate_file.is_confidential or candidate_file.scan_status != "clean"
        or candidate_file.category != "wacom_execution_candidate"
        or candidate_file.mime_type != "application/pdf"
        or not isinstance(candidate_pdf, bytes)
        or not 5 <= len(candidate_pdf) <= 25 * 1024 * 1024
        or not candidate_pdf.startswith(b"%PDF-")
        or not _hash_equal(
            hashlib.sha256(candidate_pdf).hexdigest(), challenge.candidate_sha256,
        )
    ):
        reasons.append("borrower_affirmation_candidate_invalid")
    return reasons


def affirmation_digest(*, challenge_id, user_id, candidate_sha256, field_sha256, now):
    """Minimal hash commitment; deliberately stores no borrower-entered signature."""
    timestamp = _utc(now)
    if timestamp is None or not _hash_equal(candidate_sha256, candidate_sha256) or not _hash_equal(field_sha256, field_sha256):
        raise ValueError("Invalid borrower affirmation commitment")
    message = (
        f"LOANHUB-WACOM-BORROWER-AFFIRMATION-V1\n{challenge_id}\n{user_id}\n"
        f"{candidate_sha256}\n{field_sha256}\n{timestamp.isoformat()}\n"
    ).encode("ascii")
    return hashlib.sha256(message).hexdigest()
