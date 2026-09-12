from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import InstallmentStatus, LoanCalculationMethod, LoanStatus
from database.models.file_management import ManagedFile
from database.models.origination import (
    AffordabilityAssessment,
    BorrowerBankAccount,
    BorrowerDebtObligation,
    BorrowerDebtObligationEvent,
    BorrowerEmploymentProfile,
    BorrowerExpense,
    BorrowerIncomeSource,
    BorrowerKYCProfile,
    OriginationPolicy,
)
from database.models.person import Person
from database.models.professional_lending import CreditBlacklist, DirectLoanApplication
from database.models.repayment import RepaymentInstallment
from database.models.user import User
from database.schemas.origination import FinancialProfileUpdate, OriginationPolicyUpdate
from services.company_client_service import (
    normalized_monthly_debt_installment,
    sync_borrower_external_debt_summary,
)
from services.credential_service import encrypt_credential
from services.interest_calculation_service import calculate_loan_terms

MONEY = Decimal("0.01")
PERCENT = Decimal("0.001")

OPEN_APPLICATION_STATUSES = {"draft", "submitted", "under_review"}
ACTIVE_LOAN_STATUSES = {LoanStatus.APPROVED, LoanStatus.ACTIVE, LoanStatus.DEFAULTED}


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def percent(value) -> Decimal:
    return Decimal(value or 0).quantize(PERCENT, rounding=ROUND_HALF_UP)


def serialize(model) -> dict:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def json_safe(value):
    """Convert ORM/Python values into JSONB-safe primitives without losing audit detail."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (UUID, date, datetime)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "value"):
        return json_safe(value.value)
    return str(value)


def get_or_create_policy(db: Session, company_id: UUID, user_id: UUID | None = None) -> OriginationPolicy:
    policy = (
        db.query(OriginationPolicy)
        .filter(OriginationPolicy.company_id == company_id)
        .first()
    )
    if policy:
        return policy
    policy = OriginationPolicy(company_id=company_id, configured_by_user_id=user_id)
    db.add(policy)
    db.flush()
    return policy


def update_policy(
    db: Session,
    *,
    company_id: UUID,
    user_id: UUID,
    payload: OriginationPolicyUpdate,
) -> OriginationPolicy:
    policy = get_or_create_policy(db, company_id, user_id)
    for key, value in payload.model_dump().items():
        setattr(policy, key, value)
    policy.version = int(policy.version or 0) + 1
    policy.configured_by_user_id = user_id
    db.commit()
    db.refresh(policy)
    return policy


def borrower_identity(db: Session, borrower_id: UUID) -> dict:
    row = (
        db.query(Borrower, User, Person)
        .join(User, User.id == Borrower.user_id)
        .outerjoin(Person, Person.user_id == User.id)
        .filter(Borrower.id == borrower_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Borrower not found")
    borrower, user, person = row
    return {
        "borrower_id": borrower.id,
        "user_id": user.id,
        "full_name": person.full_name if person else "Registered borrower",
        "date_of_birth": person.date_of_birth if person else None,
        "national_id": person.national_id if person else None,
        "passport_number": person.passport_number if person else None,
        "phone": user.phone,
        "email": user.email,
    }


def age_on(date_of_birth: date | None, on_date: date | None = None) -> int | None:
    if not date_of_birth:
        return None
    today = on_date or date.today()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def duplicate_exposure(
    db: Session,
    *,
    borrower_id: UUID,
    exclude_application_id: UUID | None = None,
    exclude_loan_id: UUID | None = None,
) -> dict:
    app_query = db.query(DirectLoanApplication).filter(
        DirectLoanApplication.borrower_id == borrower_id,
        DirectLoanApplication.status.in_(OPEN_APPLICATION_STATUSES),
    )
    if exclude_application_id:
        app_query = app_query.filter(DirectLoanApplication.id != exclude_application_id)
    open_apps = app_query.order_by(DirectLoanApplication.created_at.desc()).all()

    loan_query = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.borrower_id == borrower_id,
        ClientCompanyLoan.status.in_(ACTIVE_LOAN_STATUSES),
    )
    if exclude_loan_id:
        loan_query = loan_query.filter(ClientCompanyLoan.id != exclude_loan_id)
    active_loans = loan_query.order_by(ClientCompanyLoan.created_at.desc()).all()

    return {
        "has_open_application": bool(open_apps),
        "has_active_loan": bool(active_loans),
        "open_applications": [
            {
                "id": item.id,
                "reference": item.application_reference,
                "company_id": item.company_id,
                "status": item.status,
                "requested_amount": item.requested_amount,
            }
            for item in open_apps
        ],
        "active_loans": [
            {
                "id": item.id,
                "reference": item.loan_reference,
                "company_id": item.company_id,
                "status": item.status.value if hasattr(item.status, "value") else str(item.status),
                "balance": item.balance,
            }
            for item in active_loans
        ],
    }


def top_up_eligibility(
    db: Session,
    *,
    borrower_id: UUID,
    company_id: UUID,
    policy: OriginationPolicy,
    loan_id: UUID | None = None,
) -> dict:
    query = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.borrower_id == borrower_id,
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
    )
    if loan_id:
        query = query.filter(ClientCompanyLoan.id == loan_id)
    loan = query.order_by(ClientCompanyLoan.created_at.desc()).first()
    if not loan:
        return {
            "eligible": False,
            "requires_owner_exception": False,
            "reason": "No active company loan is available for a top-up",
            "loan": None,
            "paid_percent": Decimal("0.000"),
            "paid_installments": 0,
            "required_paid_percent": percent(policy.top_up_min_paid_percent),
            "required_paid_installments": int(policy.top_up_min_paid_installments or 0),
        }

    total = money(loan.total_repayable)
    paid = money(loan.amount_paid)
    paid_percent = percent((paid / total * Decimal("100")) if total > 0 else Decimal("0"))
    paid_installments = (
        db.query(func.count(RepaymentInstallment.id))
        .filter(
            RepaymentInstallment.loan_id == loan.id,
            RepaymentInstallment.status == InstallmentStatus.PAID,
        )
        .scalar()
        or 0
    )
    required_percent = percent(policy.top_up_min_paid_percent)
    required_installments = int(policy.top_up_min_paid_installments or 0)
    positive_history = loan.status != LoanStatus.DEFAULTED and not bool(loan.is_overdue)
    threshold_passed = paid_percent >= required_percent and int(paid_installments) >= required_installments
    if policy.top_up_require_positive_history and not positive_history:
        threshold_passed = False
    allowed = bool(policy.allow_top_up and policy.top_up_settle_existing_balance)
    requires_exception = bool(allowed and not threshold_passed and policy.top_up_owner_exception_enabled)
    if not allowed:
        reason = (
            "Top-ups are disabled by company policy"
            if not policy.allow_top_up
            else "Top-up settlement is disabled by company policy"
        )
    elif threshold_passed:
        reason = "The existing loan meets the configured top-up rules"
    elif requires_exception:
        reason = "The normal top-up threshold is not met; company-owner exception approval is required"
    else:
        reason = "The normal top-up threshold is not met and owner exceptions are disabled"
    return {
        "eligible": bool(allowed and threshold_passed),
        "requires_owner_exception": requires_exception,
        "reason": reason,
        "paid_percent": paid_percent,
        "paid_installments": int(paid_installments),
        "required_paid_percent": required_percent,
        "required_paid_installments": required_installments,
        "positive_history": positive_history,
        "loan": {
            "id": loan.id,
            "reference": loan.loan_reference,
            "status": loan.status.value if hasattr(loan.status, "value") else str(loan.status),
            "principal_amount": money(loan.principal_amount),
            "total_repayable": total,
            "amount_paid": paid,
            "balance": money(loan.balance),
            "installment_amount": money(loan.installment_amount),
        },
    }


def enforce_duplicate_policy(
    db: Session,
    *,
    borrower_id: UUID,
    company_id: UUID,
    policy: OriginationPolicy,
    exclude_application_id: UUID | None = None,
    exclude_loan_id: UUID | None = None,
    application_type: str = "new_loan",
    parent_loan_id: UUID | None = None,
    top_up_exception_approved: bool = False,
) -> dict:
    borrower = db.query(Borrower).filter(Borrower.id == borrower_id).with_for_update().first()
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")

    exposure = duplicate_exposure(
        db,
        borrower_id=borrower_id,
        exclude_application_id=exclude_application_id,
        exclude_loan_id=exclude_loan_id,
    )
    if len(exposure["open_applications"]) >= int(policy.max_open_applications or 1):
        references = ", ".join(item["reference"] for item in exposure["open_applications"])
        raise HTTPException(status_code=409, detail=f"The borrower already has an open application: {references}")

    if application_type == "top_up":
        eligibility = top_up_eligibility(
            db,
            borrower_id=borrower_id,
            company_id=company_id,
            policy=policy,
            loan_id=parent_loan_id,
        )
        if not eligibility["loan"]:
            raise HTTPException(status_code=409, detail=eligibility["reason"])
        if not eligibility["eligible"] and not (eligibility["requires_owner_exception"] and top_up_exception_approved):
            raise HTTPException(status_code=409, detail=eligibility["reason"])
        parent_id = eligibility["loan"]["id"]
        other_loans = [item for item in exposure["active_loans"] if item["id"] != parent_id]
        if other_loans and not policy.allow_concurrent_active_loans:
            references = ", ".join(item["reference"] for item in other_loans)
            raise HTTPException(status_code=409, detail=f"The borrower has another active loan that is not part of this top-up: {references}")
        exposure["top_up_eligibility"] = eligibility
        return exposure

    if not policy.allow_concurrent_active_loans and exposure["active_loans"]:
        references = ", ".join(item["reference"] for item in exposure["active_loans"])
        raise HTTPException(status_code=409, detail=f"The borrower already has an active or approved loan: {references}")
    if policy.allow_concurrent_active_loans and len(exposure["active_loans"]) >= int(policy.max_active_loans or 1):
        raise HTTPException(status_code=409, detail="The borrower has reached the configured maximum number of active loans")
    return exposure


def _upsert(db: Session, model, filters: dict, values: dict):
    row = db.query(model).filter_by(**filters).first()
    if not row:
        row = model(**filters)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    db.flush()
    return row


def save_financial_profile(
    db: Session,
    *,
    company_id: UUID | None,
    borrower_id: UUID,
    user_id: UUID,
    payload: FinancialProfileUpdate,
    actor_role: str | None = None,
) -> dict:
    identity = borrower_identity(db, borrower_id)
    before_profile = financial_profile_payload(
        db,
        company_id=company_id,
        borrower_id=borrower_id,
        identity=identity,
    )

    kyc_values = payload.kyc.model_dump()
    document_ids = list(payload.kyc.document_file_ids)
    if document_ids:
        document_scope = [
            ManagedFile.id.in_(document_ids),
            ManagedFile.is_deleted.is_(False),
            ManagedFile.scan_status != "quarantined",
            or_(
                (
                    (ManagedFile.linked_entity_type == "borrower_evaluation")
                    & (ManagedFile.linked_entity_id == str(borrower_id))
                ),
                (
                    (ManagedFile.category == "kyc")
                    & (ManagedFile.company_id == company_id)
                )
                if company_id is not None
                else (
                    (ManagedFile.linked_entity_type == "borrower_evaluation")
                    & (ManagedFile.linked_entity_id == str(borrower_id))
                ),
            ),
        ]
        valid_documents = db.query(ManagedFile.id).filter(*document_scope).all()
        valid_ids = {row[0] for row in valid_documents}
        invalid_ids = [str(item) for item in document_ids if item not in valid_ids]
        if invalid_ids:
            raise HTTPException(
                status_code=422,
                detail="One or more assessment-document references are invalid for this borrower",
            )
    kyc_values["document_file_ids"] = [str(item) for item in document_ids]
    kyc_values["company_id"] = company_id
    if payload.kyc.status in {"verified", "failed", "enhanced_due_diligence"}:
        kyc_values["reviewed_by_user_id"] = user_id
        kyc_values["reviewed_at"] = datetime.now(timezone.utc)
    kyc = _upsert(
        db,
        BorrowerKYCProfile,
        {"borrower_id": borrower_id},
        kyc_values,
    )

    employment_values = payload.employment.model_dump()
    employment_values["company_id"] = company_id
    employment = _upsert(
        db,
        BorrowerEmploymentProfile,
        {"borrower_id": borrower_id},
        employment_values,
    )

    for model in (BorrowerIncomeSource, BorrowerExpense):
        db.query(model).filter(model.borrower_id == borrower_id).delete(
            synchronize_session=False
        )

    income_rows = []
    for item in payload.income_sources:
        row = BorrowerIncomeSource(
            company_id=company_id,
            borrower_id=borrower_id,
            **item.model_dump(),
        )
        db.add(row)
        income_rows.append(row)

    expense_rows = []
    for item in payload.expenses:
        row = BorrowerExpense(
            company_id=company_id,
            borrower_id=borrower_id,
            **item.model_dump(),
        )
        db.add(row)
        expense_rows.append(row)

    debt_rows = []
    submitted_debt_ids: set[UUID] = set()
    for item in payload.debts:
        values = item.model_dump(exclude={"id"})
        installment_amount = Decimal(
            values.get("installment_amount")
            or values.get("monthly_installment")
            or 0
        )
        frequency = str(values.get("installment_frequency") or "monthly")
        values["installment_amount"] = installment_amount
        values["monthly_installment"] = normalized_monthly_debt_installment(
            installment_amount,
            frequency,
        )
        values["remaining_term_months"] = (
            values.get("remaining_installments")
            if frequency == "monthly"
            else values.get("remaining_term_months")
        )
        if values.get("current_balance", 0) <= 0:
            values["current_balance"] = Decimal("0")
            values["status"] = "settled"
            values["remaining_installments"] = 0
            values["remaining_term_months"] = 0

        row = None
        if item.id is not None:
            row = (
                db.query(BorrowerDebtObligation)
                .filter(
                    BorrowerDebtObligation.id == item.id,
                    BorrowerDebtObligation.borrower_id == borrower_id,
                )
                .first()
            )
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail="One of the tracked external loans was not found",
                )
        old_balance = Decimal(row.current_balance or 0) if row is not None else None
        if row is None:
            row = BorrowerDebtObligation(
                company_id=company_id,
                borrower_id=borrower_id,
            )
            db.add(row)
        elif company_id is not None:
            row.company_id = company_id
        for key, value in values.items():
            setattr(row, key, value)
        row.last_reviewed_at = datetime.now(timezone.utc)
        row.last_reviewed_by_user_id = user_id
        db.flush()
        submitted_debt_ids.add(row.id)
        db.add(
            BorrowerDebtObligationEvent(
                company_id=company_id,
                borrower_id=borrower_id,
                obligation_id=row.id,
                recorded_by_user_id=user_id,
                event_type="created" if old_balance is None else "reviewed",
                event_at=datetime.now(timezone.utc),
                amount=(
                    abs(old_balance - Decimal(row.current_balance or 0))
                    if old_balance is not None
                    and old_balance != Decimal(row.current_balance or 0)
                    else None
                ),
                balance_after=Decimal(row.current_balance or 0),
                remaining_installments_after=row.remaining_installments,
                notes="External loan schedule saved from the shared borrower assessment.",
            )
        )
        debt_rows.append(row)

    borrower = db.get(Borrower, borrower_id)
    if borrower is not None:
        sync_borrower_external_debt_summary(
            db,
            borrower=borrower,
            company_id=company_id,
        )

    existing_banks = (
        db.query(BorrowerBankAccount)
        .filter(BorrowerBankAccount.borrower_id == borrower_id)
        .all()
    )
    existing_by_id = {row.id: row for row in existing_banks}
    submitted_bank_ids: set[UUID] = set()

    for bank_input in payload.bank_accounts:
        existing_bank = existing_by_id.get(bank_input.id) if bank_input.id else None
        if bank_input.id is not None and existing_bank is None:
            raise HTTPException(
                status_code=404,
                detail="One of the borrower bank accounts was not found",
            )
        if not bank_input.account_number and not existing_bank:
            raise HTTPException(
                status_code=422,
                detail="A bank account number is required when a banking profile is first created",
            )
        encrypted = (
            encrypt_credential(bank_input.account_number)
            if bank_input.account_number
            else existing_bank.account_number_encrypted
        )
        last4 = (
            bank_input.account_number[-4:]
            if bank_input.account_number
            else existing_bank.account_number_last4
        )
        token = (
            encrypt_credential(bank_input.tokenized_card_reference)
            if bank_input.tokenized_card_reference
            else (
                existing_bank.tokenized_card_reference_encrypted
                if existing_bank
                else None
            )
        )
        bank_values = bank_input.model_dump(
            exclude={"id", "account_number", "tokenized_card_reference"}
        )
        bank_values.update(
            {
                "account_number_encrypted": encrypted,
                "account_number_last4": last4,
                "tokenized_card_reference_encrypted": token,
                "verified_at": (
                    datetime.now(timezone.utc)
                    if bank_input.verification_status == "verified"
                    else None
                ),
            }
        )
        bank = existing_bank or BorrowerBankAccount(
            company_id=company_id,
            borrower_id=borrower_id,
        )
        if existing_bank is None:
            db.add(bank)
        elif company_id is not None:
            bank.company_id = company_id
        for key, value in bank_values.items():
            setattr(bank, key, value)
        db.flush()
        submitted_bank_ids.add(bank.id)

    for bank in existing_banks:
        if bank.id not in submitted_bank_ids:
            db.delete(bank)

    db.flush()
    after_profile = financial_profile_payload(
        db,
        company_id=company_id,
        borrower_id=borrower_id,
        identity=identity,
    )
    sections = (
        "kyc",
        "employment",
        "income_sources",
        "expenses",
        "debts",
        "bank_accounts",
    )
    changed_fields = [
        section
        for section in sections
        if before_profile.get(section) != after_profile.get(section)
    ]
    if changed_fields:
        db.add(
            AuditLog(
                user_id=user_id,
                company_id=company_id,
                action="borrower.assessment_updated",
                table_name="borrowers",
                entity_type="borrower_financial_profile",
                record_id=borrower_id,
                description="The shared borrower assessment was updated.",
                actor_role=actor_role,
                severity="info",
                status="success",
                before_data=json_safe(
                    {key: before_profile.get(key) for key in changed_fields}
                ),
                after_data=json_safe(
                    {key: after_profile.get(key) for key in changed_fields}
                ),
                changed_fields=changed_fields,
                event_data={"borrower_id": str(borrower_id)},
            )
        )
    db.commit()
    return financial_profile_payload(
        db,
        company_id=company_id,
        borrower_id=borrower_id,
        identity=identity,
    )


def financial_profile_payload(
    db: Session,
    *,
    company_id: UUID | None,
    borrower_id: UUID,
    identity: dict | None = None,
) -> dict:
    del company_id
    identity = identity or borrower_identity(db, borrower_id)
    kyc = (
        db.query(BorrowerKYCProfile)
        .filter(BorrowerKYCProfile.borrower_id == borrower_id)
        .first()
    )
    employment = (
        db.query(BorrowerEmploymentProfile)
        .filter(BorrowerEmploymentProfile.borrower_id == borrower_id)
        .first()
    )
    incomes = (
        db.query(BorrowerIncomeSource)
        .filter(BorrowerIncomeSource.borrower_id == borrower_id)
        .order_by(BorrowerIncomeSource.created_at)
        .all()
    )
    expenses = (
        db.query(BorrowerExpense)
        .filter(BorrowerExpense.borrower_id == borrower_id)
        .order_by(BorrowerExpense.created_at)
        .all()
    )
    debts = (
        db.query(BorrowerDebtObligation)
        .filter(BorrowerDebtObligation.borrower_id == borrower_id)
        .order_by(BorrowerDebtObligation.created_at)
        .all()
    )
    banks = (
        db.query(BorrowerBankAccount)
        .filter(BorrowerBankAccount.borrower_id == borrower_id)
        .order_by(
            BorrowerBankAccount.salary_account.desc(),
            BorrowerBankAccount.created_at,
        )
        .all()
    )

    bank_payloads = []
    for bank in banks:
        bank_payload = serialize(bank)
        bank_payload.pop("account_number_encrypted", None)
        bank_payload.pop("tokenized_card_reference_encrypted", None)
        bank_payload["masked_account_number"] = (
            f"****{bank.account_number_last4}"
            if bank.account_number_last4
            else None
        )
        bank_payload["has_tokenized_card"] = bool(
            bank.tokenized_card_reference_encrypted
        )
        bank_payloads.append(bank_payload)

    return {
        "identity": identity,
        "kyc": serialize(kyc) if kyc else None,
        "employment": serialize(employment) if employment else None,
        "income_sources": [serialize(item) for item in incomes],
        "expenses": [serialize(item) for item in expenses],
        "debts": [serialize(item) for item in debts],
        "bank_accounts": bank_payloads,
        "bank_account": bank_payloads[0] if bank_payloads else None,
    }


def profile_totals(
    db: Session,
    *,
    company_id: UUID | None,
    borrower_id: UUID,
) -> dict:
    del company_id
    employment = (
        db.query(BorrowerEmploymentProfile)
        .filter(BorrowerEmploymentProfile.borrower_id == borrower_id)
        .first()
    )
    verified_additional = (
        db.query(func.coalesce(func.sum(BorrowerIncomeSource.verified_amount), 0))
        .filter(
            BorrowerIncomeSource.borrower_id == borrower_id,
            BorrowerIncomeSource.is_verified.is_(True),
        )
        .scalar()
    )
    expenses = (
        db.query(func.coalesce(func.sum(BorrowerExpense.monthly_amount), 0))
        .filter(BorrowerExpense.borrower_id == borrower_id)
        .scalar()
    )
    debts = (
        db.query(func.coalesce(func.sum(BorrowerDebtObligation.monthly_installment), 0))
        .filter(
            BorrowerDebtObligation.borrower_id == borrower_id,
            BorrowerDebtObligation.status.in_(
                ("active", "defaulted", "restructured", "unknown")
            ),
            BorrowerDebtObligation.current_balance > 0,
        )
        .scalar()
    )
    verified_salary = money(
        employment.verified_net_income if employment else 0
    )
    return {
        "verified_salary": verified_salary,
        "verified_additional_income": money(verified_additional),
        "verified_income": money(verified_salary + money(verified_additional)),
        "household_expenses": money(expenses),
        "existing_debt_installments": money(debts),
    }


def calculate_affordability(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
    application: DirectLoanApplication,
    principal: Decimal,
    rate_percent: Decimal,
    months: int,
    processing_fee: Decimal,
    interest_method: LoanCalculationMethod | str,
    calculated_by_user_id: UUID,
) -> AffordabilityAssessment:
    policy = get_or_create_policy(db, company_id, calculated_by_user_id)
    profile = financial_profile_payload(db, company_id=company_id, borrower_id=borrower_id)
    totals = profile_totals(db, company_id=company_id, borrower_id=borrower_id)
    identity = profile["identity"]
    kyc = profile["kyc"]
    employment = profile["employment"]

    raw_due_dates = list(application.installment_due_dates or [])
    if len(raw_due_dates) != months:
        raise HTTPException(
            status_code=422,
            detail=f"Enter exactly {months} installment due dates before calculating affordability",
        )
    due_dates = [date.fromisoformat(str(value)) for value in raw_due_dates]
    try:
        monthly, total_repayable, calculation = calculate_loan_terms(
            principal=principal,
            rate_percent=rate_percent,
            term_months=months,
            processing_fee=processing_fee,
            interest_method=interest_method,
            due_dates=due_dates,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    verified_income = money(totals["verified_income"])
    household_expenses = money(totals["household_expenses"])
    debt_installments = money(totals["existing_debt_installments"])
    dependants = int((kyc or {}).get("dependants") or 0)
    dependant_total = money(Decimal(dependants) * Decimal(policy.dependant_allowance or 0))
    buffer_amount = money(policy.living_expense_buffer)
    committed = money(household_expenses + debt_installments + dependant_total + buffer_amount)
    disposable = money(verified_income - committed)

    disposable_limit = money(max(disposable, Decimal("0")) * Decimal(policy.disposable_income_usage_percent or 0) / Decimal("100"))
    dti_limit = money(max(verified_income * Decimal(policy.max_dti_percent or 0) / Decimal("100") - debt_installments, Decimal("0")))
    installment_income_limit = money(verified_income * Decimal(policy.max_installment_income_percent or 0) / Decimal("100"))
    max_installment = money(min(disposable_limit, dti_limit, installment_income_limit))
    headroom = money(max_installment - monthly)
    dti = percent((debt_installments + monthly) * Decimal("100") / verified_income) if verified_income > 0 else Decimal("100")

    reasons: list[dict[str, str]] = []
    blocking = False
    referral = False

    applicant_age = age_on(identity.get("date_of_birth"))
    if applicant_age is None:
        blocking = True
        reasons.append({"severity": "error", "code": "age_missing", "message": "Applicant date of birth is required."})
    elif applicant_age < policy.min_age or applicant_age > policy.max_age:
        blocking = True
        reasons.append({"severity": "error", "code": "age_outside_policy", "message": f"Applicant age {applicant_age} is outside the configured {policy.min_age}–{policy.max_age} range."})
    else:
        reasons.append({"severity": "pass", "code": "age_ok", "message": "Applicant age is within policy."})

    if verified_income < money(policy.min_verified_net_income):
        blocking = True
        reasons.append({"severity": "error", "code": "income_below_minimum", "message": "Verified income is below the configured minimum."})
    else:
        reasons.append({"severity": "pass", "code": "income_ok", "message": "Verified income meets the minimum."})

    if policy.require_kyc_verified and (not kyc or kyc.get("status") != "verified"):
        blocking = True
        reasons.append({"severity": "error", "code": "kyc_incomplete", "message": "KYC must be verified before approval."})
    elif kyc:
        reasons.append({"severity": "pass", "code": "kyc_ok", "message": "KYC is verified."})

    if kyc and any(kyc.get(flag) for flag in ("sanctions_hit", "fraud_flag")):
        blocking = True
        reasons.append({"severity": "error", "code": "compliance_block", "message": "A sanctions or fraud flag requires compliance resolution."})
    if kyc and (kyc.get("politically_exposed") or kyc.get("adverse_media_hit")):
        referral = True
        reasons.append({"severity": "warning", "code": "enhanced_due_diligence", "message": "Enhanced due diligence is required."})

    blacklist = db.query(CreditBlacklist).filter(CreditBlacklist.borrower_id == borrower_id, CreditBlacklist.is_active.is_(True)).first()
    if blacklist and not policy.allow_blacklisted:
        blocking = True
        reasons.append({"severity": "error", "code": "blacklisted", "message": f"Applicant is blacklisted: {blacklist.reason}"})

    if employment:
        if employment.get("payslip_count", 0) < policy.required_payslips:
            referral = True
            reasons.append({"severity": "warning", "code": "payslips_missing", "message": "Required payslip count has not been met."})
        if employment.get("bank_statement_months", 0) < policy.required_bank_statement_months:
            referral = True
            reasons.append({"severity": "warning", "code": "bank_statements_missing", "message": "Required bank statement history has not been met."})

    if monthly > max_installment or disposable - monthly < money(policy.min_disposable_after_installment):
        blocking = True
        reasons.append({"severity": "error", "code": "not_affordable", "message": "The proposed instalment exceeds the calculated affordability limit."})
    else:
        reasons.append({"severity": "pass", "code": "affordable", "message": "The proposed instalment is within the affordability limit."})

    if blocking:
        decision = "not_affordable"
    elif referral:
        decision = "refer"
    else:
        decision = "eligible"

    assessment_number = (
        db.query(func.coalesce(func.max(AffordabilityAssessment.assessment_number), 0))
        .filter(AffordabilityAssessment.application_id == application.id)
        .scalar()
    ) + 1

    assessment = AffordabilityAssessment(
        company_id=company_id,
        borrower_id=borrower_id,
        application_id=application.id,
        policy_id=policy.id,
        policy_version=policy.version,
        assessment_number=assessment_number,
        decision=decision,
        verified_income=verified_income,
        household_expenses=household_expenses,
        existing_debt_installments=debt_installments,
        configured_buffer=buffer_amount,
        dependant_allowance_total=dependant_total,
        disposable_income=disposable,
        dti_percent=dti,
        disposable_income_limit=disposable_limit,
        dti_limit=dti_limit,
        installment_income_limit=installment_income_limit,
        maximum_affordable_installment=max_installment,
        proposed_installment=monthly,
        affordability_headroom=headroom,
        input_snapshot=json_safe({
            "identity": identity,
            "kyc": kyc,
            "employment": employment,
            "totals": totals,
            "policy": serialize(policy),
            "proposal": {
                "principal": principal,
                "rate_percent": rate_percent,
                "months": months,
                "processing_fee": processing_fee,
                "total_repayable": total_repayable,
                "monthly_installment": monthly,
                "calculation": calculation,
            },
        }),
        result_reasons=reasons,
        calculated_by_user_id=calculated_by_user_id,
    )
    db.add(assessment)
    db.flush()
    application.affordability_assessment_id = assessment.id
    if kyc and kyc.get("id"):
        application.kyc_profile_id = UUID(str(kyc["id"]))
    application.affordability_snapshot = {
        "assessment_id": str(assessment.id),
        "decision": decision,
        "verified_income": str(verified_income),
        "household_expenses": str(household_expenses),
        "existing_debt_installments": str(debt_installments),
        "maximum_affordable_installment": str(max_installment),
        "proposed_installment": str(monthly),
        "headroom": str(headroom),
        "policy_version": policy.version,
    }
    db.commit()
    db.refresh(assessment)
    return assessment



def assessment_effective_decision(assessment: AffordabilityAssessment | None) -> str | None:
    if not assessment:
        return None
    return assessment.override_decision if assessment.overridden else assessment.decision
