"""PostgreSQL-backed, tenant-scoped registration idempotency reservations.

Internal only; no public endpoint invokes this code. All operations require
the caller's transaction, never commit, and never insert a borrower.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from database.models.new_client_registration_attempt import NewClientRegistrationAttempt
from database.models.company_client import CompanyBorrowerAccount
from services.new_only_client_registration import NewOnlyRegistrationIntent


class IdempotencyConflict(ValueError):
    pass


class IdempotencyUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistrationReservation:
    attempt_id: UUID
    status: str
    existing: bool
    client_account_id: UUID | None


def reserve_new_client_registration(
    db: Session, *, intent: NewOnlyRegistrationIntent,
) -> RegistrationReservation:
    """Atomic upsert of request key; lock and compare the complete request.

    A company/key is unique. An existing matching request never starts a
    second operation; the caller must review its status before proceeding.
    """
    if not isinstance(intent, NewOnlyRegistrationIntent):
        raise IdempotencyConflict("Validated registration intent required")
    if db.get_bind() is None or db.get_bind().dialect.name != "postgresql":
        raise IdempotencyUnavailable("PostgreSQL required")
    if not db.in_transaction():
        raise IdempotencyUnavailable("Caller-managed transaction required")

    table = NewClientRegistrationAttempt.__table__
    new_id = uuid4()
    statement = (
        pg_insert(table)
        .values(
            id=new_id,
            company_id=intent.company_id,
            branch_id=intent.branch_id,
            employee_user_id=intent.employee_id,
            idempotency_key=intent.idempotency_key,
            request_fingerprint=intent.registration_fingerprint,
            status="reserved",
        )
        .on_conflict_do_nothing(
            constraint="uq_new_client_registration_company_idempotency")
        .returning(table.c.id)
    )
    inserted_id = db.execute(statement).scalar_one_or_none()
    row = db.execute(
        select(NewClientRegistrationAttempt)
        .where(
            NewClientRegistrationAttempt.company_id == intent.company_id,
            NewClientRegistrationAttempt.idempotency_key == intent.idempotency_key,
        )
        .with_for_update()
    ).scalar_one()
    if (
        row.request_fingerprint != intent.registration_fingerprint
        or row.branch_id != intent.branch_id
        or row.employee_user_id != intent.employee_id
    ):
        raise IdempotencyConflict(
            "Request key already belongs to a different registration")
    if row.status not in ("reserved", "completed", "rejected"):
        raise IdempotencyConflict("Unexpected registration state")
    return RegistrationReservation(
        attempt_id=row.id,
        status=row.status,
        existing=inserted_id is None,
        client_account_id=row.client_account_id,
    )


def finalize_new_client_registration(
    db: Session, *, intent: NewOnlyRegistrationIntent,
    reservation: RegistrationReservation, client_account_id: UUID,
) -> None:
    """Complete a newly reserved request and newly created scoped account.

    This does not commit. The account, audit event, and reservation must all
    be part of the exact same caller-owned transaction. Existing completed or
    rejected attempts may not be modified.
    """
    if (
        not isinstance(intent, NewOnlyRegistrationIntent)
        or not isinstance(reservation, RegistrationReservation)
        or not isinstance(client_account_id, UUID)
        or reservation.existing
        or reservation.status != "reserved"
    ):
        raise IdempotencyConflict("New reservation required for completion")
    if db.get_bind() is None or db.get_bind().dialect.name != "postgresql":
        raise IdempotencyUnavailable("PostgreSQL required")
    if not db.in_transaction():
        raise IdempotencyUnavailable("Caller-managed transaction required")

    attempt = db.execute(
        select(NewClientRegistrationAttempt).where(
            NewClientRegistrationAttempt.id == reservation.attempt_id,
            NewClientRegistrationAttempt.company_id == intent.company_id,
            NewClientRegistrationAttempt.branch_id == intent.branch_id,
            NewClientRegistrationAttempt.employee_user_id == intent.employee_id,
            NewClientRegistrationAttempt.idempotency_key == intent.idempotency_key,
            NewClientRegistrationAttempt.request_fingerprint == intent.registration_fingerprint,
        ).with_for_update()
    ).scalar_one_or_none()
    if attempt is None or attempt.status != "reserved" or attempt.client_account_id is not None:
        raise IdempotencyConflict("Registration state changed before completion")

    account = db.execute(
        select(CompanyBorrowerAccount).where(
            CompanyBorrowerAccount.id == client_account_id,
            CompanyBorrowerAccount.company_id == intent.company_id,
            CompanyBorrowerAccount.branch_id == intent.branch_id,
            CompanyBorrowerAccount.opened_by_user_id == intent.employee_id,
        )
    ).scalar_one_or_none()
    if account is None:
        raise IdempotencyConflict("New account does not belong to registration scope")

    attempt.client_account_id = client_account_id
    attempt.status = "completed"
    attempt.finalized_at = datetime.now(timezone.utc)
    db.flush()
