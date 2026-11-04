"""Fail-closed admission checks for future *temporary* Wacom previews.

Pure validation only. This module neither issues tokens nor exposes an API.
Caller must first authenticate the operator and independently retrieve the
tenant-scoped persisted session and current contract under authorization.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_PREVIEW_STATES = frozenset({"created", "consented"})


def authorize_wacom_preview_admission(
    *,
    session: object,
    authenticated_company_id: UUID,
    authenticated_operator_id: UUID,
    current_contract_id: UUID,
    current_contract_hash: str,
    expected_session_id: UUID,
    now: datetime,
) -> None:
    """Check an existing session; never mint authority from browser fields.

    The active contract's hash and tenant must come from the database, not
    a browser-provided fingerprint. This checks *only* preview eligibility,
    NOT borrower identity, consent, stored evidence, or legal finalization.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise HTTPException(422, "Timezone-aware clock required")
    if not isinstance(current_contract_hash, str) or not _HASH_RE.fullmatch(current_contract_hash):
        raise HTTPException(409, "Current contract hash unavailable")
    if session is None:
        raise HTTPException(404, "Pad session unavailable")

    for name, value in (
        ("id", expected_session_id),
        ("company_id", authenticated_company_id),
        ("operator_user_id", authenticated_operator_id),
        ("contract_id", current_contract_id),
    ):
        if getattr(session, name, None) != value:
            raise HTTPException(403, "Pad preview session context mismatch")

    if getattr(session, "contract_hash", None) != current_contract_hash:
        raise HTTPException(409, "Contract changed; preview session invalid")

    expires = getattr(session, "expires_at", None)
    if not isinstance(expires, datetime) or expires.tzinfo is None or expires.utcoffset() is None:
        raise HTTPException(409, "Session expiry unavailable")
    if now.astimezone(timezone.utc) >= expires.astimezone(timezone.utc):
        raise HTTPException(409, "Pad preview session expired")

    if getattr(session, "status", None) not in _ALLOWED_PREVIEW_STATES:
        raise HTTPException(409, "Pad session cannot preview")

    # A preview must never revive a finalized evidence record or a captured
    # session, even if the status field was incorrectly left active.
    if getattr(session, "evidence_sha256", None) is not None:
        raise HTTPException(409, "Pad evidence already captured")
