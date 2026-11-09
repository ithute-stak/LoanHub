"""Fail-closed fresh Wacom execution ceremony eligibility.

An archived handwriting-PDF candidate is NOT a signed contract. This
policy checks a proposed *new* borrower affirmation, device evidence and
independent legal release. It does not verify hardware cryptography itself,
certify legal sufficiency, sign documents or change any loan state.

Callers must independently validate the attestation's signature and physical
workstation identity, and commit all legal execution changes atomically.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

SHA256_LENGTH = 64
MAX_CEREMONY_AGE = timedelta(minutes=2)


def aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def hash_match(left, right):
    return (
        isinstance(left, str) and isinstance(right, str)
        and len(left) == SHA256_LENGTH and len(right) == SHA256_LENGTH
        and all(c in "0123456789abcdef" for c in left)
        and all(c in "0123456789abcdef" for c in right)
        and hmac.compare_digest(left, right)
    )


def execution_ceremony_blockers(
    *, intent, authorization, receipt, contract, candidate_file,
    fresh_consent, device_proof, legal_release, executor_id,
    candidate_pdf: bytes, now: datetime | None = None,
) -> list[str]:
    """Return denial codes only. Empty means eligible for *further* scrutiny."""
    now = aware(now or datetime.now(timezone.utc))
    if now is None:
        return ["invalid_execution_clock"]
    if any(obj is None for obj in (
        intent, authorization, receipt, contract, candidate_file,
        fresh_consent, device_proof, legal_release,
    )):
        return ["execution_ceremony_context_missing"]

    issues = []
    expected_company = intent.company_id
    if any(
        getattr(obj, "company_id", None) != expected_company
        for obj in (
            authorization, receipt, contract, candidate_file,
            fresh_consent, device_proof, legal_release,
        )
    ):
        issues.append("cross_tenant_execution_context")
    if (
        getattr(contract, "id", None) != intent.contract_id
        or getattr(receipt, "intent_id", None) != intent.id
        or getattr(receipt, "authorization_id", None) != authorization.id
        or getattr(receipt, "contract_id", None) != intent.contract_id
        or getattr(receipt, "executed_file_id", None) != candidate_file.id
        or getattr(authorization, "intent_id", None) != intent.id
        or getattr(authorization, "contract_id", None) != intent.contract_id
    ):
        issues.append("execution_reference_chain_invalid")
    if (
        getattr(receipt, "status", None) != "reserved"
        or getattr(receipt, "executed_at", None) is not None
        or getattr(authorization, "status", None) != "approved"
        or getattr(authorization, "consumed_at", None) is not None
    ):
        issues.append("execution_already_closed")
    if (
        getattr(contract, "status", None) == "signed"
        or getattr(contract, "borrower_signed_at", None) is not None
        or getattr(contract, "locked_at", None) is not None
        or getattr(contract, "pdf_file_id", None) != intent.source_file_id
        or getattr(contract, "borrower_id", None) != intent.borrower_id
        or str(getattr(contract, "version", "")) != intent.document_version
    ):
        issues.append("contract_changed_or_already_executed")

    if (
        getattr(candidate_file, "category", None) != "wacom_execution_candidate"
        or not getattr(candidate_file, "is_encrypted", False)
        or not getattr(candidate_file, "is_confidential", False)
        or getattr(candidate_file, "is_deleted", True)
        or getattr(candidate_file, "scan_status", None) != "clean"
        or getattr(candidate_file, "mime_type", None) != "application/pdf"
        or not isinstance(candidate_pdf, bytes)
        or not candidate_pdf.startswith(b"%PDF-")
        or not hash_match(
            hashlib.sha256(candidate_pdf).hexdigest(),
            getattr(receipt, "executed_pdf_sha256", None),
        )
        or not hash_match(
            getattr(candidate_file, "checksum_sha256", None),
            getattr(receipt, "executed_pdf_sha256", None),
        )
    ):
        issues.append("execution_candidate_not_verified")
    if (
        not hash_match(
            getattr(receipt, "field_binding_sha256", None),
            getattr(authorization, "field_binding_sha256", None),
        )
        or not hash_match(
            getattr(receipt, "document_sha256", None),
            intent.document_sha256,
        )
        or not hash_match(
            getattr(receipt, "evidence_sha256", None),
            intent.evidence_sha256,
        )
        or not hash_match(
            getattr(receipt, "binding_sha256", None),
            intent.binding_sha256,
        )
    ):
        issues.append("execution_binding_mismatch")

    consent_time = aware(getattr(fresh_consent, "affirmed_at", None))
    if (
        getattr(fresh_consent, "borrower_id", None) != intent.borrower_id
        or getattr(fresh_consent, "contract_id", None) != intent.contract_id
        or not hash_match(
            getattr(fresh_consent, "candidate_sha256", None),
            getattr(receipt, "executed_pdf_sha256", None),
        )
        or not hash_match(
            getattr(fresh_consent, "field_binding_sha256", None),
            getattr(authorization, "field_binding_sha256", None),
        )
        or getattr(fresh_consent, "affirmative_choice", None) is not True
        or not getattr(fresh_consent, "consent_reference", None)
        or consent_time is None or not timedelta(0) <= now - consent_time <= MAX_CEREMONY_AGE
    ):
        issues.append("fresh_borrower_affirmation_missing")

    proof_time = aware(getattr(device_proof, "verified_at", None))
    if (
        getattr(device_proof, "workstation_id", None) != intent.workstation_id
        or getattr(device_proof, "borrower_id", None) != intent.borrower_id
        or getattr(device_proof, "contract_id", None) != intent.contract_id
        or not hash_match(
            getattr(device_proof, "candidate_sha256", None),
            getattr(receipt, "executed_pdf_sha256", None),
        )
        or getattr(device_proof, "signature_verified", None) is not True
        or not getattr(device_proof, "hardware_evidence_reference", None)
        or proof_time is None or not timedelta(0) <= now - proof_time <= MAX_CEREMONY_AGE
        or consent_time is None or proof_time < consent_time
    ):
        issues.append("fresh_physical_device_proof_missing")

    release_time = aware(getattr(legal_release, "released_at", None))
    if (
        getattr(legal_release, "status", None) != "approved"
        or not hash_match(
            getattr(legal_release, "candidate_sha256", None),
            getattr(receipt, "executed_pdf_sha256", None),
        )
        or not getattr(legal_release, "legal_basis_reference", None)
        or not getattr(legal_release, "reviewer_user_id", None)
        or release_time is None or release_time > now
        or consent_time is None or release_time < consent_time
    ):
        issues.append("independent_legal_release_missing")

    restricted = {
        intent.operator_user_id, intent.review_by,
        authorization.requested_by, authorization.authorized_by,
        getattr(receipt, "reserved_by", None),
        getattr(legal_release, "reviewer_user_id", None),
    }
    if executor_id is None or executor_id in restricted:
        issues.append("execution_operator_not_independent")
    if (
        getattr(legal_release, "reviewer_user_id", None) is None
        or legal_release.reviewer_user_id in {
            intent.operator_user_id, authorization.requested_by,
            authorization.authorized_by, getattr(receipt, "reserved_by", None),
        }
    ):
        issues.append("legal_reviewer_not_independent")
    return issues
