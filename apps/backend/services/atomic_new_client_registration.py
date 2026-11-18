"""Internal new-only registration transaction, with all writes in one commit.

NO API ROUTE invokes this entry point and NO production feature enables it.
The function requires all four normalized database uniqueness indexes to be
present, valid, ready and structurally correct. In today's schema these are
not installed, so this method fails BEFORE any client write.

This deliberately handles a restricted minimal registration payload. Bank,
debt, government payroll, and advanced employment details cannot be dropped
silently: they are rejected until a separate vetted capture path exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import secrets
from uuid import UUID

from sqlalchemy import text, select, func
from database.models.legacy_loan_capture import LegacyLoanCapture
from database.models.company_client import CompanyBorrowerAccount
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from core.security import hash_password
from database.schemas.company_clients import AssistedCompanyClientCreate
from services.new_client_identity_locks import check_with_transaction_identity_locks
from services.new_client_registration_idempotency import (
    reserve_new_client_registration, finalize_new_client_registration,
)
from services.new_only_client_registration import (
    prepare_new_only_registration_intent,
)
from services.new_only_client_staging import (
    MinimalNewClient, stage_new_only_client_rows,
)
from services.platform_finance_service import (
    active_company_account_opening_fee_configuration,
)


class AtomicRegistrationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AtomicRegistrationResult:
    client_account_id: UUID
    existing: bool


# These four named indexes require independent DBA review. The check is
# fail-closed if the DB schema, index names or expressions differ. Other
# identity writers must still be audited before enabling any API route.
_REQUIRED = (
    ("people", "national_id", "uq_people_national_id_normalized"),
    ("people", "passport_number", "uq_people_passport_normalized"),
    ("users", "phone", "uq_users_phone_normalized"),
    ("users", "email", "uq_users_email_normalized"),
)


def require_normalized_identity_constraints(db: Session) -> None:
    if db.get_bind() is None or db.get_bind().dialect.name != "postgresql":
        raise AtomicRegistrationUnavailable("PostgreSQL required")
    for table_name, field, index_name in _REQUIRED:
        record = db.execute(text("""
            SELECT i.indisunique, i.indisvalid, i.indisready,
                   pg_get_expr(i.indexprs, i.indrelid),
                   pg_get_expr(i.indpred, i.indrelid)
            FROM pg_index i
            JOIN pg_class idx ON idx.oid = i.indexrelid
            JOIN pg_class tbl ON tbl.oid = i.indrelid
            JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
            WHERE ns.nspname = current_schema()
              AND tbl.relname = :table_name AND idx.relname = :index_name
        """), {"table_name": table_name, "index_name": index_name}).one_or_none()
        if record is None or any(value is not True for value in record[:3]):
            raise AtomicRegistrationUnavailable("Verified normalized identity constraints required")
        expr, predicate = record[3], record[4]
        # PostgreSQL deparsing can include cast parentheses. Accept only a
        # lower(btrim(column)) expression (plus optional SQL text casts).
        flattened = re.sub(r"\s+", "", str(expr).lower())
        normalized = flattened.replace("(", "").replace(")", "")
        if (
            not flattened.startswith("lower(btrim(")
            or field not in normalized
            or any(x not in normalized for x in ("lower", "btrim"))
            or not predicate
            or field not in str(predicate)
            or "IS NOT NULL" not in str(predicate).upper()
        ):
            raise AtomicRegistrationUnavailable("Unexpected normalized index definition")


def _minimal_only(payload: AssistedCompanyClientCreate) -> MinimalNewClient:
    """Refuse data that the first atomic writer cannot safely store."""
    if not isinstance(payload, AssistedCompanyClientCreate):
        raise AtomicRegistrationUnavailable("Validated assisted-client schema required")
    unsupported = (
        payload.email is not None
        or payload.temporary_password is not None
        or bool(payload.middle_name)
        or payload.marital_status is not None
        or bool(payload.town_or_village)
        or bool(payload.physical_address)
        or bool(payload.employment_type)
        or bool(payload.cdas_employee_number)
        or bool(payload.employer_name)
        or payload.employer_group_id is not None
        or payload.new_employer_group is not None
        or payload.income_day is not None
        or bool(payload.job_title)
        or payload.monthly_income is not None
        or bool(payload.salary_date)
        or payload.has_existing_loans
        or bool(payload.existing_loan_total)
        or bool(payload.external_debts)
        or payload.bank_account is not None
        or (payload.nationality or "Mosotho") != "Mosotho"
    )
    if unsupported:
        raise AtomicRegistrationUnavailable(
            "Unsupported fields require separately certified registration capture")
    return MinimalNewClient(
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        national_id=payload.national_id,
        passport_number=payload.passport_number,
        district=payload.district,
        employment_status=payload.employment_status,
        consent_to_share_profile=payload.consent_to_share_profile,
        consent_to_credit_checks=payload.consent_to_credit_checks,
    )


def create_new_client_atomically(
    db: Session, *,
    context: TenantContext,
    payload: AssistedCompanyClientCreate,
    idempotency_key: str,
    fingerprint_secret: bytes,
) -> AtomicRegistrationResult:
    """Private callable implementation; never used from a public API.

    The registration attempt, newly created borrower/account and audit entry
    are committed together by one db.begin() context manager. Every exception
    rolls back all work. No existing global borrower is ever updated.
    """
    # Validate the request and LoanHub staff role/branch BEFORE opening
    # the write transaction. The caller must supply the authoritative
    # LoanHub tenant context, not headers from Batlokoa.
    minimal = _minimal_only(payload)
    if payload.branch_id is None:
        raise AtomicRegistrationUnavailable("Explicit assigned branch required")
    intent = prepare_new_only_registration_intent(
        context=context,
        branch_id=payload.branch_id,
        idempotency_key=idempotency_key,
        payload=payload,
        secret=fingerprint_secret,
    )
    if db.in_transaction():
        raise AtomicRegistrationUnavailable("Dedicated transaction required")

    with db.begin():
        # DB unique indexes are mandatory: advisory locks alone do not stop
        # old or third-party writers using other code paths.
        require_normalized_identity_constraints(db)

        # Lock first, then upsert idempotency record under the same tx.
        # The scanning guard always returns candidate=False by design:
        # only the validated *reason* and counters are interpreted here.
        guard = check_with_transaction_identity_locks(
            db,
            company_id=intent.company_id,
            national_id=minimal.national_id,
            passport_number=minimal.passport_number,
            phone=minimal.phone,
        )
        reservation = reserve_new_client_registration(db, intent=intent)
        if reservation.existing:
            if reservation.status == "completed" and reservation.client_account_id:
                # Replay must resolve to an existing account in the same
                # company, branch and actor scope, never trust an ID alone.
                prior = db.execute(select(CompanyBorrowerAccount.id).where(
                    CompanyBorrowerAccount.id == reservation.client_account_id,
                    CompanyBorrowerAccount.company_id == intent.company_id,
                    CompanyBorrowerAccount.branch_id == intent.branch_id,
                    CompanyBorrowerAccount.opened_by_user_id == intent.employee_id,
                )).scalar_one_or_none()
                if prior is None:
                    raise AtomicRegistrationUnavailable("Completed request account scope mismatch")
                return AtomicRegistrationResult(prior, True)
            raise AtomicRegistrationUnavailable("Registration request not independently finalized")

        # Global legacy captures can predate LoanHub borrower profiles.
        # Never treat a new Person row as safe when that ID occurs in a
        # different company's unlinked historical captures. Query only an
        # aggregate count; expose no cross-tenant client details.
        if minimal.national_id:
            normalized_id = minimal.national_id.strip().casefold()
            historic = db.query(func.count(LegacyLoanCapture.id)).filter(
                func.lower(func.trim(LegacyLoanCapture.national_id)) == normalized_id,
            ).scalar()
            if type(historic) is not int or historic > 0 or historic < 0:
                raise AtomicRegistrationUnavailable(
                    "Existing historical identity requires controlled review")

        if (
            guard.reason != "candidate_requires_transactional_reservation"
            or guard.identity_conflicts != 0
            or guard.legacy_conflicts != 0
        ):
            raise AtomicRegistrationUnavailable("Existing identity or legacy record requires review")

        fee = active_company_account_opening_fee_configuration(
            db, company_id=intent.company_id)
        # A fresh random secret is never returned to Batlokoa or logged.
        server_password_hash = hash_password(secrets.token_urlsafe(36))
        account = stage_new_only_client_rows(
            db, intent=intent, payload=minimal,
            password_hash=server_password_hash,
            approved_internal_call=True,
            fee_config=fee,
        )
        finalize_new_client_registration(
            db, intent=intent, reservation=reservation,
            client_account_id=account.client_account_id,
        )
        return AtomicRegistrationResult(account.client_account_id, False)
