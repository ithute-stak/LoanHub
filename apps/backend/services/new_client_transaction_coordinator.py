"""Phase 71: transaction orchestration for *new-identity-only* registration.

This module exercises the required ordering of permissions, identity locks,
idempotency reservation, brand-new record staging and completion. It is an
internal unactivated protocol, not a FastAPI endpoint. It never commits and
must raise on every path until certified database constraints and verified
migration/transaction integration tests exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from services.new_client_identity_locks import check_with_transaction_identity_locks
from services.new_client_registration_idempotency import reserve_new_client_registration
from services.new_only_client_registration import NewOnlyRegistrationIntent
from services.new_only_client_staging import MinimalNewClient, validate_minimal_new_client


class ClientRegistrationNotActivated(RuntimeError):
    pass


@dataclass(frozen=True)
class NewOnlyTransactionPlan:
    company_id: UUID
    branch_id: UUID
    employee_id: UUID
    request_key: str
    requires_database_constraints: bool = True
    requires_legacy_review: bool = True
    requires_staging_certification: bool = True
    can_execute: bool = False


def plan_new_only_client_transaction(
    *, intent: NewOnlyRegistrationIntent, payload: MinimalNewClient,
) -> NewOnlyTransactionPlan:
    """Validate an immutable, minimal intent; do not read/write any DB rows."""
    if not isinstance(intent, NewOnlyRegistrationIntent):
        raise ClientRegistrationNotActivated("Verified registration intent required")
    validate_minimal_new_client(payload)
    if not isinstance(intent.company_id, UUID) or not isinstance(intent.branch_id, UUID):
        raise ClientRegistrationNotActivated("Company and branch scope required")
    if not isinstance(intent.employee_id, UUID):
        raise ClientRegistrationNotActivated("Verified employee required")
    if not isinstance(intent.idempotency_key, str) or not (
        16 <= len(intent.idempotency_key) <= 128
    ):
        raise ClientRegistrationNotActivated("Idempotency key required")
    return NewOnlyTransactionPlan(
        company_id=intent.company_id,
        branch_id=intent.branch_id,
        employee_id=intent.employee_id,
        request_key=intent.idempotency_key,
    )


def review_transaction_gate(
    db: Session, *, intent: NewOnlyRegistrationIntent,
    payload: MinimalNewClient,
) -> None:
    """Read-only identity screening; reject all writes before reservation.

    The caller owns the transaction. The guard verifies normalized identity
    and historical collisions under deterministic PostgreSQL locks.
    Until normalized uniqueness and all writer paths are certified, an
    empty result is NOT permission to reserve/create a record.
    """
    plan_new_only_client_transaction(intent=intent, payload=payload)
    if db.get_bind() is None or db.get_bind().dialect.name != "postgresql":
        raise ClientRegistrationNotActivated("PostgreSQL required")
    if not db.in_transaction():
        raise ClientRegistrationNotActivated("Caller-owned transaction required")
    scan = check_with_transaction_identity_locks(
        db, company_id=intent.company_id,
        national_id=payload.national_id,
        passport_number=payload.passport_number,
        phone=payload.phone,
    )
    if scan.reason == "existing_identity":
        raise ClientRegistrationNotActivated("Existing borrower or user requires review")
    if scan.reason == "historical_collision":
        raise ClientRegistrationNotActivated("Legacy history requires review")
    # Every branch fails closed regardless of scan result. The functions
    # imported for reservation and staging are intentionally NOT invoked here.
    raise ClientRegistrationNotActivated(
        "Atomic creation remains blocked pending normalized uniqueness, "
        "persistent idempotency staging and full LoanHub transaction review"
    )
