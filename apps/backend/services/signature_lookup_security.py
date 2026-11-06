"""Database-coordinated controls for exact National ID lookup on staging.

Never persist National ID input, raw request bodies, bearer tokens or
person names in audit logs. Each attempt counts, including unsuccessful ones.

PostgreSQL transaction advisory lock serializes lookups per tenant/operator
across backend workers, so the cap cannot be bypassed with concurrent calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog

ACTION = "signature_bridge.national_id_lookup"
WINDOW_SECONDS = 60
MAX_ATTEMPTS = 8


def reserve_lookup_attempt(db: Session, *, company_id, operator_id) -> None:
    """Persist budget event before lookup; fail closed if ledger unavailable.

    Caller must be an already authenticated tenant staff member.
    The lock is held through the audit commit and scopes only that actor.
    """
    identity = f"signature-lookup:{company_id}:{operator_id}"
    # Stable signed 64-bit key avoids Python's process-randomized hash().
    key = int.from_bytes(sha256(identity.encode("ascii")).digest()[:8], "big", signed=True)
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=WINDOW_SECONDS)
        used = db.query(func.count(AuditLog.id)).filter(
            AuditLog.company_id == company_id,
            AuditLog.user_id == operator_id,
            AuditLog.action == ACTION,
            AuditLog.created_at >= cutoff,
        ).scalar()
        if not isinstance(used, int):
            raise ValueError("Audit query returned an invalid count")
        if used >= MAX_ATTEMPTS:
            db.rollback()
            raise HTTPException(429, "National ID lookup limit reached; retry later")
        db.add(AuditLog(
            company_id=company_id, user_id=operator_id,
            action=ACTION, table_name="people", entity_type="privacy_access",
            description="Authenticated exact client identity lookup attempt",
            status="attempted", severity="info",
            event_data={"lookup_type": "exact_national_id", "contains_personal_data": False},
        ))
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "Client lookup audit unavailable") from exc
