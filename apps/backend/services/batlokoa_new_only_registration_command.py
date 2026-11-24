"""Batlokoa new-only client command adapter (unmounted until approved release).

No FastAPI router imports this module. Approval is deliberately an explicit
server-side argument, never a request field, environment flag or frontend value.
Production release remains blocked by identity migrations and governance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.tenant_context import bind_database_tenant_context
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from services.atomic_new_client_registration import (
    AtomicRegistrationResult,
    create_full_new_client_atomically,
)


class BatlokoaRegistrationNotReleased(RuntimeError):
    """New-only client registration has not passed the production release gate."""


@dataclass(frozen=True)
class BatlokoaNewClientReceipt:
    client_account_id: UUID
    replayed: bool


def submit_new_only_client(
    *,
    context: TenantContext,
    payload: FullNewOnlyClientCapture,
    idempotency_key: str,
    fingerprint_secret: bytes,
    session_factory: Callable[[], Session],
    independently_approved_release: bool = False,
) -> BatlokoaNewClientReceipt:
    """Execute the existing fully atomic writer only after independent approval.

    Caller must derive context from LoanHub authentication, never browser
    company/role headers. The dedicated Session is required because ordinary
    FastAPI auth dependencies may already have opened an SQLAlchemy transaction.

    This is an internal staging adapter, not a deployed API endpoint. Its
    approval argument MUST NOT be connected to user input or a runtime feature
    flag. A future reviewed router must enforce release approval independently.
    """
    if independently_approved_release is not True:
        raise BatlokoaRegistrationNotReleased("New-only registration is not released")
    if not isinstance(payload, FullNewOnlyClientCapture):
        raise ValueError("Validated complete client capture required")
    if (
        not isinstance(context, TenantContext)
        or context.is_platform_admin
        or context.user is None
        or context.staff is None
        or context.user.is_active is not True
        or context.staff.is_active is not True
        or context.company_id is None
        or context.staff.company_id != context.company_id
        or context.staff.user_id != context.user.id
    ):
        raise ValueError("Verified active LoanHub staff context required")
    if not isinstance(idempotency_key, str) or not 16 <= len(idempotency_key) <= 128:
        raise ValueError("Valid server-bound idempotency key required")
    if not isinstance(fingerprint_secret, bytes) or len(fingerprint_secret) < 32:
        raise ValueError("Server-owned fingerprint secret required")
    # Session is dedicated to the existing writer's single db.begin() boundary.
    # Never partially create borrower rows in Batlokoa's gateway.
    with session_factory() as db:
        # Restore authenticated tenant RLS context on the dedicated session.
        # The SQLAlchemy after_begin hook applies it transaction-locally.
        bind_database_tenant_context(
            db,
            user_id=context.user.id,
            company_id=context.company_id,
            branch_id=context.branch_id,
            role=context.role.value,
            actor_scope="tenant",
        )
        result: AtomicRegistrationResult = create_full_new_client_atomically(
            db,
            context=context,
            payload=payload,
            idempotency_key=idempotency_key,
            fingerprint_secret=fingerprint_secret,
        )
    return BatlokoaNewClientReceipt(
        client_account_id=result.client_account_id,
        replayed=result.existing,
    )
