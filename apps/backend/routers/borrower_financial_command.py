from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, ROUND_CEILING
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload

from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_current_active_user,
    get_user_context,
    require_tenant_roles,
)
from database.models.borrower import Borrower
from database.models.borrower_service_request import BorrowerServiceRequest
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import (
    CompanyStatus,
    InstallmentStatus,
    LoanRequestStatus,
    LoanStatus,
    NotificationType,
    PaymentStatus,
    UnlockStatus,
    UserRole,
)
from database.models.loan_offer import LoanOffer
from database.models.loan_product import LoanProduct
from database.models.loan_request import LoanRequest
from database.models.marketplace_access import MarketplaceUnlock
from database.models.notification import Notification
from database.models.origination import (
    AffordabilityAssessment,
    BorrowerBankAccount,
    BorrowerDebtObligation,
    BorrowerEmploymentProfile,
    BorrowerExpense,
    BorrowerIncomeSource,
    BorrowerKYCProfile,
    OriginationPolicy,
)
from database.models.payment import PaymentTransaction
from database.models.repayment import RepaymentInstallment
from database.models.user import RefreshToken, User
from database.schemas.borrower_command import (
    BORROWER_SERVICE_REQUEST_STATUSES,
    BorrowerConsentUpdate,
    BorrowerServiceRequestCompanyUpdate,
    BorrowerServiceRequestCreate,
)
from database.session import get_db
from services.interest_calculation_service import calculate_loan_terms, generate_monthly_due_dates


router = APIRouter(prefix="/borrower-command", tags=["Borrower Financial Command Centre"])

SERVICE_REVIEW_ROLES = (
    LENDING_ROLES
    | COLLECTIONS_ROLES
    | COMPANY_MANAGEMENT_ROLES
    | {UserRole.CUSTOMER_SUPPORT, UserRole.COMPLIANCE_OFFICER}
)
LOAN_REQUIRED_REQUEST_TYPES = {
    "settlement_quote",
    "payment_arrangement",
    "change_payment_date",
    "top_up",
    "early_repayment",
    "payment_allocation_dispute",
    "balance_dispute",
    "hardship",
    "paid_up_letter",
    "statement",
    "update_payment_account",
}
REQUEST_LABELS = {
    "settlement_quote": "Settlement quotation",
    "payment_arrangement": "Payment arrangement",
    "change_payment_date": "Change repayment date",
    "top_up": "Loan top-up",
    "refinance": "Refinance request",
    "consolidation": "Debt consolidation",
    "early_repayment": "Early repayment",
    "payment_allocation_dispute": "Payment allocation dispute",
    "balance_dispute": "Balance dispute",
    "hardship": "Financial hardship assistance",
    "paid_up_letter": "Paid-up letter",
    "statement": "Loan statement",
    "update_payment_account": "Update payment account",
}
OPEN_SERVICE_STATUSES = {"submitted", "under_review", "approved"}
ACTIVE_DEBT_LOAN_STATUSES = {LoanStatus.APPROVED, LoanStatus.ACTIVE, LoanStatus.DEFAULTED}
OPEN_INSTALLMENT_STATUSES = {
    InstallmentStatus.PENDING,
    InstallmentStatus.PARTIALLY_PAID,
    InstallmentStatus.OVERDUE,
}


def _num(value: Any) -> float:
    return float(Decimal(str(value or 0)))


def _enum(value: Any) -> str:
    return str(getattr(value, "value", value or ""))


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


def _at(value: date | datetime | None) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.min


def _monthly_amount(amount: Any, frequency: str | None) -> Decimal:
    value = Decimal(str(amount or 0))
    normalized = (frequency or "monthly").strip().lower()
    if normalized in {"weekly", "week"}:
        return value * Decimal("52") / Decimal("12")
    if normalized in {"fortnightly", "biweekly", "two_weekly"}:
        return value * Decimal("26") / Decimal("12")
    if normalized in {"daily", "day"}:
        return value * Decimal("365") / Decimal("12")
    if normalized in {"annual", "annually", "yearly", "year"}:
        return value / Decimal("12")
    if normalized in {"quarterly", "quarter"}:
        return value / Decimal("3")
    return value


def _require_borrower(user: User) -> Borrower:
    if user.role != UserRole.BORROWER or not user.borrower_profile:
        raise HTTPException(status_code=403, detail="This feature is available to borrower accounts")
    return user.borrower_profile


def _dedupe_latest(rows: list[Any], key_builder) -> list[Any]:
    selected: dict[tuple[Any, ...], Any] = {}
    for row in rows:
        key = key_builder(row)
        current = selected.get(key)
        if current is None or _at(getattr(row, "updated_at", None)) > _at(getattr(current, "updated_at", None)):
            selected[key] = row
    return list(selected.values())


def _debt_rows(db: Session, borrower_id: UUID) -> list[BorrowerDebtObligation]:
    rows = (
        db.query(BorrowerDebtObligation)
        .filter(
            BorrowerDebtObligation.borrower_id == borrower_id,
            BorrowerDebtObligation.status.in_(["active", "open", "current"]),
        )
        .order_by(BorrowerDebtObligation.updated_at.desc())
        .all()
    )
    return _dedupe_latest(
        rows,
        lambda row: (
            (row.creditor or "").strip().lower(),
            (row.account_reference or "").strip().lower()
            or f"{row.debt_type}:{row.original_amount}:{row.started_on}",
        ),
    )


def _expense_rows(db: Session, borrower_id: UUID) -> list[BorrowerExpense]:
    rows = (
        db.query(BorrowerExpense)
        .filter(BorrowerExpense.borrower_id == borrower_id)
        .order_by(BorrowerExpense.updated_at.desc())
        .all()
    )
    return _dedupe_latest(
        rows,
        lambda row: ((row.category or "other").strip().lower(), (row.description or "").strip().lower()),
    )


def _income_rows(db: Session, borrower_id: UUID) -> list[BorrowerIncomeSource]:
    rows = (
        db.query(BorrowerIncomeSource)
        .filter(BorrowerIncomeSource.borrower_id == borrower_id)
        .order_by(BorrowerIncomeSource.updated_at.desc())
        .all()
    )
    return _dedupe_latest(
        rows,
        lambda row: ((row.source_type or "other").strip().lower(), (row.description or "").strip().lower()),
    )


def _employment_rows(db: Session, borrower_id: UUID) -> list[BorrowerEmploymentProfile]:
    return (
        db.query(BorrowerEmploymentProfile)
        .filter(BorrowerEmploymentProfile.borrower_id == borrower_id)
        .order_by(BorrowerEmploymentProfile.updated_at.desc())
        .all()
    )


def _kyc_rows(db: Session, borrower_id: UUID) -> list[BorrowerKYCProfile]:
    return (
        db.query(BorrowerKYCProfile)
        .filter(BorrowerKYCProfile.borrower_id == borrower_id)
        .order_by(BorrowerKYCProfile.updated_at.desc())
        .all()
    )


def _borrower_loans(db: Session, borrower_id: UUID) -> list[ClientCompanyLoan]:
    return (
        db.query(ClientCompanyLoan)
        .options(joinedload(ClientCompanyLoan.company), selectinload(ClientCompanyLoan.installments))
        .filter(ClientCompanyLoan.borrower_id == borrower_id)
        .order_by(ClientCompanyLoan.created_at.desc())
        .all()
    )


def _verified_income(
    borrower: Borrower,
    employment_rows: list[BorrowerEmploymentProfile],
    income_rows: list[BorrowerIncomeSource],
) -> tuple[Decimal, Decimal, bool]:
    verified_employment = max(
        (Decimal(str(row.verified_net_income or 0)) for row in employment_rows),
        default=Decimal("0"),
    )
    employment_fallback = max(
        (Decimal(str(row.net_salary or row.gross_salary or 0)) for row in employment_rows),
        default=Decimal("0"),
    )
    base_income = verified_employment or employment_fallback or Decimal(str(borrower.monthly_income or 0))
    salary_types = {"salary", "employment", "wages", "payroll", "primary_salary"}
    additional = Decimal("0")
    any_verified_source = verified_employment > 0
    for row in income_rows:
        source_type = (row.source_type or "").strip().lower()
        if source_type in salary_types and base_income > 0:
            continue
        amount = row.verified_amount if row.is_verified and row.verified_amount is not None else row.declared_amount
        if row.is_verified:
            any_verified_source = True
        additional += _monthly_amount(amount, row.frequency)
    return base_income + additional, additional, any_verified_source


def financial_snapshot(db: Session, borrower: Borrower) -> dict[str, Any]:
    employment_rows = _employment_rows(db, borrower.id)
    incomes = _income_rows(db, borrower.id)
    expenses = _expense_rows(db, borrower.id)
    debts = _debt_rows(db, borrower.id)
    loans = _borrower_loans(db, borrower.id)
    income, additional_income, income_verified = _verified_income(borrower, employment_rows, incomes)
    living_expenses = sum((Decimal(str(row.monthly_amount or 0)) for row in expenses), Decimal("0"))
    active_loans = [loan for loan in loans if loan.status in ACTIVE_DEBT_LOAN_STATUSES]
    internal_balance = sum((Decimal(str(loan.balance or 0)) for loan in active_loans), Decimal("0"))
    internal_commitments = sum((Decimal(str(loan.installment_amount or 0)) for loan in active_loans), Decimal("0"))
    external_balance = sum((Decimal(str(row.current_balance or 0)) for row in debts), Decimal("0"))
    external_commitments = sum((Decimal(str(row.monthly_installment or 0)) for row in debts), Decimal("0"))
    total_commitments = internal_commitments + external_commitments
    total_debt = internal_balance + external_balance
    dti = total_commitments / income * Decimal("100") if income > 0 else Decimal("0")
    disposable = income - living_expenses - total_commitments
    assessment = (
        db.query(AffordabilityAssessment)
        .filter(AffordabilityAssessment.borrower_id == borrower.id)
        .order_by(AffordabilityAssessment.created_at.desc())
        .first()
    )
    generic_limit = max(Decimal("0"), income * Decimal("0.35") - total_commitments)
    maximum_affordable = (
        Decimal(str(assessment.maximum_affordable_installment or 0))
        if assessment and assessment.maximum_affordable_installment
        else generic_limit
    )
    next_due = (
        db.query(RepaymentInstallment)
        .join(ClientCompanyLoan, RepaymentInstallment.loan_id == ClientCompanyLoan.id)
        .options(joinedload(RepaymentInstallment.loan).joinedload(ClientCompanyLoan.company))
        .filter(
            ClientCompanyLoan.borrower_id == borrower.id,
            RepaymentInstallment.is_superseded.is_(False),
            RepaymentInstallment.status.in_(list(OPEN_INSTALLMENT_STATUSES)),
        )
        .order_by(RepaymentInstallment.due_date.asc())
        .first()
    )
    return {
        "income": income,
        "additional_income": additional_income,
        "income_verified": income_verified,
        "living_expenses": living_expenses,
        "internal_balance": internal_balance,
        "internal_commitments": internal_commitments,
        "external_balance": external_balance,
        "external_commitments": external_commitments,
        "total_commitments": total_commitments,
        "total_debt": total_debt,
        "dti": dti,
        "disposable": disposable,
        "maximum_affordable": maximum_affordable,
        "assessment": assessment,
        "debts": debts,
        "expenses": expenses,
        "income_rows": incomes,
        "employment_rows": employment_rows,
        "loans": loans,
        "active_loans": active_loans,
        "next_due": next_due,
    }


def readiness_score(db: Session, borrower: Borrower, snapshot: dict[str, Any]) -> dict[str, Any]:
    person = borrower.user.person if borrower.user else None
    kycs = _kyc_rows(db, borrower.id)
    identity_verified = any(row.identity_verified for row in kycs)
    employment_verified = any(
        (row.verification_status or "").strip().lower() in {"verified", "approved", "complete"}
        or Decimal(str(row.verified_net_income or 0)) > 0
        for row in snapshot["employment_rows"]
    )
    components: list[dict[str, Any]] = []
    identity_points = (7 if person and (person.national_id or person.passport_number) else 0) + (8 if identity_verified else 0)
    components.append({"key": "identity", "label": "Identity readiness", "score": identity_points, "max": 15})
    consent_points = (7 if borrower.consent_to_share_profile else 0) + (8 if borrower.consent_to_credit_checks else 0)
    components.append({"key": "consent", "label": "Consent readiness", "score": consent_points, "max": 15})
    income_points = (10 if snapshot["income"] > 0 else 0) + (10 if employment_verified or snapshot["income_verified"] else 0)
    components.append({"key": "income", "label": "Income evidence", "score": income_points, "max": 20})
    affordability_points = 0
    if snapshot["income"] > 0:
        if snapshot["dti"] <= Decimal("35"):
            affordability_points += 12
        elif snapshot["dti"] <= Decimal("45"):
            affordability_points += 9
        elif snapshot["dti"] <= Decimal("60"):
            affordability_points += 5
    affordability_points += 8 if snapshot["disposable"] > 0 else 0
    affordability_points += 5 if snapshot["maximum_affordable"] > 0 else 0
    components.append({"key": "affordability", "label": "Affordability", "score": affordability_points, "max": 25})
    succeeded_payments = (
        db.query(PaymentTransaction.id)
        .filter(PaymentTransaction.borrower_id == borrower.id, PaymentTransaction.status == PaymentStatus.SUCCEEDED)
        .count()
    )
    has_overdue = any(bool(loan.is_overdue) for loan in snapshot["active_loans"])
    has_default = any(loan.status == LoanStatus.DEFAULTED for loan in snapshot["loans"])
    if snapshot["loans"]:
        payment_points = (10 if succeeded_payments > 0 else 4) + (10 if not has_overdue else 0) + (5 if not has_default else 0)
    else:
        payment_points = 15
    components.append({"key": "repayment", "label": "Repayment evidence", "score": payment_points, "max": 25})
    score = min(100, sum(int(item["score"]) for item in components))
    band = "Strong" if score >= 85 else "Good" if score >= 70 else "Developing" if score >= 55 else "Action needed"
    helping: list[str] = []
    reducing: list[str] = []
    actions: list[str] = []
    if identity_verified:
        helping.append("Identity has been verified by at least one lender workflow.")
    else:
        reducing.append("Verified identity evidence is incomplete.")
        actions.append("Complete identity and KYC verification when requested by a lender.")
    if employment_verified or snapshot["income_verified"]:
        helping.append("Verified income evidence is available.")
    else:
        reducing.append("Income has not yet been fully verified.")
        actions.append("Keep payslips, employment information and bank statements current.")
    if not borrower.consent_to_share_profile or not borrower.consent_to_credit_checks:
        reducing.append("One or more lending consents are disabled.")
        actions.append("Review profile-sharing and credit-check consents before applying.")
    if has_overdue:
        reducing.append("At least one LoanHub loan is currently marked overdue.")
        actions.append("Bring overdue installments up to date or request a payment arrangement.")
    elif snapshot["loans"]:
        helping.append("No current LoanHub loan is marked overdue.")
    if snapshot["disposable"] > 0:
        helping.append("Recorded income exceeds recorded living expenses and debt commitments.")
    else:
        reducing.append("Recorded monthly commitments leave little or no disposable income.")
        actions.append("Review declared expenses and existing debt before taking additional credit.")
    evidence_count = sum([
        bool(person and (person.national_id or person.passport_number)),
        identity_verified,
        snapshot["income_verified"],
        bool(snapshot["debts"]),
        bool(snapshot["loans"]),
        succeeded_payments > 0,
    ])
    confidence = "high" if evidence_count >= 5 else "medium" if evidence_count >= 3 else "low"
    return {
        "score": score,
        "band": band,
        "confidence": confidence,
        "components": components,
        "helping": helping,
        "reducing": reducing,
        "actions": actions,
        "is_credit_bureau_score": False,
        "disclaimer": "LoanHub readiness is an explainable guidance score, not a credit-bureau score or a lender approval decision.",
    }


def _service_payload(row: BorrowerServiceRequest, include_borrower: bool = False) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "borrower_id": row.borrower_id,
        "company_id": row.company_id,
        "company_name": row.company.name if row.company else "Lender",
        "loan_id": row.loan_id,
        "loan_reference": row.loan.loan_reference if row.loan else None,
        "request_type": row.request_type,
        "request_type_label": REQUEST_LABELS.get(row.request_type, row.request_type.replace("_", " ").title()),
        "status": row.status,
        "subject": row.subject,
        "details": row.details,
        "requested_value": _num(row.requested_value) if row.requested_value is not None else None,
        "company_response": row.company_response,
        "responded_at": _iso(row.responded_at),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }
    if include_borrower:
        person = row.borrower.user.person if row.borrower and row.borrower.user else None
        payload["borrower_name"] = person.full_name if person else "Borrower"
    return payload


def _notify_company_reviewers(db: Session, row: BorrowerServiceRequest, actor_user_id: UUID) -> None:
    staff_rows = (
        db.query(CompanyStaff)
        .filter(
            CompanyStaff.company_id == row.company_id,
            CompanyStaff.is_active.is_(True),
            CompanyStaff.role.in_(list(SERVICE_REVIEW_ROLES)),
        )
        .all()
    )
    sent: set[UUID] = set()
    for staff in staff_rows:
        if staff.user_id in sent:
            continue
        sent.add(staff.user_id)
        db.add(Notification(
            user_id=staff.user_id,
            actor_user_id=actor_user_id,
            company_id=row.company_id,
            title=f"Borrower request: {REQUEST_LABELS.get(row.request_type, row.request_type)}",
            message="A borrower submitted a service request that needs lender review.",
            notification_type=NotificationType.SYSTEM,
            event_type="borrower.service_request.submitted",
            action="review",
            entity_type="borrower_service_request",
            entity_id=str(row.id),
            action_url="/company/borrower-requests",
            priority="high",
            deduplication_key=f"borrower-service-request:{row.id}:submitted:{staff.user_id}",
            data={"request_type": row.request_type, "loan_id": str(row.loan_id) if row.loan_id else None},
        ))


def _notify_borrower_response(db: Session, row: BorrowerServiceRequest, actor_user_id: UUID) -> None:
    if not row.borrower or not row.borrower.user_id:
        return
    db.add(Notification(
        user_id=row.borrower.user_id,
        actor_user_id=actor_user_id,
        company_id=row.company_id,
        title=f"{REQUEST_LABELS.get(row.request_type, 'Borrower request')} updated",
        message=f"Your lender changed this request to {row.status.replace('_', ' ')}.",
        notification_type=NotificationType.SYSTEM,
        event_type="borrower.service_request.updated",
        action="view",
        entity_type="borrower_service_request",
        entity_id=str(row.id),
        action_url="/borrower/financial-centre?tab=requests",
        priority="high",
        deduplication_key=f"borrower-service-request:{row.id}:{row.status}",
        data={"request_type": row.request_type, "status": row.status},
    ))


@router.get("/overview")
def borrower_financial_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    snapshot = financial_snapshot(db, borrower)
    readiness = readiness_score(db, borrower, snapshot)
    next_due = snapshot["next_due"]
    open_requests = db.query(BorrowerServiceRequest.id).filter(
        BorrowerServiceRequest.borrower_id == borrower.id,
        BorrowerServiceRequest.status.in_(list(OPEN_SERVICE_STATUSES)),
    ).count()
    active_applications = db.query(LoanRequest.id).filter(
        LoanRequest.borrower_id == borrower.id,
        ~LoanRequest.status.in_([LoanRequestStatus.CANCELLED, LoanRequestStatus.EXPIRED, LoanRequestStatus.ACCEPTED]),
    ).count()
    return {
        "financial_health": {
            "monthly_income": _num(snapshot["income"]),
            "additional_income": _num(snapshot["additional_income"]),
            "living_expenses": _num(snapshot["living_expenses"]),
            "loanhub_installments": _num(snapshot["internal_commitments"]),
            "external_installments": _num(snapshot["external_commitments"]),
            "total_monthly_commitments": _num(snapshot["total_commitments"]),
            "estimated_disposable_income": _num(snapshot["disposable"]),
            "loanhub_balance": _num(snapshot["internal_balance"]),
            "external_debt_balance": _num(snapshot["external_balance"]),
            "total_outstanding_debt": _num(snapshot["total_debt"]),
            "debt_to_income_percent": round(_num(snapshot["dti"]), 2),
            "maximum_affordable_installment": _num(snapshot["maximum_affordable"]),
            "source": "current_loan_and_profile_records",
        },
        "readiness": readiness,
        "counts": {
            "active_loans": len(snapshot["active_loans"]),
            "external_debts": len(snapshot["debts"]),
            "open_service_requests": open_requests,
            "active_applications": active_applications,
        },
        "next_due": {
            "installment_id": next_due.id,
            "loan_id": next_due.loan_id,
            "loan_reference": next_due.loan.loan_reference if next_due.loan else None,
            "lender": next_due.loan.company.name if next_due.loan and next_due.loan.company else None,
            "due_date": _iso(next_due.due_date),
            "amount_due": _num(Decimal(str(next_due.total_due or 0)) - Decimal(str(next_due.paid_amount or 0))),
            "status": _enum(next_due.status),
        } if next_due else None,
        "consents": {
            "share_profile": bool(borrower.consent_to_share_profile),
            "credit_checks": bool(borrower.consent_to_credit_checks),
        },
    }


@router.get("/financial-profile")
def borrower_financial_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    snapshot = financial_snapshot(db, borrower)
    employment = max(
        snapshot["employment_rows"],
        key=lambda row: (Decimal(str(row.verified_net_income or 0)), _at(row.updated_at)),
        default=None,
    )
    banks = _dedupe_latest(
        db.query(BorrowerBankAccount).filter(BorrowerBankAccount.borrower_id == borrower.id).order_by(BorrowerBankAccount.updated_at.desc()).all(),
        lambda row: ((row.bank_name or "").lower(), row.account_number_last4 or ""),
    )
    kycs = _kyc_rows(db, borrower.id)
    employment_payload = {
        "employment_status": employment.employment_status,
        "employer_name": employment.employer_name,
        "job_title": employment.job_title,
        "employment_start_date": _iso(employment.employment_start_date),
        "contract_type": employment.contract_type,
        "gross_salary": _num(employment.gross_salary),
        "net_salary": _num(employment.net_salary),
        "verified_net_income": _num(employment.verified_net_income),
        "verification_status": employment.verification_status,
        "payslip_count": employment.payslip_count,
        "bank_statement_months": employment.bank_statement_months,
    } if employment else {
        "employment_status": _enum(borrower.employment_status),
        "employer_name": borrower.employer_name,
        "job_title": borrower.job_title,
        "verified_net_income": _num(borrower.monthly_income),
        "verification_status": "borrower_profile",
    }
    return {
        "employment": employment_payload,
        "income_sources": [{
            "id": row.id,
            "source_type": row.source_type,
            "description": row.description,
            "declared_amount": _num(row.declared_amount),
            "verified_amount": _num(row.verified_amount),
            "frequency": row.frequency,
            "is_verified": bool(row.is_verified),
        } for row in snapshot["income_rows"]],
        "expenses": [{
            "id": row.id,
            "category": row.category,
            "description": row.description,
            "monthly_amount": _num(row.monthly_amount),
            "is_verified": bool(row.is_verified),
        } for row in snapshot["expenses"]],
        "external_debts": [{
            "id": row.id,
            "creditor": row.creditor,
            "account_reference": row.account_reference,
            "debt_type": row.debt_type,
            "started_on": _iso(row.started_on),
            "original_amount": _num(row.original_amount),
            "current_balance": _num(row.current_balance),
            "monthly_installment": _num(row.monthly_installment),
            "total_installments": row.total_installments,
            "installments_paid": row.installments_paid,
            "remaining_installments": row.remaining_installments,
            "next_due_date": _iso(row.next_due_date),
            "settlement_amount": _num(row.settlement_amount) if row.settlement_amount is not None else None,
            "remaining_term_months": row.remaining_term_months,
            "status": row.status,
            "is_verified": bool(row.is_verified),
        } for row in snapshot["debts"]],
        "bank_accounts": [{
            "id": row.id,
            "bank_name": row.bank_name,
            "account_holder": row.account_holder,
            "account_type": row.account_type,
            "account_last4": row.account_number_last4,
            "salary_account": bool(row.salary_account),
            "verification_status": row.verification_status,
            "masked_card_number": row.masked_card_number,
            "card_brand": row.card_brand,
        } for row in banks],
        "kyc": {
            "identity_verified": any(row.identity_verified for row in kycs),
            "address_verified": any(row.address_verified for row in kycs),
            "phone_verified": any(row.phone_verified for row in kycs),
            "profiles": len(kycs),
        },
    }


@router.patch("/consents")
def update_borrower_consents(payload: BorrowerConsentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No consent changes were supplied")
    for field, value in changes.items():
        setattr(borrower, field, value)
    db.commit()
    return {"share_profile": bool(borrower.consent_to_share_profile), "credit_checks": bool(borrower.consent_to_credit_checks)}


@router.get("/applications")
def borrower_application_tracker(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    rows = (
        db.query(LoanRequest)
        .options(
            selectinload(LoanRequest.offers).joinedload(LoanOffer.company),
            joinedload(LoanRequest.loan).joinedload(ClientCompanyLoan.company),
            selectinload(LoanRequest.documents),
        )
        .filter(LoanRequest.borrower_id == borrower.id)
        .order_by(LoanRequest.created_at.desc())
        .all()
    )
    results: list[dict[str, Any]] = []
    for row in rows:
        status_value = _enum(row.status)
        offers = list(row.offers or [])
        loan = row.loan
        submitted = bool(row.submitted_at or status_value != "draft")
        review = status_value in {"under_review", "offered", "accepted"} or bool(offers)
        selected = bool(row.selected_offer_id or status_value == "accepted")
        approved = bool(loan and (loan.approved_at or loan.status in {LoanStatus.APPROVED, LoanStatus.ACTIVE, LoanStatus.COMPLETED}))
        disbursed = bool(loan and (loan.disbursed_at or loan.status in {LoanStatus.ACTIVE, LoanStatus.COMPLETED}))
        stages = [
            {"key": "created", "label": "Application created", "complete": True},
            {"key": "submitted", "label": "Submitted to LoanHub", "complete": submitted},
            {"key": "review", "label": "Lender / credit review", "complete": review},
            {"key": "offer", "label": "Offer received", "complete": bool(offers)},
            {"key": "accepted", "label": "Offer accepted / approved", "complete": selected or approved},
            {"key": "disbursed", "label": "Loan disbursed", "complete": disbursed},
        ]
        if status_value == "draft":
            action_required = "Complete and submit this application."
        elif offers and not selected:
            action_required = "Compare the available offers and choose only if one suits you."
        elif not borrower.consent_to_share_profile or not borrower.consent_to_credit_checks:
            action_required = "Review your lending consents; disabled consent can prevent further assessment."
        else:
            action_required = None
        results.append({
            "id": row.id,
            "requested_amount": _num(row.requested_amount),
            "preferred_term_months": row.preferred_term_months,
            "loan_purpose": row.loan_purpose,
            "status": status_value,
            "created_at": _iso(row.created_at),
            "submitted_at": _iso(row.submitted_at),
            "offer_count": len(offers),
            "documents_count": len(row.documents or []),
            "selected_offer_id": row.selected_offer_id,
            "loan_id": loan.id if loan else None,
            "loan_reference": loan.loan_reference if loan else None,
            "lender": loan.company.name if loan and loan.company else None,
            "stages": stages,
            "action_required": action_required,
        })
    return results


@router.get("/offers/{request_id}")
def borrower_offer_comparison(request_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    request_row = (
        db.query(LoanRequest)
        .options(selectinload(LoanRequest.offers).joinedload(LoanOffer.company))
        .filter(LoanRequest.id == request_id, LoanRequest.borrower_id == borrower.id)
        .first()
    )
    if not request_row:
        raise HTTPException(status_code=404, detail="Loan request not found")
    offers = list(request_row.offers or [])
    active = [offer for offer in offers if _enum(offer.status) not in {"withdrawn", "expired", "rejected"}]
    lowest_total = min((_num(offer.total_repayment) for offer in active), default=None)
    lowest_monthly = min((_num(offer.monthly_repayment) for offer in active), default=None)
    return {
        "request": {
            "id": request_row.id,
            "requested_amount": _num(request_row.requested_amount),
            "preferred_term_months": request_row.preferred_term_months,
            "loan_purpose": request_row.loan_purpose,
            "selected_offer_id": request_row.selected_offer_id,
        },
        "offers": [{
            "id": offer.id,
            "company_id": offer.company_id,
            "company_name": offer.company.name if offer.company else "Lender",
            "approved_amount": _num(offer.approved_amount),
            "term_months": offer.term_months,
            "interest_rate_percent": _num(offer.interest_rate_percent),
            "processing_fee": _num(offer.processing_fee),
            "monthly_repayment": _num(offer.monthly_repayment),
            "total_repayment": _num(offer.total_repayment),
            "status": _enum(offer.status),
            "expires_at": _iso(offer.expires_at),
            "is_selected": offer.id == request_row.selected_offer_id,
            "is_lowest_total": lowest_total is not None and _num(offer.total_repayment) == lowest_total,
            "is_lowest_installment": lowest_monthly is not None and _num(offer.monthly_repayment) == lowest_monthly,
        } for offer in offers],
        "guidance": "Compare the monthly installment, fees and total repayment. The lowest installment is not always the lowest total cost.",
    }


@router.get("/repayment-calendar")
def borrower_repayment_calendar(include_paid: bool = Query(default=False), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    query = (
        db.query(RepaymentInstallment)
        .join(ClientCompanyLoan, RepaymentInstallment.loan_id == ClientCompanyLoan.id)
        .options(joinedload(RepaymentInstallment.loan).joinedload(ClientCompanyLoan.company))
        .filter(ClientCompanyLoan.borrower_id == borrower.id, RepaymentInstallment.is_superseded.is_(False))
    )
    if not include_paid:
        query = query.filter(~RepaymentInstallment.status.in_([InstallmentStatus.PAID, InstallmentStatus.WAIVED]))
    rows = query.order_by(RepaymentInstallment.due_date.asc()).all()
    return [{
        "id": row.id,
        "loan_id": row.loan_id,
        "loan_reference": row.loan.loan_reference if row.loan else None,
        "lender": row.loan.company.name if row.loan and row.loan.company else None,
        "installment_number": row.installment_number,
        "due_date": _iso(row.due_date),
        "principal_due": _num(row.principal_due),
        "interest_due": _num(row.interest_due),
        "fee_due": _num(row.fee_due),
        "total_due": _num(row.total_due),
        "paid_amount": _num(row.paid_amount),
        "remaining_due": _num(max(Decimal("0"), Decimal(str(row.total_due or 0)) - Decimal(str(row.paid_amount or 0)))),
        "status": _enum(row.status),
        "paid_at": _iso(row.paid_at),
    } for row in rows]


@router.get("/payoff/{loan_id}")
def borrower_payoff_estimate(loan_id: UUID, extra_payment: Decimal = Query(default=Decimal("0"), ge=0), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    loan = (
        db.query(ClientCompanyLoan)
        .options(joinedload(ClientCompanyLoan.company), selectinload(ClientCompanyLoan.installments))
        .filter(ClientCompanyLoan.id == loan_id, ClientCompanyLoan.borrower_id == borrower.id)
        .first()
    )
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    balance = Decimal(str(loan.balance or 0))
    installment = Decimal(str(loan.installment_amount or 0))
    balance_after = max(Decimal("0"), balance - extra_payment)
    estimated_installments = int((balance_after / installment).to_integral_value(rounding=ROUND_CEILING)) if balance_after > 0 and installment > 0 else 0
    remaining_schedule = sum((
        max(Decimal("0"), Decimal(str(row.total_due or 0)) - Decimal(str(row.paid_amount or 0)))
        for row in loan.installments
        if not row.is_superseded and row.status not in {InstallmentStatus.PAID, InstallmentStatus.WAIVED}
    ), Decimal("0"))
    return {
        "loan_id": loan.id,
        "loan_reference": loan.loan_reference,
        "lender": loan.company.name if loan.company else "Lender",
        "current_balance": _num(balance),
        "scheduled_installment": _num(installment),
        "extra_payment": _num(extra_payment),
        "estimated_balance_after_extra": _num(balance_after),
        "estimated_installments_remaining": estimated_installments,
        "remaining_scheduled_amount": _num(remaining_schedule),
        "official_settlement_required": True,
        "disclaimer": "This is a planning estimate based on the current recorded balance. Request an official settlement quotation from the lender before settling or refinancing.",
    }


@router.get("/eligibility")
def borrower_product_eligibility(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    snapshot = financial_snapshot(db, borrower)
    person = borrower.user.person if borrower.user else None
    age = None
    if person and person.date_of_birth:
        today = date.today()
        age = today.year - person.date_of_birth.year - ((today.month, today.day) < (person.date_of_birth.month, person.date_of_birth.day))
    products = (
        db.query(LoanProduct)
        .join(LoanCompany, LoanProduct.company_id == LoanCompany.id)
        .options(joinedload(LoanProduct.company))
        .filter(LoanProduct.is_active.is_(True), LoanCompany.status == CompanyStatus.APPROVED, LoanCompany.is_active.is_(True))
        .order_by(LoanCompany.name.asc(), LoanProduct.name.asc())
        .all()
    )
    policies = {row.company_id: row for row in db.query(OriginationPolicy).filter(OriginationPolicy.is_active.is_(True)).all()}
    kyc_rows = _kyc_rows(db, borrower.id)
    kyc_by_company = {row.company_id: row for row in kyc_rows}
    dependant_count = max((row.dependants for row in kyc_rows), default=0)
    results: list[dict[str, Any]] = []
    today = date.today()
    for product in products:
        policy = policies.get(product.company_id)
        term = max(1, int(product.max_term_months or product.min_term_months or 1))
        amount = Decimal(str(product.min_amount or 0))
        try:
            due_dates = generate_monthly_due_dates(today, term)
            monthly, total, details = calculate_loan_terms(
                principal=amount,
                rate_percent=Decimal(str(product.interest_rate_percent or 0)),
                term_months=term,
                processing_fee=Decimal(str(product.processing_fee or 0)),
                interest_method=product.interest_method,
                start_date=today,
                due_dates=due_dates,
            )
            estimated_monthly, estimated_total, rate_basis = monthly, total, details.get("rate_basis")
        except ValueError:
            estimated_monthly = (amount + Decimal(str(product.processing_fee or 0))) / Decimal(term)
            estimated_total = amount + Decimal(str(product.processing_fee or 0))
            rate_basis = "Fallback estimate; lender calculation must be confirmed"
        hard_reasons: list[str] = []
        verification_reasons: list[str] = []
        income = Decimal(str(snapshot["income"]))
        commitments = Decimal(str(snapshot["total_commitments"]))
        living_expenses = Decimal(str(snapshot["living_expenses"]))
        projected_dti = (commitments + estimated_monthly) / income * Decimal("100") if income > 0 else Decimal("999")
        if not borrower.consent_to_share_profile:
            verification_reasons.append("Profile-sharing consent is currently disabled.")
        if not borrower.consent_to_credit_checks:
            verification_reasons.append("Credit-check consent is currently disabled.")
        if any(loan.is_overdue for loan in snapshot["active_loans"]):
            hard_reasons.append("An existing LoanHub facility is currently overdue.")
        if policy:
            if age is not None and (age < policy.min_age or age > policy.max_age):
                hard_reasons.append(f"Current age is outside this lender's configured {policy.min_age}-{policy.max_age} range.")
            if income < Decimal(str(policy.min_verified_net_income or 0)):
                hard_reasons.append("Current verified income is below this lender's configured minimum.")
            if projected_dti > Decimal(str(policy.max_dti_percent or 100)):
                hard_reasons.append("Estimated debt-to-income would exceed this lender's configured limit.")
            buffer = Decimal(str(policy.living_expense_buffer or 0))
            dependant_allowance = Decimal(str(policy.dependant_allowance or 0)) * Decimal(dependant_count)
            projected_disposable = income - living_expenses - commitments - buffer - dependant_allowance - estimated_monthly
            if projected_disposable < Decimal(str(policy.min_disposable_after_installment or 0)):
                hard_reasons.append("Estimated disposable income would be below this lender's configured minimum.")
            kyc = kyc_by_company.get(product.company_id)
            if policy.require_kyc_verified and not (kyc and kyc.identity_verified):
                verification_reasons.append("This lender requires completed KYC verification.")
            if not policy.allow_concurrent_active_loans and any(
                loan.company_id == product.company_id and loan.status in ACTIVE_DEBT_LOAN_STATUSES
                for loan in snapshot["active_loans"]
            ):
                hard_reasons.append("This lender's policy does not allow another concurrent active loan.")
        status_value = "unlikely" if hard_reasons else "needs_verification" if verification_reasons else "appears_eligible"
        results.append({
            "product_id": product.id,
            "company_id": product.company_id,
            "company_name": product.company.name if product.company else "Lender",
            "product_name": product.name,
            "description": product.description,
            "min_amount": _num(product.min_amount),
            "max_amount": _num(product.max_amount),
            "min_term_months": product.min_term_months,
            "max_term_months": product.max_term_months,
            "interest_method": product.interest_method,
            "interest_rate_percent": _num(product.interest_rate_percent),
            "processing_fee": _num(product.processing_fee),
            "estimated_for_amount": _num(amount),
            "estimated_term_months": term,
            "estimated_monthly_installment": _num(estimated_monthly),
            "estimated_total_repayment": _num(estimated_total),
            "estimated_projected_dti_percent": round(_num(projected_dti), 2),
            "rate_basis": rate_basis,
            "status": status_value,
            "reasons": hard_reasons + verification_reasons,
        })
    return {"products": results, "disclaimer": "Eligibility is an estimate from current LoanHub data and lender-configured rules. It is not an approval, offer or promise of credit."}


@router.get("/timeline")
def borrower_life_timeline(limit: int = Query(default=100, ge=10, le=250), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    events: list[dict[str, Any]] = []
    requests = (
        db.query(LoanRequest)
        .options(
            selectinload(LoanRequest.offers).joinedload(LoanOffer.company),
            joinedload(LoanRequest.loan).joinedload(ClientCompanyLoan.company),
        )
        .filter(LoanRequest.borrower_id == borrower.id)
        .all()
    )
    for row in requests:
        events.append({"at": row.created_at, "type": "application_created", "title": "Loan application created", "description": f"Requested M{_num(row.requested_amount):,.2f}", "href": "/borrower/requests"})
        if row.submitted_at:
            events.append({"at": row.submitted_at, "type": "application_submitted", "title": "Loan application submitted", "description": row.loan_purpose or "Submitted for lender review", "href": "/borrower/requests"})
        for offer in row.offers or []:
            events.append({"at": offer.created_at, "type": "offer_received", "title": "Loan offer received", "description": f"{offer.company.name if offer.company else 'Lender'} offered M{_num(offer.approved_amount):,.2f}", "href": "/borrower/financial-centre?tab=applications"})
        if row.loan and row.loan.approved_at:
            events.append({"at": row.loan.approved_at, "type": "loan_approved", "title": "Loan approved", "description": row.loan.loan_reference, "href": "/borrower/loans"})
        if row.loan and row.loan.disbursed_at:
            events.append({"at": row.loan.disbursed_at, "type": "loan_disbursed", "title": "Loan disbursed", "description": row.loan.loan_reference, "href": "/borrower/loans"})
    payments = (
        db.query(PaymentTransaction)
        .options(joinedload(PaymentTransaction.loan))
        .filter(PaymentTransaction.borrower_id == borrower.id, PaymentTransaction.status == PaymentStatus.SUCCEEDED)
        .order_by(PaymentTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    for payment in payments:
        events.append({"at": payment.completed_at or payment.created_at, "type": "payment", "title": f"Payment M{_num(payment.amount):,.2f} received", "description": payment.loan.loan_reference if payment.loan else _enum(payment.purpose).replace("_", " ").title(), "href": "/borrower/payments"})
    service_rows = (
        db.query(BorrowerServiceRequest)
        .options(joinedload(BorrowerServiceRequest.company), joinedload(BorrowerServiceRequest.loan))
        .filter(BorrowerServiceRequest.borrower_id == borrower.id)
        .all()
    )
    for row in service_rows:
        events.append({"at": row.created_at, "type": "service_request", "title": f"{REQUEST_LABELS.get(row.request_type, 'Service request')} submitted", "description": row.company.name if row.company else "Lender", "href": "/borrower/financial-centre?tab=requests"})
        if row.responded_at:
            events.append({"at": row.responded_at, "type": "service_response", "title": f"Request {row.status.replace('_', ' ')}", "description": row.company_response or (row.company.name if row.company else "Lender response"), "href": "/borrower/financial-centre?tab=requests"})
    events.sort(key=lambda item: _at(item["at"]), reverse=True)
    return [{**item, "at": _iso(item["at"])} for item in events[:limit]]


@router.get("/security")
def borrower_security_and_access(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    active_sessions = db.query(RefreshToken.id).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked.is_(False),
        RefreshToken.expires_at > datetime.utcnow(),
    ).count()
    unlocks = (
        db.query(MarketplaceUnlock)
        .join(LoanRequest, MarketplaceUnlock.loan_request_id == LoanRequest.id)
        .options(joinedload(MarketplaceUnlock.company))
        .filter(LoanRequest.borrower_id == borrower.id, MarketplaceUnlock.status == UnlockStatus.UNLOCKED)
        .order_by(MarketplaceUnlock.unlocked_at.desc())
        .limit(50)
        .all()
    )
    return {
        "active_sessions": active_sessions,
        "last_seen_at": _iso(current_user.last_seen_at),
        "account_verified": bool(current_user.is_verified),
        "consents": {"share_profile": bool(borrower.consent_to_share_profile), "credit_checks": bool(borrower.consent_to_credit_checks)},
        "profile_access": [{
            "company_id": row.company_id,
            "company_name": row.company.name if row.company else "Lender",
            "loan_request_id": row.loan_request_id,
            "unlocked_at": _iso(row.unlocked_at),
            "expires_at": _iso(row.expires_at),
            "purpose": "Marketplace loan assessment",
        } for row in unlocks],
        "account_security_url": "/borrower/account",
    }


@router.get("/service-requests")
def list_borrower_service_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    rows = (
        db.query(BorrowerServiceRequest)
        .options(joinedload(BorrowerServiceRequest.company), joinedload(BorrowerServiceRequest.loan))
        .filter(BorrowerServiceRequest.borrower_id == borrower.id)
        .order_by(BorrowerServiceRequest.created_at.desc())
        .all()
    )
    return [_service_payload(row) for row in rows]


@router.post("/service-requests", status_code=201)
def create_borrower_service_request(payload: BorrowerServiceRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    loan = None
    company_id = payload.company_id
    if payload.loan_id:
        loan = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.id == payload.loan_id, ClientCompanyLoan.borrower_id == borrower.id).first()
        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found")
        if company_id and company_id != loan.company_id:
            raise HTTPException(status_code=422, detail="Selected company does not match the selected loan")
        company_id = loan.company_id
    elif payload.request_type in LOAN_REQUIRED_REQUEST_TYPES:
        raise HTTPException(status_code=422, detail="Select the LoanHub loan this request relates to")
    if not company_id:
        raise HTTPException(status_code=422, detail="Select the lender that should receive this request")
    company = db.get(LoanCompany, company_id)
    if not company or company.status != CompanyStatus.APPROVED or not company.is_active:
        raise HTTPException(status_code=422, detail="Selected lender is not currently available")
    duplicate = db.query(BorrowerServiceRequest.id).filter(
        BorrowerServiceRequest.borrower_id == borrower.id,
        BorrowerServiceRequest.company_id == company_id,
        BorrowerServiceRequest.request_type == payload.request_type,
        BorrowerServiceRequest.loan_id == payload.loan_id,
        BorrowerServiceRequest.status.in_(list(OPEN_SERVICE_STATUSES)),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="An open request of this type already exists for this lender/loan")
    label = REQUEST_LABELS[payload.request_type]
    row = BorrowerServiceRequest(
        borrower_id=borrower.id,
        company_id=company_id,
        loan_id=payload.loan_id,
        request_type=payload.request_type,
        status="submitted",
        subject=payload.subject or (f"{label} — {loan.loan_reference}" if loan else label),
        details=payload.details,
        requested_value=payload.requested_value,
    )
    db.add(row)
    db.flush()
    _notify_company_reviewers(db, row, current_user.id)
    db.commit()
    return _service_payload(
        db.query(BorrowerServiceRequest)
        .options(joinedload(BorrowerServiceRequest.company), joinedload(BorrowerServiceRequest.loan))
        .filter(BorrowerServiceRequest.id == row.id)
        .one()
    )


@router.patch("/service-requests/{request_id}/cancel")
def cancel_borrower_service_request(request_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    borrower = _require_borrower(current_user)
    row = (
        db.query(BorrowerServiceRequest)
        .options(joinedload(BorrowerServiceRequest.company), joinedload(BorrowerServiceRequest.loan))
        .filter(BorrowerServiceRequest.id == request_id, BorrowerServiceRequest.borrower_id == borrower.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Service request not found")
    if row.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="This request can no longer be cancelled by the borrower")
    row.status = "cancelled"
    db.commit()
    db.refresh(row)
    return _service_payload(row)


@router.get("/company/service-requests")
def list_company_borrower_service_requests(status_filter: str | None = Query(default=None, alias="status"), db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    require_tenant_roles(context, SERVICE_REVIEW_ROLES)
    query = db.query(BorrowerServiceRequest).options(
        joinedload(BorrowerServiceRequest.company),
        joinedload(BorrowerServiceRequest.loan),
        joinedload(BorrowerServiceRequest.borrower).joinedload(Borrower.user).joinedload(User.person),
    )
    if not context.is_platform_admin:
        query = query.filter(BorrowerServiceRequest.company_id == context.company_id)
    if status_filter:
        normalized = status_filter.strip().lower()
        if normalized not in BORROWER_SERVICE_REQUEST_STATUSES:
            raise HTTPException(status_code=422, detail="Unknown service-request status")
        query = query.filter(BorrowerServiceRequest.status == normalized)
    rows = query.order_by(BorrowerServiceRequest.created_at.desc()).limit(500).all()
    return [_service_payload(row, include_borrower=True) for row in rows]


@router.patch("/company/service-requests/{request_id}")
def update_company_borrower_service_request(request_id: UUID, payload: BorrowerServiceRequestCompanyUpdate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    require_tenant_roles(context, SERVICE_REVIEW_ROLES)
    row = (
        db.query(BorrowerServiceRequest)
        .options(joinedload(BorrowerServiceRequest.company), joinedload(BorrowerServiceRequest.loan), joinedload(BorrowerServiceRequest.borrower))
        .filter(BorrowerServiceRequest.id == request_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Service request not found")
    if not context.is_platform_admin and row.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    if row.status in {"cancelled", "declined", "completed"}:
        raise HTTPException(status_code=409, detail="This service request is already closed")
    row.status = payload.status
    row.company_response = payload.company_response
    row.responded_by_user_id = context.user.id
    row.responded_at = datetime.utcnow()
    _notify_borrower_response(db, row, context.user.id)
    db.commit()
    db.refresh(row)
    return _service_payload(row, include_borrower=True)
