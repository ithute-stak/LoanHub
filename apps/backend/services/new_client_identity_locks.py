"""Phase 64: deterministic PostgreSQL transaction locks for identity checks.

This is an internal building block for a future new-only registration route,
NOT a replacement for database uniqueness. The existing assisted registration
route is unchanged and does not yet participate in these locks.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.new_client_identity_guard import (
    NewClientGuardDecision,
    inspect_new_client_candidate,
)


class RegistrationLockUnavailable(RuntimeError):
    pass


def _identity_lock_keys(
    *, national_id: str | None, passport_number: str | None,
    phone: str, email: str | None,
) -> tuple[str, ...]:
    """Canonical, globally scoped keys shared across every company/branch."""
    fields = {
        "national_id": national_id,
        "passport_number": passport_number,
        "phone": phone,
        "email": email,
    }
    keys = []
    for kind, value in fields.items():
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError("Invalid identity field")
        normalized = value.strip().casefold()
        if not normalized:
            continue
        if len(normalized) > 150 or any(ord(c) < 32 for c in normalized):
            raise ValueError("Invalid identity field")
        keys.append("loanhub:new-client:identity:v1:" + kind + ":" + normalized)
    if not any(k.split(":")[4] in ("national_id", "passport_number")
               for k in keys) or not any(":phone:" in k for k in keys):
        raise ValueError("National ID/passport and phone are required")
    return tuple(sorted(set(keys)))


def check_with_transaction_identity_locks(
    db: Session,
    *, company_id: UUID,
    national_id: str | None,
    passport_number: str | None,
    phone: str,
    email: str | None = None,
) -> NewClientGuardDecision:
    """Hold globally keyed advisory locks until the caller's transaction ends.

    A future audited writer must acquire these locks in the *same transaction*
    before checking and inserting, and every other identity writer must follow
    the protocol. This function *never* inserts or commits.
    """
    if not isinstance(company_id, UUID):
        raise ValueError("Verified company required")
    keys = _identity_lock_keys(
        national_id=national_id, passport_number=passport_number,
        phone=phone, email=email)
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        raise RegistrationLockUnavailable("PostgreSQL required")
    if not db.in_transaction():
        raise RegistrationLockUnavailable("Caller-managed transaction required")

    # PostgreSQL transactional advisory locks automatically release on commit
    # or rollback. Fixed namespace, sorted lock order to reduce deadlocks.
    for key in keys:
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity_key, 0))"),
            {"identity_key": key},
        )
    # Never set candidate=True here. This is still only a read-only guard.
    return inspect_new_client_candidate(
        db, company_id=company_id,
        national_id=national_id, passport_number=passport_number,
        phone=phone, email=email,
    )
