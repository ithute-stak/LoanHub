"""Read-only session revalidation against the current loan contract.

Used by the existing authenticated pad-session status API. This is a UI
eligibility signal, NOT a workstation credential or authorization to stream.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def current_pad_preview_eligibility(session: Any, contract: Any, now: datetime) -> dict[str, object]:
    """Fail closed if current contract no longer matches the prepared session."""
    reasons: list[str] = []
    if now.tzinfo is None or now.utcoffset() is None:
        reasons.append("clock_unavailable")
    expiry = getattr(session, "expires_at", None)
    if not isinstance(expiry, datetime) or expiry.tzinfo is None or expiry.utcoffset() is None:
        reasons.append("session_expiry_unavailable")
    elif now.astimezone(timezone.utc) >= expiry.astimezone(timezone.utc):
        reasons.append("session_expired")
    if getattr(session, "status", None) not in ("created", "consented"):
        reasons.append("session_closed")
    if getattr(session, "contract_id", None) != getattr(contract, "id", None):
        reasons.append("contract_mismatch")
    if getattr(session, "company_id", None) != getattr(contract, "company_id", None):
        reasons.append("company_mismatch")
    current_hash = getattr(contract, "contract_hash", None)
    if (not isinstance(current_hash, str) or len(current_hash) != 64 or
            any(c not in "0123456789abcdef" for c in current_hash) or
            getattr(session, "contract_hash", None) != current_hash):
        reasons.append("contract_changed")
    if getattr(contract, "borrower_signed_at", None) is not None:
        reasons.append("borrower_already_signed")
    if (getattr(contract, "locked_at", None) is not None or
            getattr(contract, "status", None) == "signed"):
        reasons.append("contract_locked")
    if getattr(contract, "pdf_file_id", None) is None:
        reasons.append("contract_pdf_missing")
    if getattr(session, "evidence_sha256", None) is not None:
        reasons.append("evidence_already_captured")
    return {"preview_eligible": not reasons, "preview_blockers": reasons}
