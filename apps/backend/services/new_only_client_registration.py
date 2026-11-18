"""Phase 68: new-only client registration transaction boundary.

Deliberately INTERNAL and NOT connected to a FastAPI router. Requires a
separately approved database uniqueness rollout and persistent idempotency
before activation. No current feature flag can enable live writes.

Critically, this service never calls create_assisted_company_client: that
legacy function may update an existing global borrower.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import (
    LENDING_ROLES, TenantContext, assert_branch_scope, require_tenant_roles,
)
from services.new_client_identity_locks import (
    check_with_transaction_identity_locks,
)


class NewOnlyRegistrationNotReady(RuntimeError):
    """No safe new-client write transaction is deployed."""


@dataclass(frozen=True)
class NewOnlyRegistrationIntent:
    company_id: UUID
    branch_id: UUID
    employee_id: UUID
    idempotency_key: str
    registration_fingerprint: str


def _normalized(value: str | None) -> str:
    return (value or "").strip().casefold()


def prepare_new_only_registration_intent(
    *,
    context: TenantContext,
    branch_id: UUID,
    idempotency_key: str,
    payload: object,
    secret: bytes,
) -> NewOnlyRegistrationIntent:
    """Bind an intent to verified LoanHub staff and canonical request content.

    A keyed HMAC is used to avoid exposing a raw identity/PII hash. This
    fingerprint is not itself a unique constraint or an idempotency store.
    """
    require_tenant_roles(context, LENDING_ROLES)
    if not isinstance(context.company_id, UUID) or not isinstance(context.user.id, UUID):
        raise ValueError("Authoritative LoanHub employee/company required")
    if not isinstance(branch_id, UUID):
        raise ValueError("Valid branch UUID required")
    assert_branch_scope(context, branch_id)
    if (
        not isinstance(idempotency_key, str)
        or not 16 <= len(idempotency_key) <= 128
        or not all(ch.isascii() and (ch.isalnum() or ch in "-_.")
                   for ch in idempotency_key)
    ):
        raise ValueError("Invalid idempotency key")
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("Server-only HMAC secret required")

    required = (
        "first_name", "last_name", "phone", "date_of_birth",
        "national_id", "passport_number",
    )
    values = {key: getattr(payload, key, None) for key in required}
    for field in ("first_name", "last_name", "phone"):
        if not isinstance(values[field], str) or not values[field].strip():
            raise ValueError("Missing registration field")
    if not (_normalized(values["national_id"]) or
            _normalized(values["passport_number"])):
        raise ValueError("An identity document is required")
    dob = values["date_of_birth"]
    if dob is None or not hasattr(dob, "isoformat"):
        raise ValueError("Date of birth required")
    # An idempotency replay must compare the *entire* submitted command,
    # not just identity fields (which would miss changes to salary, consent,
    # employer, address, debts or bank information).
    if not callable(getattr(payload, "model_dump", None)):
        raise ValueError("Validated registration schema required")
    canonical = json.dumps({
        "company": str(context.company_id),
        "branch": str(branch_id),
        "actor": str(context.user.id),
        "payload": payload.model_dump(mode="json", exclude_none=False),
    }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    digest = hmac.new(secret, canonical, sha256).hexdigest()
    return NewOnlyRegistrationIntent(
        company_id=context.company_id,
        branch_id=branch_id,
        employee_id=context.user.id,
        idempotency_key=idempotency_key,
        registration_fingerprint=digest,
    )


def execute_new_only_registration(
    db: Session,
    *,
    intent: NewOnlyRegistrationIntent,
    national_id: str | None,
    passport_number: str | None,
    phone: str,
    email: str | None = None,
):
    """Fail-closed transaction outline; never performs client writes.

    Readiness depends on a reviewed unique-index migration, all writers
    adopting a common serialization protocol, and a persistent idempotency
    record. Until those are independently proven, even a clear check fails.
    """
    if not isinstance(intent, NewOnlyRegistrationIntent):
        raise NewOnlyRegistrationNotReady("Verified intent required")
    check_with_transaction_identity_locks(
        db,
        company_id=intent.company_id,
        national_id=national_id,
        passport_number=passport_number,
        phone=phone,
        email=email,
    )
    raise NewOnlyRegistrationNotReady(
        "Database constraints, persistent idempotency and "
        "transactional new-only creation are not yet certified"
    )
