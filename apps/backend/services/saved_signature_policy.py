"""Fail-closed reusable-signature authorization rules.

The library validates data for a future authenticated, transaction-locked API.
It does not create signature artifacts or sign any contract.
"""
from datetime import datetime, timezone
import re

from fastapi import HTTPException

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def authorize_saved_signature_use(
    *,
    signature_company_id,
    signature_borrower_id,
    signature_status: str,
    signature_opt_in_at: datetime | None,
    contract_company_id,
    contract_borrower_id,
    contract_hash: str,
    session_contract_hash: str,
    session_status: str,
    session_expires_at: datetime,
    identity_verified_at: datetime | None,
    explicit_consent_at: datetime | None,
    now: datetime | None = None,
) -> None:
    """Require new signer authorization for every exact immutable contract."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or session_expires_at.tzinfo is None:
        raise HTTPException(409, "Timezone-aware session required")
    if signature_company_id != contract_company_id or signature_borrower_id != contract_borrower_id:
        raise HTTPException(403, "Signature profile does not belong to this borrower and company")
    if signature_status != "active" or signature_opt_in_at is None:
        raise HTTPException(409, "Signature reuse is not enabled")
    if not _SHA256.fullmatch(contract_hash) or contract_hash != session_contract_hash:
        raise HTTPException(409, "Signing session is bound to a different contract revision")
    if session_status != "consented" or now >= session_expires_at:
        raise HTTPException(409, "Active consented signing session required")
    if identity_verified_at is None or explicit_consent_at is None:
        raise HTTPException(409, "Verified borrower identity and new contract consent required")
    if any(t.tzinfo is None or t > now for t in (identity_verified_at, explicit_consent_at, signature_opt_in_at)):
        raise HTTPException(409, "Invalid verification or consent timestamp")
    if identity_verified_at > explicit_consent_at:
        raise HTTPException(409, "Consent must follow identity verification")


def may_reuse_saved_signature(*, opted_in: bool, specific_contract_approved: bool) -> bool:
    """Saved profile availability alone never permits applying it to a contract."""
    return opted_in and specific_contract_approved
