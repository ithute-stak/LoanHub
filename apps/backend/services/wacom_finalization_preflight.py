"""Fail-closed, side-effect-free eligibility for a FUTURE PDF finalization.

Passing this check must never itself authorize signing, release signing keys,
issue a signature reuse grant, or modify a contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.wacom_document_policy import IntentIdentity


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def finalization_blockers(*, intent: Any, contract: Any, source: Any,
                          evidence: Any, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    if intent.status != "verified" or not intent.review_by or not intent.review_at:
        reasons.append("independent_evidence_review_missing")
    if intent.review_by == intent.operator_user_id:
        reasons.append("capturing_operator_cannot_review")
    if not intent.review_reference or not intent.review_reason:
        reasons.append("review_audit_incomplete")
    if not intent.consent_reference or not intent.consent_commitment_sha256 or not intent.consent_at:
        reasons.append("explicit_document_consent_missing")
    if _aware(intent.consent_at) is not None and _aware(intent.review_at) is not None and _aware(intent.review_at) < _aware(intent.consent_at):
        reasons.append("review_precedes_consent")
    if _aware(intent.expires_at) is None or _aware(intent.consent_at) is None or _aware(intent.consent_at) >= _aware(intent.expires_at):
        reasons.append("consent_outside_prepared_window")
    if contract is None:
        return reasons + ["contract_missing"]
    if (contract.id != intent.contract_id or contract.company_id != intent.company_id or
        contract.borrower_id != intent.borrower_id or contract.pdf_file_id != intent.source_file_id):
        reasons.append("contract_identity_changed")
    if (str(contract.version) != intent.document_version or
        contract.borrower_signed_at is not None or contract.locked_at is not None or
        contract.status == "signed"):
        reasons.append("contract_version_or_status_changed")
    if source is None or (source.id != intent.source_file_id or
        source.company_id != intent.company_id or source.checksum_sha256 != intent.document_sha256 or
        source.mime_type != "application/pdf" or not source.is_encrypted or
        source.is_deleted or source.scan_status != "clean"):
        reasons.append("source_pdf_unavailable_or_changed")
    if evidence is None or (evidence.id != intent.evidence_file_id or
        evidence.company_id != intent.company_id or
        evidence.checksum_sha256 != intent.evidence_sha256 or
        evidence.linked_entity_type != "wacom_client" or
        evidence.linked_entity_id != str(intent.borrower_id) or
        evidence.category != "wacom_client_capture_verified" or
        not evidence.is_encrypted or not evidence.is_confidential or
        evidence.is_deleted or evidence.scan_status != "clean"):
        reasons.append("reviewed_evidence_unavailable_or_changed")
    try:
        digest = IntentIdentity(
            company_id=intent.company_id, borrower_id=intent.borrower_id,
            contract_id=intent.contract_id, source_file_id=intent.source_file_id,
            operator_user_id=intent.operator_user_id, workstation_id=intent.workstation_id,
            document_sha256=intent.document_sha256,
            document_version=intent.document_version,
        ).binding_sha256()
        if digest != intent.binding_sha256:
            reasons.append("document_binding_invalid")
    except (ValueError, TypeError, AttributeError):
        reasons.append("document_binding_invalid")
    return reasons
