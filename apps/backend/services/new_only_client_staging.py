"""Phase 70: stage *new identity only* rows in a single caller-owned transaction.

INTERNAL staging primitive only. No API route or live feature invokes it.
The production gateway remains fail-closed via execute_new_only_registration.
This function has no commit, no global borrower lookup/link, no loan changes.
The caller must enforce verified KYC, normalized DB uniqueness, identity locks,
persistent idempotency, tenant roles, and rollback of all rows on any error.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.user import User
from database.models.person import Person
from database.models.borrower import Borrower
from database.models.company_client import CompanyBorrowerAccount
from database.models.audit_log import AuditLog
from database.models.enums import UserRole
from services.company_client_service import account_reference
from services.new_only_client_registration import NewOnlyRegistrationIntent


class NewOnlyStagingDenied(RuntimeError):
    pass


@dataclass(frozen=True)
class MinimalNewClient:
    first_name: str
    last_name: str
    phone: str
    date_of_birth: date
    gender: object
    national_id: str | None
    passport_number: str | None
    district: str
    employment_status: object
    consent_to_share_profile: bool
    consent_to_credit_checks: bool


@dataclass(frozen=True)
class StagedNewClient:
    user_id: UUID
    borrower_id: UUID
    client_account_id: UUID
    company_id: UUID
    branch_id: UUID


def validate_minimal_new_client(payload: MinimalNewClient) -> None:
    if not isinstance(payload, MinimalNewClient):
        raise NewOnlyStagingDenied("A minimal validated client record is required")
    for v in (payload.first_name, payload.last_name, payload.district):
        if not isinstance(v, str) or not 1 <= len(v.strip()) <= 100:
            raise NewOnlyStagingDenied("Invalid required client field")
    if not isinstance(payload.phone, str) or not 8 <= len(payload.phone.strip()) <= 30:
        raise NewOnlyStagingDenied("Invalid client phone")
    if not isinstance(payload.date_of_birth, date) or payload.date_of_birth >= date.today():
        raise NewOnlyStagingDenied("Invalid date of birth")
    if not any(isinstance(v, str) and bool(v.strip())
               for v in (payload.national_id, payload.passport_number)):
        raise NewOnlyStagingDenied("National ID or passport required")
    if payload.gender is None or payload.employment_status is None:
        raise NewOnlyStagingDenied("Gender and employment status are required")
    if type(payload.consent_to_share_profile) is not bool or type(payload.consent_to_credit_checks) is not bool:
        raise NewOnlyStagingDenied("Explicit consent decisions are required")


def stage_new_only_client_rows(
    db: Session, *,
    intent: NewOnlyRegistrationIntent,
    payload: MinimalNewClient,
    password_hash: str,
    approved_internal_call: bool = False,
) -> StagedNewClient:
    """Add and flush ONLY new rows. Never commit or re-use an existing borrower.

    Hard-disabled by default. Even callers setting approved_internal_call=True
    must first meet external database/idempotency/identity gate requirements.
    Do not expose this function as a public API or background job.
    """
    if approved_internal_call is not True:
        raise NewOnlyStagingDenied("Internal new-only staging not activated")
    if not isinstance(intent, NewOnlyRegistrationIntent):
        raise NewOnlyStagingDenied("Verified staff registration intent required")
    validate_minimal_new_client(payload)
    if not isinstance(password_hash, str) or not 20 <= len(password_hash) <= 255:
        raise NewOnlyStagingDenied("Server-generated secure password hash required")
    if db.get_bind() is None or db.get_bind().dialect.name != "postgresql" or not db.in_transaction():
        raise NewOnlyStagingDenied("Caller-controlled PostgreSQL transaction required")

    # New rows are additive only; no UPDATE on any pre-existing borrower,
    # user, loan, bank account or repayment table.
    user = User(
        phone=payload.phone.strip(),
        password_hash=password_hash,
        role=UserRole.BORROWER,
        is_active=True, is_verified=False,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    person = Person(
        user_id=user.id,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        national_id=payload.national_id.strip() if payload.national_id else None,
        passport_number=payload.passport_number.strip() if payload.passport_number else None,
        district=payload.district.strip(),
    )
    borrower = Borrower(
        user_id=user.id,
        employment_status=payload.employment_status,
        consent_to_share_profile=payload.consent_to_share_profile,
        consent_to_credit_checks=payload.consent_to_credit_checks,
        has_existing_loans=False,
        existing_loan_total=Decimal("0"),
    )
    db.add_all([person, borrower])
    db.flush()
    account = CompanyBorrowerAccount(
        company_id=intent.company_id, branch_id=intent.branch_id,
        borrower_id=borrower.id, opened_by_user_id=intent.employee_id,
        account_reference=account_reference(),
        source="assisted_registration", status="active",
        opening_fee_amount=Decimal("0"),
        opening_fee_currency="LSL", opening_fee_status="not_required",
    )
    db.add(account)
    db.flush()
    db.add(AuditLog(
        user_id=intent.employee_id,
        company_id=intent.company_id,
        branch_id=intent.branch_id,
        action="company_client.new_only_registration_staged",
        table_name="company_borrower_accounts",
        entity_type="company_client",
        record_id=account.id,
        description="New-only borrower and company account staged.",
        actor_role="loan_officer",
        severity="info", status="success",
        before_data={},
        after_data={"client_account_id": str(account.id)},
        changed_fields=[],
        event_data={"registration_attempt_idempotency_key": intent.idempotency_key},
    ))
    db.flush()
    return StagedNewClient(
        user_id=user.id, borrower_id=borrower.id,
        client_account_id=account.id,
        company_id=intent.company_id, branch_id=intent.branch_id,
    )
