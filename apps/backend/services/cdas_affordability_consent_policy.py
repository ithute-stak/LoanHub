"""Fail-closed CDAS affordability consent evidence policy.

This policy does NOT infer CDAS consent from a generic verified borrower file.
An independent, purpose-specific reviewer must approve evidence for the exact
company, borrower, employee number and CDAS affordability use before a future
live-operation gate can accept it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from uuid import UUID

PURPOSE = "cdas_government_employee_affordability"


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def consent_evidence_blockers(
    *,
    evidence,
    company_id: UUID,
    borrower_id: UUID,
    employee_number: str,
    reference: str,
    operator_user_id: UUID,
    now: datetime | None = None,
) -> list[str]:
    """Return stable reason codes. An empty list is a necessary, not sufficient,
    prerequisite for contacting CDAS. This helper does not perform I/O.
    """
    current = _utc(now or datetime.now(timezone.utc))
    if current is None or evidence is None:
        return ["consent_evidence_unavailable"]

    reasons = []
    if getattr(evidence, "company_id", None) != company_id:
        reasons.append("company_mismatch")
    if getattr(evidence, "borrower_id", None) != borrower_id:
        reasons.append("borrower_mismatch")
    if str(getattr(evidence, "employee_number", "")).strip().casefold() != employee_number.strip().casefold():
        reasons.append("employee_number_mismatch")
    if getattr(evidence, "reference", None) != reference.strip():
        reasons.append("consent_reference_mismatch")
    if getattr(evidence, "purpose", None) != PURPOSE:
        reasons.append("wrong_consent_purpose")
    if getattr(evidence, "status", None) != "approved":
        reasons.append("consent_not_approved")
    if not getattr(evidence, "document_id", None):
        reasons.append("consent_document_missing")
    if re.fullmatch(r"[a-fA-F0-9]{64}", str(getattr(evidence, "document_sha256", ""))) is None:
        reasons.append("document_integrity_unavailable")
    verified_at = _utc(getattr(evidence, "verified_at", None))
    expires_at = _utc(getattr(evidence, "expires_at", None))
    if verified_at is None or verified_at > current:
        reasons.append("consent_verification_unavailable")
    if expires_at is None or expires_at <= current:
        reasons.append("consent_expired")
    reviewer = getattr(evidence, "verified_by_user_id", None)
    if reviewer is None or reviewer == operator_user_id:
        reasons.append("reviewer_not_independent")
    if not getattr(evidence, "borrower_authorization_confirmed", False):
        reasons.append("borrower_authorization_missing")
    return reasons
