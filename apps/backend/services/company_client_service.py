from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.access_control import TenantContext, assert_branch_scope
from core.security import hash_password
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import LoanStatus, UserRole
from database.models.origination import (
    BorrowerBankAccount,
    BorrowerDebtObligation,
    BorrowerDebtObligationEvent,
)
from database.models.person import Person
from database.models.user import User
from services.credential_service import encrypt_credential
from services.employer_group_service import resolve_employer_group
from services.platform_finance_service import (
    active_company_account_opening_fee_configuration,
    apply_company_account_opening_fee_snapshot,
)


def account_reference() -> str:
    return f"CLI-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(4).upper()}"


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None



def _save_assisted_banking_profile(
    db: Session,
    *,
    borrower: Borrower,
    company_id: UUID,
    bank_input,
) -> BorrowerBankAccount | None:
    """Save bank account details without storing full card PAN/CVV/PIN.

    Bank account numbers and provider card tokens are encrypted at rest. Card data
    is limited to masked/last-four identification metadata plus expiry/brand.
    """
    if bank_input is None:
        return None

    existing = (
        db.query(BorrowerBankAccount)
        .filter(
            BorrowerBankAccount.borrower_id == borrower.id,
        )
        .order_by(
            BorrowerBankAccount.salary_account.desc(),
            BorrowerBankAccount.updated_at.desc(),
        )
        .first()
    )
    account_number = clean_optional(bank_input.account_number)
    if not account_number and existing is None:
        raise HTTPException(
            status_code=422,
            detail="A bank account number is required when banking details are captured.",
        )

    encrypted_account = (
        encrypt_credential(account_number)
        if account_number
        else existing.account_number_encrypted
    )
    account_last4 = account_number[-4:] if account_number else existing.account_number_last4

    token_reference = clean_optional(bank_input.tokenized_card_reference)
    encrypted_token = (
        encrypt_credential(token_reference)
        if token_reference
        else (existing.tokenized_card_reference_encrypted if existing else None)
    )

    values = bank_input.model_dump(
        exclude={"account_number", "tokenized_card_reference"}
    )
    # Assisted registration only captures details. Verification belongs to the
    # KYC/origination workflow and cannot be self-declared by this request.
    values.update(
        {
            "verification_status": "unverified",
            "verification_reference": None,
            "verified_at": None,
            "account_number_encrypted": encrypted_account,
            "account_number_last4": account_last4,
            "tokenized_card_reference_encrypted": encrypted_token,
        }
    )

    if existing is None:
        existing = BorrowerBankAccount(
            company_id=company_id,
            borrower_id=borrower.id,
            **values,
        )
        db.add(existing)
    else:
        for key, value in values.items():
            setattr(existing, key, value)

    db.flush()
    return existing


_DEBT_MONTHLY_FACTORS = {
    "weekly": Decimal("4.333333"),
    "fortnightly": Decimal("2.166667"),
    "monthly": Decimal("1"),
    "quarterly": Decimal("0.333333"),
    "custom": Decimal("1"),
}
_ACTIVE_EXTERNAL_DEBT_STATUSES = ("active", "defaulted", "restructured", "unknown")


def normalized_monthly_debt_installment(amount: Decimal | int | float, frequency: str | None) -> Decimal:
    value = Decimal(str(amount or 0))
    factor = _DEBT_MONTHLY_FACTORS.get(str(frequency or "monthly").lower(), Decimal("1"))
    return (value * factor).quantize(Decimal("0.01"))


def external_debt_payload(row: BorrowerDebtObligation, *, include_events: bool = True) -> dict[str, object]:
    events = []
    if include_events:
        events = [
            {
                "id": item.id,
                "event_type": item.event_type,
                "event_at": item.event_at,
                "amount": item.amount,
                "balance_after": item.balance_after,
                "remaining_installments_after": item.remaining_installments_after,
                "notes": item.notes,
                "recorded_by_user_id": item.recorded_by_user_id,
            }
            for item in sorted(row.events or [], key=lambda event: event.event_at, reverse=True)[:25]
        ]
    return {
        "id": row.id,
        "company_id": row.company_id,
        "borrower_id": row.borrower_id,
        "creditor": row.creditor,
        "account_reference": row.account_reference,
        "debt_type": row.debt_type,
        "started_on": row.started_on,
        "original_amount": Decimal(row.original_amount or 0),
        "current_balance": Decimal(row.current_balance or 0),
        "installment_amount": Decimal(row.installment_amount or row.monthly_installment or 0),
        "installment_frequency": row.installment_frequency or "monthly",
        "monthly_installment": Decimal(row.monthly_installment or 0),
        "total_installments": row.total_installments,
        "installments_paid": int(row.installments_paid or 0),
        "remaining_installments": row.remaining_installments,
        "next_due_date": row.next_due_date,
        "status": row.status or "unknown",
        "source": row.source or "declared",
        "is_verified": bool(row.is_verified),
        "last_reviewed_at": row.last_reviewed_at,
        "notes": row.notes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "events": events,
    }


def sync_borrower_external_debt_summary(
    db: Session,
    *,
    borrower: Borrower,
    company_id: UUID | None = None,
) -> None:
    """Synchronize the legacy borrower summary from shared debt records.

    company_id is accepted for backward compatibility and records provenance
    only; external obligations are borrower-owned facts visible to concerned
    lenders.
    """
    balance = (
        db.query(func.coalesce(func.sum(BorrowerDebtObligation.current_balance), 0))
        .filter(
            BorrowerDebtObligation.borrower_id == borrower.id,
            BorrowerDebtObligation.status.in_(_ACTIVE_EXTERNAL_DEBT_STATUSES),
            BorrowerDebtObligation.current_balance > 0,
        )
        .scalar()
    )
    structured_total = Decimal(balance or 0)
    borrower.has_existing_loans = structured_total > 0
    borrower.existing_loan_total = structured_total


def save_assisted_external_debts(
    db: Session,
    *,
    borrower: Borrower,
    company_id: UUID,
    user_id: UUID,
    debts,
    legacy_total: Decimal | int | float = 0,
    legacy_has_existing_loans: bool = False,
) -> list[BorrowerDebtObligation]:
    created: list[BorrowerDebtObligation] = []
    now = datetime.now(timezone.utc)
    debt_inputs = list(debts or [])

    if not debt_inputs and legacy_has_existing_loans and Decimal(str(legacy_total or 0)) > 0:
        debt_inputs = [
            {
                "creditor": "Borrower-declared external lender",
                "debt_type": "other",
                "original_amount": Decimal(str(legacy_total)),
                "current_balance": Decimal(str(legacy_total)),
                "installment_amount": Decimal("0"),
                "installment_frequency": "monthly",
                "status": "unknown",
                "source": "legacy_registration",
                "is_verified": False,
                "notes": "Imported from the previous single existing-loan-total field. Review the installment schedule before the next affordability assessment.",
            }
        ]

    for raw in debt_inputs:
        values = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
        frequency = str(values.get("installment_frequency") or "monthly")
        installment_amount = Decimal(str(values.get("installment_amount") or 0))
        total_installments = values.get("total_installments")
        installments_paid = int(values.get("installments_paid") or 0)
        remaining_installments = values.get("remaining_installments")
        if remaining_installments is None and total_installments is not None:
            remaining_installments = max(int(total_installments) - installments_paid, 0)
        current_balance = Decimal(str(values.get("current_balance") or 0))
        status_value = str(values.get("status") or "active")
        if current_balance <= 0:
            status_value = "settled"

        row = BorrowerDebtObligation(
            company_id=company_id,
            borrower_id=borrower.id,
            creditor=str(values.get("creditor") or "External lender").strip(),
            account_reference=clean_optional(values.get("account_reference")),
            debt_type=str(values.get("debt_type") or "other"),
            started_on=values.get("started_on"),
            original_amount=Decimal(str(values.get("original_amount") or current_balance)),
            current_balance=current_balance,
            installment_amount=installment_amount,
            installment_frequency=frequency,
            monthly_installment=normalized_monthly_debt_installment(installment_amount, frequency),
            total_installments=total_installments,
            installments_paid=installments_paid,
            remaining_installments=remaining_installments,
            remaining_term_months=(remaining_installments if frequency == "monthly" else None),
            next_due_date=values.get("next_due_date"),
            status=status_value,
            source=str(values.get("source") or "declared"),
            is_verified=bool(values.get("is_verified")),
            last_reviewed_at=now,
            last_reviewed_by_user_id=user_id,
            notes=clean_optional(values.get("notes")),
        )
        db.add(row)
        db.flush()
        db.add(
            BorrowerDebtObligationEvent(
                company_id=company_id,
                borrower_id=borrower.id,
                obligation_id=row.id,
                recorded_by_user_id=user_id,
                event_type="created",
                event_at=now,
                balance_after=current_balance,
                remaining_installments_after=remaining_installments,
                notes="Existing external loan captured during borrower registration.",
            )
        )
        created.append(row)

    db.flush()
    if created or legacy_has_existing_loans:
        sync_borrower_external_debt_summary(db, borrower=borrower, company_id=company_id)
    return created


def find_person_by_national_id(db: Session, national_id: str | None) -> Person | None:
    cleaned = clean_optional(national_id)
    if not cleaned:
        return None
    return (
        db.query(Person)
        .options(joinedload(Person.user).joinedload(User.borrower_profile))
        .filter(func.lower(func.trim(Person.national_id)) == cleaned.lower())
        .first()
    )


def borrower_existing_loan_exposure(
    db: Session,
    *,
    borrower: Borrower | None,
    company_id: UUID,
) -> dict[str, object]:
    """Return privacy-safe aggregate LoanHub credit history for a national-ID match.

    The result intentionally excludes lender names, private notes, documents and
    other tenant-owned details. It gives authorised lending staff enough summary
    information to detect an existing borrower and make a safer onboarding
    decision without exposing another company's confidential client record.
    """
    zero = Decimal("0.00")
    if borrower is None:
        return {
            "borrower_found": False,
            "already_company_client": False,
            "company_client_account_id": None,
            "has_existing_loans": False,
            "total_loan_count": 0,
            "active_loan_count": 0,
            "completed_loan_count": 0,
            "defaulted_loan_count": 0,
            "overdue_loan_count": 0,
            "lender_count": 0,
            "loanhub_outstanding_total": zero,
            "declared_existing_loan_total": zero,
            "external_debt_count": 0,
            "external_debt_balance_total": zero,
            "external_debt_monthly_commitment": zero,
            "external_debts": [],
            "existing_loan_total": zero,
            "lifetime_principal_total": zero,
            "lifetime_paid_total": zero,
            "latest_loan_at": None,
        }

    active_statuses = (
        LoanStatus.APPROVED,
        LoanStatus.ACTIVE,
        LoanStatus.DEFAULTED,
    )
    (
        total_loan_count,
        active_loan_count,
        completed_loan_count,
        defaulted_loan_count,
        overdue_loan_count,
        lender_count,
        loanhub_total,
        lifetime_principal_total,
        lifetime_paid_total,
        latest_loan_at,
    ) = (
        db.query(
            func.count(ClientCompanyLoan.id),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ClientCompanyLoan.status.in_(active_statuses)
                            & (ClientCompanyLoan.balance > 0),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (ClientCompanyLoan.status == LoanStatus.COMPLETED, 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (ClientCompanyLoan.status == LoanStatus.DEFAULTED, 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((ClientCompanyLoan.is_overdue.is_(True), 1), else_=0)
                ),
                0,
            ),
            func.count(func.distinct(ClientCompanyLoan.company_id)),
            func.coalesce(
                func.sum(
                    case(
                        (
                            ClientCompanyLoan.status.in_(active_statuses)
                            & (ClientCompanyLoan.balance > 0),
                            ClientCompanyLoan.balance,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(ClientCompanyLoan.principal_amount), 0),
            func.coalesce(func.sum(ClientCompanyLoan.amount_paid), 0),
            func.max(ClientCompanyLoan.created_at),
        )
        .filter(ClientCompanyLoan.borrower_id == borrower.id)
        .one()
    )

    external_debt_rows = (
        db.query(BorrowerDebtObligation)
        .options(joinedload(BorrowerDebtObligation.events))
        .filter(
            BorrowerDebtObligation.borrower_id == borrower.id,
        )
        .order_by(BorrowerDebtObligation.started_on.desc().nullslast(), BorrowerDebtObligation.created_at.desc())
        .all()
    )
    active_external_debts = [
        row
        for row in external_debt_rows
        if (row.status or "unknown") in _ACTIVE_EXTERNAL_DEBT_STATUSES
        and Decimal(row.current_balance or 0) > 0
    ]
    structured_external_total = sum(
        (Decimal(row.current_balance or 0) for row in active_external_debts),
        Decimal("0"),
    )
    structured_monthly_commitment = sum(
        (Decimal(row.monthly_installment or 0) for row in active_external_debts),
        Decimal("0"),
    )
    legacy_declared_total = Decimal(borrower.existing_loan_total or 0)
    declared_total = structured_external_total if external_debt_rows else legacy_declared_total
    outstanding_total = Decimal(loanhub_total or 0)
    combined_total = outstanding_total + declared_total
    company_account = (
        db.query(CompanyBorrowerAccount.id)
        .filter(
            CompanyBorrowerAccount.company_id == company_id,
            CompanyBorrowerAccount.borrower_id == borrower.id,
        )
        .first()
    )
    return {
        "borrower_found": True,
        "already_company_client": company_account is not None,
        "company_client_account_id": company_account[0] if company_account else None,
        "has_existing_loans": bool(
            active_loan_count
            or declared_total > 0
            or borrower.has_existing_loans
        ),
        "total_loan_count": int(total_loan_count or 0),
        "active_loan_count": int(active_loan_count or 0),
        "completed_loan_count": int(completed_loan_count or 0),
        "defaulted_loan_count": int(defaulted_loan_count or 0),
        "overdue_loan_count": int(overdue_loan_count or 0),
        "lender_count": int(lender_count or 0),
        "loanhub_outstanding_total": outstanding_total,
        "declared_existing_loan_total": declared_total,
        "external_debt_count": len(active_external_debts),
        "external_debt_balance_total": structured_external_total,
        "external_debt_monthly_commitment": structured_monthly_commitment,
        "external_debts": [external_debt_payload(row) for row in external_debt_rows],
        "existing_loan_total": combined_total,
        "lifetime_principal_total": Decimal(lifetime_principal_total or 0),
        "lifetime_paid_total": Decimal(lifetime_paid_total or 0),
        "latest_loan_at": latest_loan_at,
    }


def _create_company_borrower_account(
    db: Session,
    *,
    borrower: Borrower,
    branch_id: UUID | None,
    context: TenantContext,
    source: str,
    fee_config,
) -> CompanyBorrowerAccount:
    account = CompanyBorrowerAccount(
        company_id=context.company_id,
        branch_id=branch_id,
        borrower_id=borrower.id,
        opened_by_user_id=context.user.id,
        account_reference=account_reference(),
        source=source,
        status="active",
    )
    apply_company_account_opening_fee_snapshot(account, fee_config=fee_config)
    if account.opening_fee_amount and account.opening_fee_amount > 0:
        account.opening_fee_status = "accrued"
    db.add(account)
    db.commit()
    return company_client_or_404(
        db,
        account_id=account.id,
        company_id=context.company_id,
    )


def company_client_or_404(db: Session, *, account_id: UUID, company_id: UUID) -> CompanyBorrowerAccount:
    item = (
        db.query(CompanyBorrowerAccount)
        .options(joinedload(CompanyBorrowerAccount.borrower).joinedload(Borrower.user).joinedload(User.person))
        .filter(CompanyBorrowerAccount.id == account_id, CompanyBorrowerAccount.company_id == company_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Company client account not found")
    return item


def create_assisted_company_client(db: Session, *, payload, context: TenantContext) -> CompanyBorrowerAccount:
    """Open or link a borrower account for the active lending company.

    A national-ID match reuses the existing global borrower identity after a
    date-of-birth and surname check. This avoids duplicate identities and lets
    the company see the borrower's current LoanHub exposure before lending.
    """
    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)
    email = clean_optional(str(payload.email) if payload.email else None)
    phone = payload.phone.strip()
    national_id = clean_optional(payload.national_id)
    passport_number = clean_optional(payload.passport_number)
    fee_config = active_company_account_opening_fee_configuration(
        db,
        company_id=context.company_id,
    )

    existing_person = find_person_by_national_id(db, national_id)
    if existing_person is not None:
        borrower = existing_person.user.borrower_profile if existing_person.user else None
        if borrower is None:
            raise HTTPException(
                status_code=409,
                detail="The national ID belongs to an account without a borrower profile.",
            )
        same_birth_date = existing_person.date_of_birth == payload.date_of_birth
        same_surname = (
            (existing_person.last_name or "").strip().casefold()
            == payload.last_name.strip().casefold()
        )
        if not same_birth_date or not same_surname:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The national ID belongs to an existing borrower, but the "
                    "date of birth or surname does not match."
                ),
            )
        if (
            db.query(CompanyBorrowerAccount.id)
            .filter(
                CompanyBorrowerAccount.company_id == context.company_id,
                CompanyBorrowerAccount.borrower_id == borrower.id,
            )
            .first()
        ):
            raise HTTPException(
                status_code=409,
                detail="This borrower already has an account with the active company.",
            )

        employer_group = resolve_employer_group(
            db,
            employer_group_id=payload.employer_group_id,
            new_employer_group=payload.new_employer_group,
        )

        borrower.consent_to_share_profile = bool(
            borrower.consent_to_share_profile or payload.consent_to_share_profile
        )
        borrower.consent_to_credit_checks = bool(
            borrower.consent_to_credit_checks or payload.consent_to_credit_checks
        )
        borrower.employment_status = payload.employment_status
        borrower.employer_group_id = employer_group.id if employer_group is not None else None
        borrower.employer_name = (
            employer_group.name if employer_group is not None else clean_optional(payload.employer_name)
        )
        borrower.income_day = payload.income_day
        borrower.job_title = clean_optional(payload.job_title)
        borrower.monthly_income = payload.monthly_income
        borrower.salary_date = (
            str(payload.income_day) if payload.income_day is not None else clean_optional(payload.salary_date)
        )
        try:
            save_assisted_external_debts(
                db,
                borrower=borrower,
                company_id=context.company_id,
                user_id=context.user.id,
                debts=payload.external_debts,
                legacy_total=payload.existing_loan_total,
                legacy_has_existing_loans=payload.has_existing_loans,
            )
            _save_assisted_banking_profile(
                db,
                borrower=borrower,
                company_id=context.company_id,
                bank_input=payload.bank_account,
            )
            return _create_company_borrower_account(
                db,
                borrower=borrower,
                branch_id=branch_id,
                context=context,
                source="existing_borrower_link",
                fee_config=fee_config,
            )
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="The borrower is already linked to this company.",
            ) from error

    if not payload.temporary_password:
        raise HTTPException(
            status_code=422,
            detail="A temporary password is required for a new borrower account.",
        )

    user_filters = [User.phone == phone]
    if email:
        user_filters.append(User.email == email)
    if db.query(User).filter(or_(*user_filters)).first():
        raise HTTPException(status_code=409, detail="Borrower phone or email already exists")

    person_filters = []
    if passport_number:
        person_filters.append(Person.passport_number == passport_number)
    if person_filters and db.query(Person).filter(or_(*person_filters)).first():
        raise HTTPException(status_code=409, detail="Borrower passport already exists")

    try:
        employer_group = resolve_employer_group(
            db,
            employer_group_id=payload.employer_group_id,
            new_employer_group=payload.new_employer_group,
        )
        user = User(
            email=email,
            phone=phone,
            password_hash=hash_password(payload.temporary_password),
            role=UserRole.BORROWER,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.flush()
        person = Person(
            user_id=user.id,
            first_name=payload.first_name.strip(),
            middle_name=clean_optional(payload.middle_name),
            last_name=payload.last_name.strip(),
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
            national_id=national_id,
            passport_number=passport_number,
            marital_status=payload.marital_status,
            nationality=clean_optional(payload.nationality) or "Mosotho",
            district=payload.district.strip(),
            town_or_village=clean_optional(payload.town_or_village),
            physical_address=clean_optional(payload.physical_address),
        )
        db.add(person)
        db.flush()
        borrower = Borrower(
            user_id=user.id,
            employment_status=payload.employment_status,
            employer_group_id=employer_group.id if employer_group is not None else None,
            employer_name=(
                employer_group.name if employer_group is not None else clean_optional(payload.employer_name)
            ),
            income_day=payload.income_day,
            job_title=clean_optional(payload.job_title),
            monthly_income=payload.monthly_income,
            salary_date=(
                str(payload.income_day) if payload.income_day is not None else clean_optional(payload.salary_date)
            ),
            has_existing_loans=payload.has_existing_loans,
            existing_loan_total=payload.existing_loan_total,
            consent_to_share_profile=payload.consent_to_share_profile,
            consent_to_credit_checks=payload.consent_to_credit_checks,
        )
        db.add(borrower)
        db.flush()
        save_assisted_external_debts(
            db,
            borrower=borrower,
            company_id=context.company_id,
            user_id=context.user.id,
            debts=payload.external_debts,
            legacy_total=payload.existing_loan_total,
            legacy_has_existing_loans=payload.has_existing_loans,
        )
        _save_assisted_banking_profile(
            db,
            borrower=borrower,
            company_id=context.company_id,
            bank_input=payload.bank_account,
        )
        return _create_company_borrower_account(
            db,
            borrower=borrower,
            branch_id=branch_id,
            context=context,
            source="assisted_registration",
            fee_config=fee_config,
        )
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Borrower account details already exist") from error

