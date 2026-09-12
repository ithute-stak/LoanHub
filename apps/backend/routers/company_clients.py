from __future__ import annotations

import calendar
from io import BytesIO
import re
import secrets
from urllib.parse import quote
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.audit_log import AuditLog
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_client import CompanyBorrowerAccount
from database.models.company_client_case import CompanyClientCaseEntry
from database.models.company_client_identity_change import CompanyClientIdentityChangeRequest
from database.models.file_management import ManagedFile
from database.models.loan_product import LoanProduct
from database.models.enums import InstallmentStatus, LoanStatus, PaymentProvider, PaymentPurpose, PaymentStatus, UserRole
from database.models.person import Person
from database.models.payment import PaymentTransaction
from database.models.professional_lending import DirectLoanApplication
from database.models.origination import (
    BorrowerBankAccount,
    BorrowerDebtObligation,
    BorrowerDebtObligationEvent,
)
from database.models.repayment import RepaymentInstallment
from database.models.user import User
from database.schemas.company_clients import (
    AssistedCompanyClientCreate,
    CashOpeningFeeSettlementCreate,
    CompanyClientExistingLoanCheckRead,
    CompanyClientExternalDebtCreate,
    CompanyClientExternalDebtEventRead,
    CompanyClientExternalDebtPaymentCreate,
    CompanyClientExternalDebtRead,
    CompanyClientExternalDebtUpdate,
    CompanyClientCaseEntryCreate,
    CompanyClientCaseEntryRead,
    CompanyClientCaseEntryUpdate,
    CompanyClientCaseRecordRead,
    CompanyClientRead,
    CompanyClientLoanInsightRead,
    CompanyClientPortfolioInsightsRead,
    CompanyClientNationalIdChangeDecision,
    CompanyClientNationalIdChangeRequestCreate,
    CompanyClientNationalIdChangeRequestRead,
    CompanyClientPaymentRatingRead,
    CompanyClientProfilePermissionsRead,
    CompanyClientProfileDocumentRead,
    CompanyClientProfileLoanRead,
    CompanyClientProfileRead,
    CompanyClientProfileUpdate,
    CompanyClientProfileStatsRead,
    InternalClientLoanRequestCreate,
    InternalClientLoanRequestRead,
)
from database.schemas.payment import PaymentTransactionRead
from database.session import get_db
from services.company_client_service import (
    borrower_existing_loan_exposure,
    external_debt_payload,
    normalized_monthly_debt_installment,
    save_assisted_external_debts,
    sync_borrower_external_debt_summary,
    company_client_or_404,
    create_assisted_company_client,
    find_person_by_national_id,
)
from services.borrower_identity_change_service import (
    approve_as_company_owner,
    create_identity_change_request,
    expire_request_if_needed,
    reject_identity_change_request,
    serialize_identity_change_request,
)
from services.borrower_profile_service import build_payment_rating
from services.file_service import physical_path, read_file_bytes, save_upload
from services.payment_service import build_idempotency_key, initiate_payment
from services.receipt_service import ensure_payment_receipt
from services.credential_service import encrypt_credential


router = APIRouter(prefix="/company-clients", tags=["Company Clients"])


CLIENT_FILE_LINK_TYPE = "company_borrower_account"
PROFILE_IMAGE_CATEGORY = "borrower_profile_image"
PROFILE_DOCUMENT_CATEGORIES = {
    "national_id": "borrower_national_id",
    "passport": "borrower_passport",
    "payslip": "borrower_payslip",
    "bank_statement": "borrower_bank_statement",
    "proof_of_residence": "borrower_proof_of_residence",
    "employment_letter": "borrower_employment_letter",
    "loan_agreement": "borrower_loan_agreement",
    "other": "borrower_other",
}
PROFILE_CATEGORY_DOCUMENT_TYPES = {
    category: document_type
    for document_type, category in PROFILE_DOCUMENT_CATEGORIES.items()
}


def _external_debt_or_404(
    db: Session,
    *,
    account: CompanyBorrowerAccount,
    debt_id: UUID,
) -> BorrowerDebtObligation:
    debt = (
        db.query(BorrowerDebtObligation)
        .options(joinedload(BorrowerDebtObligation.events))
        .filter(
            BorrowerDebtObligation.id == debt_id,
            BorrowerDebtObligation.borrower_id == account.borrower_id,
        )
        .first()
    )
    if not debt:
        raise HTTPException(status_code=404, detail="Tracked external loan not found")
    return debt


def _record_external_debt_event(
    db: Session,
    *,
    debt: BorrowerDebtObligation,
    user_id: UUID,
    event_type: str,
    amount: Decimal | None = None,
    notes: str | None = None,
    event_at: datetime | None = None,
) -> BorrowerDebtObligationEvent:
    event = BorrowerDebtObligationEvent(
        company_id=debt.company_id,
        borrower_id=debt.borrower_id,
        obligation_id=debt.id,
        recorded_by_user_id=user_id,
        event_type=event_type,
        event_at=event_at or datetime.now(timezone.utc),
        amount=amount,
        balance_after=Decimal(debt.current_balance or 0),
        remaining_installments_after=debt.remaining_installments,
        notes=(notes or "").strip() or None,
    )
    db.add(event)
    return event


def _validate_external_debt_schedule(debt: BorrowerDebtObligation) -> None:
    total = debt.total_installments
    paid = int(debt.installments_paid or 0)
    remaining = debt.remaining_installments
    if total is not None and paid > total:
        raise HTTPException(status_code=422, detail="Paid installments cannot exceed total installments")
    if total is not None and remaining is not None and paid + remaining > total:
        raise HTTPException(
            status_code=422,
            detail="Paid and remaining installments cannot exceed total installments",
        )
    if debt.started_on and debt.started_on > date.today():
        raise HTTPException(status_code=422, detail="An existing loan start date cannot be in the future")
    if (debt.status or "active") in {"active", "defaulted", "restructured", "unknown"} and Decimal(debt.current_balance or 0) > 0:
        if Decimal(debt.installment_amount or 0) <= 0:
            raise HTTPException(status_code=422, detail="Enter the installment amount for an active existing loan")
        if debt.remaining_installments is None:
            raise HTTPException(status_code=422, detail="Enter the number of installments remaining")


def _case_entry_read(entry: CompanyClientCaseEntry) -> CompanyClientCaseEntryRead:
    actor_name = None
    actor = entry.created_by_user
    if actor is not None:
        person = getattr(actor, "person", None)
        if person is not None:
            actor_name = " ".join(
                value for value in [person.first_name, person.middle_name, person.last_name] if value
            )
        actor_name = actor_name or actor.email or actor.phone

    return CompanyClientCaseEntryRead(
        id=entry.id,
        company_id=entry.company_id,
        branch_id=entry.branch_id,
        company_borrower_account_id=entry.company_borrower_account_id,
        borrower_id=entry.borrower_id,
        created_by_user_id=entry.created_by_user_id,
        created_by_name=actor_name,
        entry_type=entry.entry_type,
        category=entry.category,
        title=entry.title,
        body=entry.body,
        status=entry.status,
        action_date=entry.action_date,
        reference_number=entry.reference_number,
        amount=Decimal(entry.amount) if entry.amount is not None else None,
        currency=entry.currency,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _client_read(account: CompanyBorrowerAccount, summary: dict | None = None) -> CompanyClientRead:
    summary = summary or {}
    borrower = account.borrower
    user = borrower.user
    person = user.person
    full_name = " ".join(
        value for value in [person.first_name, person.middle_name, person.last_name] if value
    )
    return CompanyClientRead(
        id=account.id,
        account_reference=account.account_reference,
        company_id=account.company_id,
        branch_id=account.branch_id,
        borrower_id=borrower.id,
        user_id=user.id,
        opened_by_user_id=account.opened_by_user_id,
        source=account.source,
        status=account.status,
        opening_fee_amount=Decimal(account.opening_fee_amount or 0),
        opening_fee_currency=account.opening_fee_currency,
        opening_fee_status=account.opening_fee_status,
        opening_fee_payment_id=account.opening_fee_payment_id,
        first_name=person.first_name,
        middle_name=person.middle_name,
        last_name=person.last_name,
        full_name=full_name,
        email=user.email,
        phone=user.phone,
        gender=person.gender.value if person.gender else None,
        date_of_birth=person.date_of_birth,
        marital_status=person.marital_status.value if person.marital_status else None,
        nationality=person.nationality,
        national_id=person.national_id,
        passport_number=person.passport_number,
        district=person.district,
        town_or_village=person.town_or_village,
        physical_address=person.physical_address,
        employment_status=borrower.employment_status.value,
        employer_name=borrower.employer_name,
        employer_group_id=borrower.employer_group_id,
        employer_group_code=(borrower.employer_group.code if borrower.employer_group else None),
        income_day=borrower.income_day,
        job_title=borrower.job_title,
        monthly_income=borrower.monthly_income,
        has_existing_loans=borrower.has_existing_loans,
        existing_loan_total=Decimal(borrower.existing_loan_total or 0),
        consent_to_credit_checks=borrower.consent_to_credit_checks,
        is_login_active=user.is_active,
        salary_date=borrower.salary_date,
        has_bank_account=bool(summary.get("has_bank_account", False)),
        bank_account_holder=summary.get("bank_account_holder"),
        bank_name=summary.get("bank_name"),
        bank_branch_name=summary.get("bank_branch_name"),
        bank_branch_code=summary.get("bank_branch_code"),
        bank_account_last4=summary.get("bank_account_last4"),
        masked_bank_account=summary.get("masked_bank_account"),
        bank_account_type=summary.get("bank_account_type"),
        bank_currency=summary.get("bank_currency"),
        bank_verification_status=summary.get("bank_verification_status"),
        salary_account=bool(summary.get("salary_account", False)),
        next_salary_pay_date=summary.get("next_salary_pay_date"),
        loan_count=int(summary.get("loan_count", 0)),
        active_loan_count=int(summary.get("active_loan_count", 0)),
        loan_statuses=list(summary.get("loan_statuses", [])),
        outstanding_balance=Decimal(summary.get("outstanding_balance", 0) or 0),
        next_due_date=summary.get("next_due_date"),
        next_due_amount=(Decimal(summary["next_due_amount"]) if summary.get("next_due_amount") is not None else None),
        overdue_installment_count=int(summary.get("overdue_installment_count", 0)),
        recent_loan_id=summary.get("recent_loan_id"),
        recent_loan_reference=summary.get("recent_loan_reference"),
        recent_loan_status=summary.get("recent_loan_status"),
        recent_loan_created_at=summary.get("recent_loan_created_at"),
        case_entry_count=int(summary.get("case_entry_count", 0)),
        comment_count=int(summary.get("comment_count", 0)),
        legal_action_count=int(summary.get("legal_action_count", 0)),
        open_legal_action_count=int(summary.get("open_legal_action_count", 0)),
        latest_case_entry_at=summary.get("latest_case_entry_at"),
        latest_case_entry_kind=summary.get("latest_case_entry_kind"),
        created_at=account.created_at,
        updated_at=account.updated_at,
    )



def _profile_permissions(context: TenantContext) -> CompanyClientProfilePermissionsRead:
    role = context.role
    return CompanyClientProfilePermissionsRead(
        can_edit_profile=role in LENDING_ROLES,
        can_edit_contact=role in COMPANY_MANAGEMENT_ROLES,
        can_edit_banking=role in LENDING_ROLES,
        can_edit_account_status=role in COMPANY_MANAGEMENT_ROLES,
        can_request_national_id_change=role in LENDING_ROLES,
        can_approve_national_id_change=role == UserRole.COMPANY_OWNER,
    )


def _latest_identity_change_request(
    db: Session,
    *,
    account_id: UUID,
) -> CompanyClientIdentityChangeRequest | None:
    row = (
        db.query(CompanyClientIdentityChangeRequest)
        .filter(CompanyClientIdentityChangeRequest.company_borrower_account_id == account_id)
        .order_by(CompanyClientIdentityChangeRequest.created_at.desc())
        .first()
    )
    if row is not None:
        expire_request_if_needed(row)
    return row


def _clean_profile_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _audit_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _upsert_profile_bank_account(
    db: Session,
    *,
    account: CompanyBorrowerAccount,
    values: dict,
) -> tuple[BorrowerBankAccount, bool]:
    row = (
        db.query(BorrowerBankAccount)
        .filter(
            BorrowerBankAccount.borrower_id == account.borrower_id,
        )
        .order_by(
            BorrowerBankAccount.salary_account.desc(),
            BorrowerBankAccount.updated_at.desc(),
        )
        .first()
    )
    created = row is None
    changed = created
    account_number = _clean_profile_string(values.pop("account_number", None))
    if account_number:
        account_number = "".join(ch for ch in account_number if ch.isalnum())
        changed = True
        if len(account_number) < 4:
            raise HTTPException(status_code=422, detail="A valid bank account number is required")

    if row is None:
        required = {
            "account_holder": _clean_profile_string(values.get("account_holder")),
            "bank_name": _clean_profile_string(values.get("bank_name")),
        }
        missing = [label.replace("_", " ") for label, value in required.items() if not value]
        if not account_number:
            missing.append("account number")
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Complete the new banking profile: {', '.join(missing)}",
            )
        row = BorrowerBankAccount(
            company_id=account.company_id,
            borrower_id=account.borrower_id,
            account_holder=required["account_holder"],
            bank_name=required["bank_name"],
            account_type=_clean_profile_string(values.get("account_type")) or "savings",
            currency=(_clean_profile_string(values.get("currency")) or "LSL").upper(),
            account_number_encrypted=encrypt_credential(account_number),
            account_number_last4=account_number[-4:],
            salary_account=bool(values.get("salary_account", False)),
            verification_status="unverified",
        )
        db.add(row)

    editable = {
        "account_holder",
        "bank_name",
        "branch_name",
        "branch_code",
        "account_type",
        "currency",
        "salary_account",
    }
    for field, value in values.items():
        if field not in editable:
            continue
        if isinstance(value, str):
            value = _clean_profile_string(value)
        if field == "currency" and value:
            value = value.upper()
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed = True

    if account_number:
        row.account_number_encrypted = encrypt_credential(account_number)
        row.account_number_last4 = account_number[-4:]
    if changed:
        row.verification_status = "unverified"
        row.verification_reference = None
        row.verified_at = None
        db.flush()
    return row, changed


OPEN_INSTALLMENT_STATUSES = {
    InstallmentStatus.PENDING,
    InstallmentStatus.PARTIALLY_PAID,
    InstallmentStatus.OVERDUE,
}
CURRENT_LOAN_STATUSES = {
    LoanStatus.APPROVED,
    LoanStatus.ACTIVE,
    LoanStatus.DEFAULTED,
}


def _enum_value(value) -> str:
    return str(getattr(value, "value", value))


def _profile_document_read(record: ManagedFile) -> CompanyClientProfileDocumentRead:
    document_type = (
        "profile_image"
        if record.category == PROFILE_IMAGE_CATEGORY
        else PROFILE_CATEGORY_DOCUMENT_TYPES.get(record.category, "other")
    )
    return CompanyClientProfileDocumentRead(
        id=record.id,
        reference=record.reference,
        document_type=document_type,
        original_name=record.original_name,
        mime_type=record.mime_type,
        size_bytes=int(record.size_bytes or 0),
        description=record.description,
        is_confidential=bool(record.is_confidential),
        created_at=record.created_at,
    )


def _client_file_or_404(
    db: Session,
    *,
    account: CompanyBorrowerAccount,
    file_id: UUID,
) -> ManagedFile:
    record = (
        db.query(ManagedFile)
        .filter(
            ManagedFile.id == file_id,
            ManagedFile.company_id == account.company_id,
            ManagedFile.linked_entity_type == CLIENT_FILE_LINK_TYPE,
            ManagedFile.linked_entity_id == str(account.id),
            ManagedFile.category.in_(list(PROFILE_CATEGORY_DOCUMENT_TYPES) + [PROFILE_IMAGE_CATEGORY]),
            ManagedFile.is_deleted.is_(False),
        )
        .first()
    )
    if record is None or record.scan_status not in {"validated", "clean"}:
        raise HTTPException(status_code=404, detail="Borrower profile file not found")
    return record


def _next_monthly_date(day: int, today: date) -> date:
    day = max(1, min(31, day))
    year, month = today.year, today.month
    candidate = date(year, month, min(day, calendar.monthrange(year, month)[1]))
    if candidate >= today:
        return candidate
    month += 1
    if month == 13:
        month = 1
        year += 1
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _next_salary_pay_date(raw_value: str | None, today: date) -> date | None:
    """Interpret the legacy salary-date field as a recurring day of month.

    Existing data may contain either ``25``, ``25th`` or an ISO date. For an ISO
    date in the future, keep that exact date; older ISO values continue monthly
    using the recorded day, which is useful for legacy borrower profiles.
    """
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
        return parsed if parsed >= today else _next_monthly_date(parsed.day, today)
    except ValueError:
        pass
    match = re.search(r"(?<!\d)(\d{1,2})(?!\d)", value)
    if not match:
        return None
    day = int(match.group(1))
    if day < 1 or day > 31:
        return None
    return _next_monthly_date(day, today)


def _directory_summaries(
    db: Session,
    *,
    context: TenantContext,
    accounts: list[CompanyBorrowerAccount],
) -> tuple[dict, list[ClientCompanyLoan], list[RepaymentInstallment]]:
    borrower_ids = [account.borrower_id for account in accounts]
    if not borrower_ids:
        return {}, [], []

    banks = (
        db.query(BorrowerBankAccount)
        .filter(
            BorrowerBankAccount.borrower_id.in_(borrower_ids),
        )
        .order_by(
            BorrowerBankAccount.salary_account.asc(),
            BorrowerBankAccount.updated_at.asc(),
        )
        .all()
    )
    loans = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.company_id == context.company_id,
            ClientCompanyLoan.borrower_id.in_(borrower_ids),
        )
        .order_by(ClientCompanyLoan.created_at.desc())
        .all()
    )
    loan_ids = [loan.id for loan in loans]
    installments = (
        db.query(RepaymentInstallment)
        .filter(RepaymentInstallment.loan_id.in_(loan_ids))
        .all()
        if loan_ids
        else []
    )
    account_ids = [account.id for account in accounts]
    case_entries = (
        db.query(CompanyClientCaseEntry)
        .filter(
            CompanyClientCaseEntry.company_id == context.company_id,
            CompanyClientCaseEntry.company_borrower_account_id.in_(account_ids),
        )
        .order_by(CompanyClientCaseEntry.created_at.desc())
        .all()
        if account_ids
        else []
    )

    bank_by_borrower = {bank.borrower_id: bank for bank in banks}
    loans_by_borrower: dict = defaultdict(list)
    loan_by_id = {}
    for loan in loans:
        loans_by_borrower[loan.borrower_id].append(loan)
        loan_by_id[loan.id] = loan

    installments_by_borrower: dict = defaultdict(list)
    for installment in installments:
        loan = loan_by_id.get(installment.loan_id)
        if loan is not None:
            installments_by_borrower[loan.borrower_id].append(installment)

    case_entries_by_account: dict = defaultdict(list)
    for entry in case_entries:
        case_entries_by_account[entry.company_borrower_account_id].append(entry)

    today = date.today()
    summaries: dict = {}
    for account in accounts:
        borrower = account.borrower
        borrower_loans = loans_by_borrower.get(account.borrower_id, [])
        open_installments = [
            item
            for item in installments_by_borrower.get(account.borrower_id, [])
            if item.status in OPEN_INSTALLMENT_STATUSES
        ]
        upcoming = sorted(
            (item for item in open_installments if item.due_date >= today),
            key=lambda item: item.due_date,
        )
        overdue = [
            item
            for item in open_installments
            if item.due_date < today or item.status == InstallmentStatus.OVERDUE
        ]
        recent = borrower_loans[0] if borrower_loans else None
        statuses = sorted({_enum_value(loan.status) for loan in borrower_loans})
        current_loans = [loan for loan in borrower_loans if loan.status in CURRENT_LOAN_STATUSES]
        outstanding = sum((Decimal(loan.balance or 0) for loan in current_loans), Decimal("0"))
        bank = bank_by_borrower.get(account.borrower_id)
        next_due = upcoming[0] if upcoming else None
        account_case_entries = case_entries_by_account.get(account.id, [])
        comment_entries = [item for item in account_case_entries if item.entry_type == "comment"]
        legal_entries = [item for item in account_case_entries if item.entry_type == "legal_action"]
        open_legal_entries = [
            item for item in legal_entries
            if str(item.status or "").lower() not in {"completed", "withdrawn", "closed", "resolved"}
        ]
        latest_case_entry = account_case_entries[0] if account_case_entries else None

        summaries[account.id] = {
            "has_bank_account": bank is not None,
            "bank_account_holder": bank.account_holder if bank else None,
            "bank_name": bank.bank_name if bank else None,
            "bank_branch_name": bank.branch_name if bank else None,
            "bank_branch_code": bank.branch_code if bank else None,
            "bank_account_last4": bank.account_number_last4 if bank else None,
            "masked_bank_account": f"****{bank.account_number_last4}" if bank and bank.account_number_last4 else None,
            "bank_account_type": bank.account_type if bank else None,
            "bank_currency": bank.currency if bank else None,
            "bank_verification_status": bank.verification_status if bank else None,
            "salary_account": bool(bank.salary_account) if bank else False,
            "next_salary_pay_date": _next_salary_pay_date(borrower.salary_date, today),
            "loan_count": len(borrower_loans),
            "active_loan_count": sum(1 for loan in borrower_loans if loan.status in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}),
            "loan_statuses": statuses,
            "outstanding_balance": outstanding,
            "next_due_date": next_due.due_date if next_due else None,
            "next_due_amount": (Decimal(next_due.total_due or 0) - Decimal(next_due.paid_amount or 0)) if next_due else None,
            "overdue_installment_count": len(overdue),
            "recent_loan_id": recent.id if recent else None,
            "recent_loan_reference": recent.loan_reference if recent else None,
            "recent_loan_status": _enum_value(recent.status) if recent else None,
            "recent_loan_created_at": recent.created_at if recent else None,
            "case_entry_count": len(account_case_entries),
            "comment_count": len(comment_entries),
            "legal_action_count": len(legal_entries),
            "open_legal_action_count": len(open_legal_entries),
            "latest_case_entry_at": latest_case_entry.created_at if latest_case_entry else None,
            "latest_case_entry_kind": latest_case_entry.entry_type if latest_case_entry else None,
        }

    return summaries, loans, installments


def _optional_bool(value: bool | None) -> bool | None:
    return value if value is not None else None


def _client_query(db: Session, context: TenantContext):
    query = (
        db.query(CompanyBorrowerAccount)
        .options(
            joinedload(CompanyBorrowerAccount.borrower)
            .joinedload(Borrower.user)
            .joinedload(User.person)
        )
        .filter(CompanyBorrowerAccount.company_id == context.company_id)
    )
    if context.branch_id and context.role.value not in {"company_owner", "company_admin"}:
        query = query.filter(CompanyBorrowerAccount.branch_id == context.branch_id)
    return query


@router.get("", response_model=list[CompanyClientRead])
def list_company_clients(
    search: str | None = Query(default=None, max_length=120),
    status_filter: str | None = Query(default=None, alias="status"),
    loan_status: str | None = Query(default=None, max_length=40),
    employment_status: str | None = Query(default=None, max_length=40),
    employer: str | None = Query(default=None, max_length=200),
    opening_fee_status: str | None = Query(default=None, max_length=40),
    branch_id: UUID | None = Query(default=None),
    has_bank_account: bool | None = Query(default=None),
    has_loan: bool | None = Query(default=None),
    bank_last4: str | None = Query(default=None, min_length=1, max_length=4),
    due_within_days: int | None = Query(default=None, ge=0, le=365),
    salary_due_within_days: int | None = Query(default=None, ge=0, le=365),
    overdue_only: bool = Query(default=False),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Return the tenant's client directory with filter-ready portfolio facts.

    Bank account numbers remain encrypted at rest and this endpoint exposes only
    the last four digits/masked representation.
    """
    require_tenant_roles(context, LENDING_ROLES)
    query = _client_query(db, context)
    if status_filter:
        query = query.filter(CompanyBorrowerAccount.status == status_filter)
    if branch_id:
        if context.branch_id and context.role.value not in {"company_owner", "company_admin"}:
            assert_branch_scope(context, branch_id)
        query = query.filter(CompanyBorrowerAccount.branch_id == branch_id)
    if search:
        query = (
            query.join(Borrower, Borrower.id == CompanyBorrowerAccount.borrower_id)
            .join(User, User.id == Borrower.user_id)
            .join(Person, Person.user_id == User.id)
        )
        for term in (item for item in search.strip().split() if item):
            value = f"%{term}%"
            query = query.filter(
                or_(
                    CompanyBorrowerAccount.account_reference.ilike(value),
                    User.phone.ilike(value),
                    User.email.ilike(value),
                    Person.first_name.ilike(value),
                    Person.middle_name.ilike(value),
                    Person.last_name.ilike(value),
                    Person.national_id.ilike(value),
                    Person.passport_number.ilike(value),
                )
            )

    accounts = query.order_by(CompanyBorrowerAccount.created_at.desc()).all()
    summaries, _, _ = _directory_summaries(db, context=context, accounts=accounts)
    today = date.today()
    employer_filter = str(employer or "").strip().casefold()
    bank_filter = re.sub(r"\D", "", str(bank_last4 or ""))[-4:]
    result: list[CompanyClientRead] = []

    for account in accounts:
        summary = summaries.get(account.id, {})
        borrower = account.borrower
        statuses = set(summary.get("loan_statuses", []))
        if loan_status:
            if loan_status == "none" and summary.get("loan_count", 0) != 0:
                continue
            if loan_status != "none" and loan_status not in statuses:
                continue
        if employment_status and _enum_value(borrower.employment_status) != employment_status:
            continue
        if employer_filter and employer_filter not in str(borrower.employer_name or "").casefold():
            continue
        if opening_fee_status and account.opening_fee_status != opening_fee_status:
            continue
        if has_bank_account is not None and bool(summary.get("has_bank_account")) != has_bank_account:
            continue
        if has_loan is not None and bool(summary.get("loan_count", 0)) != has_loan:
            continue
        if bank_filter and not str(summary.get("bank_account_last4") or "").endswith(bank_filter):
            continue
        if overdue_only and int(summary.get("overdue_installment_count", 0)) <= 0:
            continue
        if due_within_days is not None:
            next_due = summary.get("next_due_date")
            if next_due is None or not (0 <= (next_due - today).days <= due_within_days):
                continue
        if salary_due_within_days is not None:
            salary_due = summary.get("next_salary_pay_date")
            if salary_due is None or not (0 <= (salary_due - today).days <= salary_due_within_days):
                continue

        result.append(_client_read(account, summary))
        if len(result) >= limit:
            break

    return result


@router.get("/portfolio-insights", response_model=CompanyClientPortfolioInsightsRead)
def company_client_portfolio_insights(
    due_within_days: int = Query(default=14, ge=1, le=90),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Small side-rail feed for the full-screen client directory."""
    require_tenant_roles(context, LENDING_ROLES)
    accounts = _client_query(db, context).all()
    _, loans, installments = _directory_summaries(db, context=context, accounts=accounts)
    client_by_borrower = {account.borrower_id: account for account in accounts}
    loan_by_id = {loan.id: loan for loan in loans}
    open_statuses = OPEN_INSTALLMENT_STATUSES
    today = date.today()
    due_cutoff = today + timedelta(days=due_within_days)

    installments_by_loan: dict = defaultdict(list)
    for item in installments:
        installments_by_loan[item.loan_id].append(item)

    def client_name(account: CompanyBorrowerAccount) -> str:
        person = account.borrower.user.person
        return " ".join(value for value in [person.first_name, person.middle_name, person.last_name] if value)

    soon_due: list[CompanyClientLoanInsightRead] = []
    for installment in sorted(installments, key=lambda item: (item.due_date, item.installment_number)):
        if installment.status not in open_statuses or installment.due_date < today or installment.due_date > due_cutoff:
            continue
        loan = loan_by_id.get(installment.loan_id)
        account = client_by_borrower.get(loan.borrower_id) if loan else None
        if loan is None or account is None:
            continue
        due_amount = Decimal(installment.total_due or 0) - Decimal(installment.paid_amount or 0)
        soon_due.append(
            CompanyClientLoanInsightRead(
                loan_id=loan.id,
                loan_reference=loan.loan_reference,
                client_account_id=account.id,
                borrower_id=loan.borrower_id,
                client_name=client_name(account),
                status=_enum_value(loan.status),
                balance=Decimal(loan.balance or 0),
                installment_amount=Decimal(loan.installment_amount or 0),
                due_date=installment.due_date,
                due_amount=due_amount,
                created_at=loan.created_at,
            )
        )
        if len(soon_due) >= limit:
            break

    recent_loans: list[CompanyClientLoanInsightRead] = []
    for loan in sorted(loans, key=lambda row: row.created_at, reverse=True):
        account = client_by_borrower.get(loan.borrower_id)
        if account is None:
            continue
        upcoming = sorted(
            (
                item for item in installments_by_loan.get(loan.id, [])
                if item.status in open_statuses and item.due_date >= today
            ),
            key=lambda item: item.due_date,
        )
        next_due = upcoming[0] if upcoming else None
        recent_loans.append(
            CompanyClientLoanInsightRead(
                loan_id=loan.id,
                loan_reference=loan.loan_reference,
                client_account_id=account.id,
                borrower_id=loan.borrower_id,
                client_name=client_name(account),
                status=_enum_value(loan.status),
                balance=Decimal(loan.balance or 0),
                installment_amount=Decimal(loan.installment_amount or 0),
                due_date=next_due.due_date if next_due else None,
                due_amount=(Decimal(next_due.total_due or 0) - Decimal(next_due.paid_amount or 0)) if next_due else None,
                created_at=loan.created_at,
            )
        )
        if len(recent_loans) >= limit:
            break

    return CompanyClientPortfolioInsightsRead(
        due_within_days=due_within_days,
        soon_due=soon_due,
        recent_loans=recent_loans,
    )


@router.get("/case-records", response_model=list[CompanyClientCaseRecordRead])
def list_company_client_case_records(
    limit: int = Query(default=5000, ge=1, le=5000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Return one row per client that has comments or legal-action history."""
    require_tenant_roles(context, LENDING_ROLES)
    query = (
        db.query(CompanyClientCaseEntry)
        .options(
            joinedload(CompanyClientCaseEntry.account)
            .joinedload(CompanyBorrowerAccount.borrower)
            .joinedload(Borrower.user)
            .joinedload(User.person),
            joinedload(CompanyClientCaseEntry.created_by_user).joinedload(User.person),
        )
        .filter(CompanyClientCaseEntry.company_id == context.company_id)
    )
    if context.branch_id and context.role.value not in {"company_owner", "company_admin"}:
        query = query.filter(CompanyClientCaseEntry.branch_id == context.branch_id)

    entries = query.order_by(CompanyClientCaseEntry.created_at.desc()).limit(limit).all()
    by_account: dict = defaultdict(list)
    for entry in entries:
        by_account[entry.company_borrower_account_id].append(entry)

    records: list[CompanyClientCaseRecordRead] = []
    for account_entries in by_account.values():
        latest = account_entries[0]
        account = latest.account
        if account is None:
            continue
        person = account.borrower.user.person
        client_name = " ".join(
            value for value in [person.first_name, person.middle_name, person.last_name] if value
        )
        comments = [item for item in account_entries if item.entry_type == "comment"]
        legal = [item for item in account_entries if item.entry_type == "legal_action"]
        open_legal = [
            item for item in legal
            if str(item.status or "").lower() not in {"completed", "withdrawn", "closed", "resolved"}
        ]
        preview = " ".join(str(latest.body or "").split())
        records.append(
            CompanyClientCaseRecordRead(
                client_account_id=account.id,
                borrower_id=account.borrower_id,
                branch_id=account.branch_id,
                account_reference=account.account_reference,
                client_name=client_name,
                phone=account.borrower.user.phone,
                comment_count=len(comments),
                legal_action_count=len(legal),
                open_legal_action_count=len(open_legal),
                latest_entry_at=latest.created_at,
                latest_entry_kind=latest.entry_type,
                latest_entry_status=latest.status,
                latest_entry_preview=preview[:280],
            )
        )

    return records


@router.get(
    "/{account_id}/case-entries",
    response_model=list[CompanyClientCaseEntryRead],
)
def list_company_client_case_entries(
    account_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    entries = (
        db.query(CompanyClientCaseEntry)
        .options(joinedload(CompanyClientCaseEntry.created_by_user).joinedload(User.person))
        .filter(
            CompanyClientCaseEntry.company_id == context.company_id,
            CompanyClientCaseEntry.company_borrower_account_id == account.id,
        )
        .order_by(CompanyClientCaseEntry.created_at.desc())
        .all()
    )
    return [_case_entry_read(entry) for entry in entries]


@router.post(
    "/{account_id}/case-entries",
    response_model=CompanyClientCaseEntryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_company_client_case_entry(
    account_id: UUID,
    payload: CompanyClientCaseEntryCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)

    entry_type = payload.entry_type
    entry_status = (payload.status or ("recorded" if entry_type == "comment" else "open")).strip().lower()
    category = payload.category.strip().lower().replace(" ", "_")
    action_date = payload.action_date
    if entry_type == "legal_action" and action_date is None:
        action_date = datetime.now(timezone.utc)

    entry = CompanyClientCaseEntry(
        company_id=context.company_id,
        branch_id=account.branch_id,
        company_borrower_account_id=account.id,
        borrower_id=account.borrower_id,
        created_by_user_id=context.user.id,
        entry_type=entry_type,
        category=category,
        title=(payload.title.strip() if payload.title else None),
        body=payload.body.strip(),
        status=entry_status,
        action_date=action_date,
        reference_number=(payload.reference_number.strip() if payload.reference_number else None),
        amount=payload.amount,
        currency=payload.currency.upper(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    entry = (
        db.query(CompanyClientCaseEntry)
        .options(joinedload(CompanyClientCaseEntry.created_by_user).joinedload(User.person))
        .filter(CompanyClientCaseEntry.id == entry.id)
        .one()
    )
    return _case_entry_read(entry)


@router.patch(
    "/{account_id}/case-entries/{entry_id}",
    response_model=CompanyClientCaseEntryRead,
)
def update_company_client_case_entry(
    account_id: UUID,
    entry_id: UUID,
    payload: CompanyClientCaseEntryUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    entry = (
        db.query(CompanyClientCaseEntry)
        .filter(
            CompanyClientCaseEntry.id == entry_id,
            CompanyClientCaseEntry.company_id == context.company_id,
            CompanyClientCaseEntry.company_borrower_account_id == account.id,
        )
        .one_or_none()
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Client case entry not found")
    if entry.entry_type != "legal_action":
        raise HTTPException(status_code=409, detail="Only legal-action status can be changed")

    entry.status = payload.status.strip().lower()
    db.commit()
    db.refresh(entry)
    entry = (
        db.query(CompanyClientCaseEntry)
        .options(joinedload(CompanyClientCaseEntry.created_by_user).joinedload(User.person))
        .filter(CompanyClientCaseEntry.id == entry.id)
        .one()
    )
    return _case_entry_read(entry)


@router.get(
    "/existing-loan-check",
    response_model=CompanyClientExistingLoanCheckRead,
)
def check_company_client_existing_loans(
    national_id: str = Query(min_length=4, max_length=100),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    cleaned_national_id = national_id.strip()
    person = find_person_by_national_id(db, cleaned_national_id)
    borrower = (
        person.user.borrower_profile
        if person is not None and person.user is not None
        else None
    )
    exposure = borrower_existing_loan_exposure(
        db,
        borrower=borrower,
        company_id=context.company_id,
    )
    return CompanyClientExistingLoanCheckRead(
        national_id=cleaned_national_id,
        checked_at=datetime.now(timezone.utc),
        **exposure,
    )


@router.get(
    "/{account_id}/external-debts",
    response_model=list[CompanyClientExternalDebtRead],
)
def list_company_client_external_debts(
    account_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    rows = (
        db.query(BorrowerDebtObligation)
        .options(joinedload(BorrowerDebtObligation.events))
        .filter(
            BorrowerDebtObligation.borrower_id == account.borrower_id,
        )
        .order_by(BorrowerDebtObligation.started_on.desc().nullslast(), BorrowerDebtObligation.created_at.desc())
        .all()
    )
    return [external_debt_payload(row) for row in rows]


@router.post(
    "/{account_id}/external-debts",
    response_model=CompanyClientExternalDebtRead,
    status_code=status.HTTP_201_CREATED,
)
def create_company_client_external_debt(
    account_id: UUID,
    payload: CompanyClientExternalDebtCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    if not _profile_permissions(context).can_edit_profile:
        raise HTTPException(status_code=403, detail="You do not have permission to manage external loans")
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    rows = save_assisted_external_debts(
        db,
        borrower=account.borrower,
        company_id=context.company_id,
        user_id=context.user.id,
        debts=[payload],
    )
    db.commit()
    debt = _external_debt_or_404(db, account=account, debt_id=rows[0].id)
    return external_debt_payload(debt)


@router.patch(
    "/{account_id}/external-debts/{debt_id}",
    response_model=CompanyClientExternalDebtRead,
)
def update_company_client_external_debt(
    account_id: UUID,
    debt_id: UUID,
    payload: CompanyClientExternalDebtUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    if not _profile_permissions(context).can_edit_profile:
        raise HTTPException(status_code=403, detail="You do not have permission to manage external loans")
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    debt = _external_debt_or_404(db, account=account, debt_id=debt_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No external loan changes were supplied")

    old_balance = Decimal(debt.current_balance or 0)
    old_status = debt.status
    for field, value in changes.items():
        setattr(debt, field, value)

    if "total_installments" in changes and "remaining_installments" not in changes:
        if debt.total_installments is not None:
            debt.remaining_installments = max(
                int(debt.total_installments) - int(debt.installments_paid or 0),
                0,
            )
    if "installment_amount" in changes or "installment_frequency" in changes:
        debt.monthly_installment = normalized_monthly_debt_installment(
            debt.installment_amount,
            debt.installment_frequency,
        )
    if (debt.installment_frequency or "monthly") == "monthly":
        debt.remaining_term_months = debt.remaining_installments
    if Decimal(debt.current_balance or 0) <= 0:
        debt.current_balance = Decimal("0")
        debt.status = "settled"
        debt.remaining_installments = 0
        debt.remaining_term_months = 0

    _validate_external_debt_schedule(debt)
    debt.last_reviewed_at = datetime.now(timezone.utc)
    debt.last_reviewed_by_user_id = context.user.id
    new_balance = Decimal(debt.current_balance or 0)
    event_type = "reviewed"
    amount = None
    if new_balance != old_balance:
        event_type = "balance_adjustment"
        amount = abs(old_balance - new_balance)
    elif debt.status != old_status:
        event_type = "status_changed"
    _record_external_debt_event(
        db,
        debt=debt,
        user_id=context.user.id,
        event_type=event_type,
        amount=amount,
        notes=debt.notes,
    )
    sync_borrower_external_debt_summary(
        db,
        borrower=account.borrower,
        company_id=context.company_id,
    )
    db.commit()
    debt = _external_debt_or_404(db, account=account, debt_id=debt.id)
    return external_debt_payload(debt)


@router.post(
    "/{account_id}/external-debts/{debt_id}/payments",
    response_model=CompanyClientExternalDebtRead,
)
def record_company_client_external_debt_payment(
    account_id: UUID,
    debt_id: UUID,
    payload: CompanyClientExternalDebtPaymentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    if not _profile_permissions(context).can_edit_profile:
        raise HTTPException(status_code=403, detail="You do not have permission to manage external loans")
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    debt = _external_debt_or_404(db, account=account, debt_id=debt_id)
    current_balance = Decimal(debt.current_balance or 0)
    amount = Decimal(payload.amount)
    if current_balance <= 0 or (debt.status or "settled") == "settled":
        raise HTTPException(status_code=409, detail="This external loan is already settled")
    if amount > current_balance:
        raise HTTPException(
            status_code=422,
            detail="The recorded payment cannot exceed the current external-loan balance",
        )
    if debt.remaining_installments is not None and int(payload.installments_covered or 0) > int(debt.remaining_installments):
        raise HTTPException(
            status_code=422,
            detail="Installments covered cannot exceed the number of installments remaining",
        )

    debt.current_balance = (current_balance - amount).quantize(Decimal("0.01"))
    debt.installments_paid = int(debt.installments_paid or 0) + int(payload.installments_covered or 0)
    if debt.remaining_installments is not None:
        debt.remaining_installments = max(
            int(debt.remaining_installments) - int(payload.installments_covered or 0),
            0,
        )
    if (debt.installment_frequency or "monthly") == "monthly":
        debt.remaining_term_months = debt.remaining_installments
    debt.next_due_date = payload.next_due_date
    if Decimal(debt.current_balance or 0) <= 0:
        debt.current_balance = Decimal("0")
        debt.status = "settled"
        debt.remaining_installments = 0
        debt.remaining_term_months = 0
        debt.next_due_date = None
    debt.last_reviewed_at = datetime.now(timezone.utc)
    debt.last_reviewed_by_user_id = context.user.id
    _validate_external_debt_schedule(debt)
    event_at = datetime.combine(payload.paid_on, datetime.min.time(), tzinfo=timezone.utc)
    _record_external_debt_event(
        db,
        debt=debt,
        user_id=context.user.id,
        event_type="payment",
        amount=amount,
        notes=payload.notes or "External loan payment recorded.",
        event_at=event_at,
    )
    sync_borrower_external_debt_summary(
        db,
        borrower=account.borrower,
        company_id=context.company_id,
    )
    db.commit()
    debt = _external_debt_or_404(db, account=account, debt_id=debt.id)
    return external_debt_payload(debt)


@router.get(
    "/{account_id}/external-debts/{debt_id}/events",
    response_model=list[CompanyClientExternalDebtEventRead],
)
def list_company_client_external_debt_events(
    account_id: UUID,
    debt_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    debt = _external_debt_or_404(db, account=account, debt_id=debt_id)
    return external_debt_payload(debt)["events"]


@router.get("/{account_id}/profile", response_model=CompanyClientProfileRead)
def get_company_client_profile(
    account_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(
        db,
        account_id=account_id,
        company_id=context.company_id,
    )
    assert_branch_scope(context, account.branch_id)

    summaries, loans, installments = _directory_summaries(
        db,
        context=context,
        accounts=[account],
    )
    summary = summaries.get(account.id, {})
    installments_by_loan: dict[UUID, list[RepaymentInstallment]] = defaultdict(list)
    for installment in installments:
        installments_by_loan[installment.loan_id].append(installment)

    payments = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.company_id == context.company_id,
            PaymentTransaction.borrower_id == account.borrower_id,
            PaymentTransaction.purpose == PaymentPurpose.LOAN_REPAYMENT,
        )
        .order_by(PaymentTransaction.created_at.desc())
        .all()
    )
    payment_rating = build_payment_rating(installments, loans, payments)

    file_categories = list(PROFILE_CATEGORY_DOCUMENT_TYPES) + [PROFILE_IMAGE_CATEGORY]
    files = (
        db.query(ManagedFile)
        .filter(
            ManagedFile.company_id == context.company_id,
            ManagedFile.linked_entity_type == CLIENT_FILE_LINK_TYPE,
            ManagedFile.linked_entity_id == str(account.id),
            ManagedFile.category.in_(file_categories),
            ManagedFile.is_deleted.is_(False),
            ManagedFile.scan_status.in_(["validated", "clean"]),
        )
        .order_by(ManagedFile.created_at.desc())
        .all()
    )
    profile_image_record = next(
        (file for file in files if file.category == PROFILE_IMAGE_CATEGORY),
        None,
    )
    document_records = [
        file for file in files
        if file.category in PROFILE_CATEGORY_DOCUMENT_TYPES
    ]

    recent_case_entries = (
        db.query(CompanyClientCaseEntry)
        .options(
            joinedload(CompanyClientCaseEntry.created_by_user).joinedload(User.person),
        )
        .filter(
            CompanyClientCaseEntry.company_id == context.company_id,
            CompanyClientCaseEntry.company_borrower_account_id == account.id,
        )
        .order_by(CompanyClientCaseEntry.created_at.desc())
        .limit(20)
        .all()
    )

    profile_loans = []
    for loan in loans:
        loan_installments = installments_by_loan.get(loan.id, [])
        overdue_count = sum(
            1
            for installment in loan_installments
            if (
                _enum_value(installment.status) == InstallmentStatus.OVERDUE.value
                or (
                    installment.due_date < date.today()
                    and _enum_value(installment.status)
                    in {
                        InstallmentStatus.PENDING.value,
                        InstallmentStatus.PARTIALLY_PAID.value,
                    }
                )
            )
        )
        profile_loans.append(
            CompanyClientProfileLoanRead(
                id=loan.id,
                loan_reference=loan.loan_reference,
                status=_enum_value(loan.status),
                risk_level=_enum_value(loan.risk_level),
                principal_amount=Decimal(loan.principal_amount or 0),
                total_repayable=Decimal(loan.total_repayable or 0),
                amount_paid=Decimal(loan.amount_paid or 0),
                balance=Decimal(loan.balance or 0),
                installment_amount=Decimal(loan.installment_amount or 0),
                repayment_type=_enum_value(loan.repayment_type),
                repayment_period=int(loan.repayment_period or 0),
                approved_at=loan.approved_at,
                disbursed_at=loan.disbursed_at,
                first_payment_due=loan.first_payment_due,
                maturity_date=loan.maturity_date,
                is_overdue=bool(loan.is_overdue or overdue_count > 0),
                overdue_installment_count=overdue_count,
            )
        )

    active_statuses = {LoanStatus.APPROVED.value, LoanStatus.ACTIVE.value}
    stats = CompanyClientProfileStatsRead(
        total_loans=len(loans),
        active_loans=sum(1 for loan in loans if _enum_value(loan.status) in active_statuses),
        completed_loans=sum(1 for loan in loans if _enum_value(loan.status) == LoanStatus.COMPLETED.value),
        defaulted_loans=sum(1 for loan in loans if _enum_value(loan.status) == LoanStatus.DEFAULTED.value),
        overdue_loans=sum(1 for loan in profile_loans if loan.is_overdue),
        lifetime_principal_total=sum(
            (Decimal(loan.principal_amount or 0) for loan in loans),
            Decimal("0"),
        ),
        lifetime_paid_total=sum(
            (Decimal(loan.amount_paid or 0) for loan in loans),
            Decimal("0"),
        ),
        outstanding_balance=Decimal(summary.get("outstanding_balance", 0) or 0),
        document_count=len(document_records),
        comment_count=int(summary.get("comment_count", 0)),
        legal_action_count=int(summary.get("legal_action_count", 0)),
        open_legal_action_count=int(summary.get("open_legal_action_count", 0)),
    )

    external_debt_rows = (
        db.query(BorrowerDebtObligation)
        .options(joinedload(BorrowerDebtObligation.events))
        .filter(
            BorrowerDebtObligation.borrower_id == account.borrower_id,
        )
        .order_by(BorrowerDebtObligation.started_on.desc().nullslast(), BorrowerDebtObligation.created_at.desc())
        .all()
    )

    latest_identity_request = _latest_identity_change_request(
        db,
        account_id=account.id,
    )

    return CompanyClientProfileRead(
        client=_client_read(account, summary),
        stats=stats,
        payment_rating=payment_rating,
        permissions=_profile_permissions(context),
        latest_national_id_change_request=(
            serialize_identity_change_request(latest_identity_request)
            if latest_identity_request is not None
            else None
        ),
        loans=profile_loans,
        external_debts=[external_debt_payload(row) for row in external_debt_rows],
        documents=[_profile_document_read(file) for file in document_records],
        profile_image=(
            _profile_document_read(profile_image_record)
            if profile_image_record is not None
            else None
        ),
        recent_case_entries=[_case_entry_read(entry) for entry in recent_case_entries],
    )


@router.patch("/{account_id}/profile", response_model=CompanyClientProfileRead)
def update_company_client_profile(
    account_id: UUID,
    payload: CompanyClientProfileUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(
        db,
        account_id=account_id,
        company_id=context.company_id,
    )
    assert_branch_scope(context, account.branch_id)
    permissions = _profile_permissions(context)
    changes = payload.model_dump(exclude_unset=True)
    bank_values = changes.pop("bank_account", None)
    if not changes and bank_values is None:
        raise HTTPException(status_code=400, detail="No borrower profile changes were supplied")

    contact_fields = {"email", "phone"}
    account_fields = {"is_login_active", "account_status"}
    if (contact_fields | account_fields) & set(changes) and not permissions.can_edit_contact:
        raise HTTPException(
            status_code=403,
            detail="Only a company owner or company administrator may edit contact or login details",
        )
    if bank_values is not None and not permissions.can_edit_banking:
        raise HTTPException(status_code=403, detail="This role cannot edit borrower banking details")

    borrower = account.borrower
    user = borrower.user
    person = user.person
    before_data: dict[str, object] = {}
    after_data: dict[str, object] = {}
    changed_fields: list[str] = []

    person_fields = {
        "first_name",
        "middle_name",
        "last_name",
        "gender",
        "date_of_birth",
        "passport_number",
        "marital_status",
        "nationality",
        "district",
        "town_or_village",
        "physical_address",
    }
    borrower_fields = {
        "employment_status",
        "employer_name",
        "job_title",
        "monthly_income",
        "salary_date",
    }
    if {"has_existing_loans", "existing_loan_total"} & set(changes):
        raise HTTPException(
            status_code=422,
            detail="Use the external-loan tracker to change existing debt balances and installments",
        )

    optional_strings = {
        "middle_name",
        "passport_number",
        "nationality",
        "district",
        "town_or_village",
        "physical_address",
        "employer_name",
        "job_title",
        "salary_date",
    }

    if "passport_number" in changes:
        passport = _clean_profile_string(changes["passport_number"])
        if passport:
            duplicate = (
                db.query(Person.id)
                .filter(
                    Person.id != person.id,
                    func.lower(func.trim(Person.passport_number)) == passport.lower(),
                )
                .first()
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="Passport number is already in use")
        changes["passport_number"] = passport

    for field in person_fields & set(changes):
        value = changes[field]
        if field in optional_strings:
            value = _clean_profile_string(value)
        if field in {"first_name", "last_name"} and not _clean_profile_string(value):
            raise HTTPException(status_code=422, detail=f"{field.replace('_', ' ').title()} is required")
        previous = getattr(person, field)
        if previous != value:
            before_data[field] = _audit_value(previous)
            after_data[field] = _audit_value(value)
            changed_fields.append(field)
            setattr(person, field, value)

    for field in borrower_fields & set(changes):
        value = changes[field]
        if field in optional_strings:
            value = _clean_profile_string(value)
        previous = getattr(borrower, field)
        if previous != value:
            before_data[field] = _audit_value(previous)
            after_data[field] = _audit_value(value)
            changed_fields.append(field)
            setattr(borrower, field, value)

    if "email" in changes:
        value = _clean_profile_string(changes["email"])
        value = value.lower() if value else None
        if value and db.query(User.id).filter(User.email == value, User.id != user.id).first():
            raise HTTPException(status_code=409, detail="Email address is already in use")
        if user.email != value:
            before_data["email"] = user.email
            after_data["email"] = value
            changed_fields.append("email")
            user.email = value
            user.is_verified = False

    if "phone" in changes:
        value = _clean_profile_string(changes["phone"])
        if not value:
            raise HTTPException(status_code=422, detail="Phone number is required")
        if db.query(User.id).filter(User.phone == value, User.id != user.id).first():
            raise HTTPException(status_code=409, detail="Phone number is already in use")
        if user.phone != value:
            before_data["phone"] = user.phone
            after_data["phone"] = value
            changed_fields.append("phone")
            user.phone = value
            user.is_verified = False

    if "is_login_active" in changes and user.is_active != changes["is_login_active"]:
        before_data["is_login_active"] = bool(user.is_active)
        after_data["is_login_active"] = bool(changes["is_login_active"])
        changed_fields.append("is_login_active")
        user.is_active = bool(changes["is_login_active"])

    if "account_status" in changes and account.status != changes["account_status"]:
        before_data["account_status"] = account.status
        after_data["account_status"] = changes["account_status"]
        changed_fields.append("account_status")
        account.status = changes["account_status"]

    if bank_values is not None:
        existing_bank = (
            db.query(BorrowerBankAccount)
            .filter(BorrowerBankAccount.borrower_id == account.borrower_id)
            .order_by(
                BorrowerBankAccount.salary_account.desc(),
                BorrowerBankAccount.updated_at.desc(),
            )
            .first()
        )
        if existing_bank:
            before_data["bank_account"] = {
                "bank_name": existing_bank.bank_name,
                "account_last4": existing_bank.account_number_last4,
                "account_type": existing_bank.account_type,
                "salary_account": bool(existing_bank.salary_account),
            }
        bank_row, bank_changed = _upsert_profile_bank_account(
            db,
            account=account,
            values=dict(bank_values),
        )
        if bank_changed:
            after_data["bank_account"] = {
                "bank_name": bank_row.bank_name,
                "account_last4": bank_row.account_number_last4,
                "account_type": bank_row.account_type,
                "salary_account": bool(bank_row.salary_account),
                "verification_status": bank_row.verification_status,
            }
            changed_fields.append("bank_account")

    if not changed_fields:
        raise HTTPException(status_code=400, detail="The submitted values do not change the borrower profile")

    db.add(
        AuditLog(
            user_id=context.user.id,
            company_id=account.company_id,
            branch_id=account.branch_id,
            action="company_client.profile_updated",
            table_name="company_borrower_accounts",
            entity_type="company_client_profile",
            record_id=account.id,
            description="An authorised company user updated borrower profile fields.",
            actor_role=context.role.value,
            severity="info",
            status="success",
            before_data=before_data,
            after_data=after_data,
            changed_fields=changed_fields,
            event_data={"borrower_id": str(account.borrower_id)},
        )
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="One of the supplied identity or contact values is already in use") from error

    return get_company_client_profile(account_id=account_id, db=db, context=context)


@router.post(
    "/{account_id}/national-id-change-requests",
    response_model=CompanyClientNationalIdChangeRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def request_company_client_national_id_change(
    account_id: UUID,
    payload: CompanyClientNationalIdChangeRequestCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    person = account.borrower.user.person
    if person is None:
        raise HTTPException(status_code=409, detail="The borrower does not have a personal identity profile")
    row = create_identity_change_request(
        db,
        company_id=account.company_id,
        branch_id=account.branch_id,
        account_id=account.id,
        borrower_id=account.borrower_id,
        person=person,
        requested_by_user_id=context.user.id,
        proposed_national_id=payload.proposed_national_id,
        reason=payload.reason,
    )
    try:
        db.commit()
        db.refresh(row)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="A National ID change request is already pending") from error
    return serialize_identity_change_request(row)


@router.post(
    "/{account_id}/national-id-change-requests/{request_id}/company-owner-decision",
    response_model=CompanyClientNationalIdChangeRequestRead,
)
def decide_company_client_national_id_change_as_owner(
    account_id: UUID,
    request_id: UUID,
    payload: CompanyClientNationalIdChangeDecision,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, {UserRole.COMPANY_OWNER})
    account = company_client_or_404(db, account_id=account_id, company_id=context.company_id)
    assert_branch_scope(context, account.branch_id)
    row = (
        db.query(CompanyClientIdentityChangeRequest)
        .filter(
            CompanyClientIdentityChangeRequest.id == request_id,
            CompanyClientIdentityChangeRequest.company_id == account.company_id,
            CompanyClientIdentityChangeRequest.company_borrower_account_id == account.id,
        )
        .with_for_update()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="National ID change request not found")
    if payload.approve:
        approve_as_company_owner(db, row=row, owner_user_id=context.user.id)
    else:
        reject_identity_change_request(
            db,
            row=row,
            user_id=context.user.id,
            actor_role=UserRole.COMPANY_OWNER.value,
            reason=payload.reason,
        )
    db.commit()
    db.refresh(row)
    return serialize_identity_change_request(row)


@router.post(
    "/{account_id}/profile-image",
    response_model=CompanyClientProfileDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_company_client_profile_image(
    account_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(
        db,
        account_id=account_id,
        company_id=context.company_id,
    )
    assert_branch_scope(context, account.branch_id)

    record = await save_upload(
        db,
        file,
        context,
        category=PROFILE_IMAGE_CATEGORY,
        visibility="private",
        description="Borrower profile image",
        linked_entity_type=CLIENT_FILE_LINK_TYPE,
        linked_entity_id=str(account.id),
        is_confidential=True,
        company_id=context.company_id,
        branch_id=account.branch_id,
    )
    if not str(record.mime_type or "").startswith("image/"):
        try:
            physical_path(record).unlink(missing_ok=True)
        finally:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The borrower profile image must be a supported image file",
        )

    db.commit()
    db.refresh(record)
    return _profile_document_read(record)


@router.post(
    "/{account_id}/documents",
    response_model=CompanyClientProfileDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_company_client_document(
    account_id: UUID,
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    description: str | None = Form(None),
    is_confidential: bool = Form(True),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(
        db,
        account_id=account_id,
        company_id=context.company_id,
    )
    assert_branch_scope(context, account.branch_id)

    clean_document_type = document_type.strip().lower()
    category = PROFILE_DOCUMENT_CATEGORIES.get(clean_document_type)
    if category is None:
        raise HTTPException(status_code=400, detail="Unsupported borrower document type")

    record = await save_upload(
        db,
        file,
        context,
        category=category,
        visibility="private",
        description=(description or "").strip() or None,
        linked_entity_type=CLIENT_FILE_LINK_TYPE,
        linked_entity_id=str(account.id),
        is_confidential=is_confidential,
        company_id=context.company_id,
        branch_id=account.branch_id,
    )
    if str(record.mime_type or "").startswith("audio/"):
        try:
            physical_path(record).unlink(missing_ok=True)
        finally:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Audio files cannot be stored as borrower profile documents",
        )

    db.commit()
    db.refresh(record)
    return _profile_document_read(record)


@router.get("/{account_id}/files/{file_id}/content")
def read_company_client_profile_file(
    account_id: UUID,
    file_id: UUID,
    download: bool = Query(False),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(
        db,
        account_id=account_id,
        company_id=context.company_id,
    )
    assert_branch_scope(context, account.branch_id)
    record = _client_file_or_404(db, account=account, file_id=file_id)

    content = read_file_bytes(record)
    encoded_name = quote(record.original_name, safe="")
    disposition = "attachment" if download else "inline"
    headers = {
        "Content-Disposition": (
            f"{disposition}; filename=\"file\"; filename*=UTF-8''{encoded_name}"
        ),
        "Content-Length": str(len(content)),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "X-File-Reference": record.reference,
    }
    return StreamingResponse(
        BytesIO(content),
        media_type=record.mime_type,
        headers=headers,
    )


@router.get("/{account_id}", response_model=CompanyClientRead)
def get_company_client(
    account_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(
        db,
        account_id=account_id,
        company_id=context.company_id,
    )
    assert_branch_scope(context, account.branch_id)
    return _client_read(account)


@router.post("", response_model=CompanyClientRead, status_code=status.HTTP_201_CREATED)
def open_company_client_account(
    payload: AssistedCompanyClientCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = create_assisted_company_client(db, payload=payload, context=context)
    return _client_read(account)


@router.post(
    "/{account_id}/opening-fee-payment",
    response_model=PaymentTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/{account_id}/cash-opening-fee",
    response_model=PaymentTransactionRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def settle_company_client_opening_fee(
    account_id: UUID,
    payload: CashOpeningFeeSettlementCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Record a verified tenant-company payment to the platform owner.

    The fee is snapshotted when the borrower account is opened. Cash creates a
    physical cash row; other recognised channels require proof evidence.
    Accounting, receipt generation, treasury posting and paid status are
    committed as one auditable operation.
    """
    require_tenant_roles(context, FINANCE_ROLES)
    account = company_client_or_404(
        db,
        account_id=account_id,
        company_id=context.company_id,
    )
    assert_branch_scope(context, account.branch_id)

    amount = Decimal(account.opening_fee_amount or 0)
    if amount <= 0 or account.opening_fee_status == "not_required":
        raise HTTPException(status_code=409, detail="No assisted-opening fee is due for this client account")
    if account.opening_fee_status == "paid":
        raise HTTPException(status_code=409, detail="The assisted-opening fee has already been paid")
    if account.opening_fee_payment_id:
        existing = db.get(PaymentTransaction, account.opening_fee_payment_id)
        if existing and existing.status == PaymentStatus.SUCCEEDED:
            raise HTTPException(status_code=409, detail="The assisted-opening fee has already been paid")

    key = payload.idempotency_key or build_idempotency_key(
        "assisted-opening-fee", account.id, account.opening_fee_amount, payload.payment_method.value
    )
    payment = initiate_payment(
        db,
        provider=PaymentProvider.CASH if payload.payment_method.value == "cash" else PaymentProvider.MANUAL,
        purpose=PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE,
        amount=amount,
        idempotency_key=key,
        initiated_by_user_id=context.user.id,
        company_id=context.company_id,
        borrower_id=account.borrower_id,
        company_borrower_account_id=account.id,
        branch_id=account.branch_id,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes or payload.notes,
    )
    cash_row = payment.cash_transaction
    if cash_row and payload.notes:
        cash_row.notes = payload.notes.strip()
    ensure_payment_receipt(db, payment)
    db.commit()
    db.refresh(payment)
    return payment


def _application_reference() -> str:
    return f"INT-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(4).upper()}"


@router.post(
    "/{account_id}/internal-loan-requests",
    response_model=InternalClientLoanRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_internal_client_loan_request(
    account_id: UUID,
    payload: InternalClientLoanRequestCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    account = company_client_or_404(
        db,
        account_id=account_id,
        company_id=context.company_id,
    )
    if account.status != "active":
        raise HTTPException(
            status_code=409,
            detail="The company client account must be active before an internal loan request is created",
        )
    branch_id = payload.branch_id or account.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)

    if payload.product_id:
        product = (
            db.query(LoanProduct)
            .filter(
                LoanProduct.id == payload.product_id,
                LoanProduct.company_id == context.company_id,
                LoanProduct.is_active.is_(True),
            )
            .first()
        )
        if not product:
            raise HTTPException(status_code=404, detail="The selected active loan product was not found")
        if not (Decimal(product.min_amount) <= payload.requested_amount <= Decimal(product.max_amount)):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Requested amount must be between {product.min_amount} and {product.max_amount} "
                    f"for {product.name}"
                ),
            )
        if not (product.min_term_months <= payload.term_count <= product.max_term_months):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Term must be between {product.min_term_months} and {product.max_term_months} months "
                    f"for {product.name}"
                ),
            )

    active_obligations = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.borrower_id == account.borrower_id,
            ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
        )
        .all()
    )
    external_obligations = (
        db.query(BorrowerDebtObligation)
        .filter(
            BorrowerDebtObligation.borrower_id == account.borrower_id,
            BorrowerDebtObligation.status.in_(("active", "defaulted", "restructured", "unknown")),
            BorrowerDebtObligation.current_balance > 0,
        )
        .order_by(BorrowerDebtObligation.started_on.asc().nullsfirst())
        .all()
    )
    external_balance_total = sum(
        (Decimal(row.current_balance or 0) for row in external_obligations),
        Decimal("0"),
    )
    external_monthly_commitment = sum(
        (Decimal(row.monthly_installment or 0) for row in external_obligations),
        Decimal("0"),
    )
    incomplete_external_schedules = sum(
        1
        for row in external_obligations
        if row.started_on is None
        or Decimal(row.installment_amount or 0) <= 0
        or row.remaining_installments is None
    )
    warning = {
        "active_obligation_count": len(active_obligations),
        "other_company_obligation": any(
            row.company_id != context.company_id for row in active_obligations
        ),
        "external_obligation_count": len(external_obligations),
        "external_schedule_review_required": incomplete_external_schedules > 0,
        "incomplete_external_schedule_count": incomplete_external_schedules,
    }
    borrower = account.borrower
    application = DirectLoanApplication(
        company_id=context.company_id,
        branch_id=branch_id,
        borrower_id=account.borrower_id,
        product_id=payload.product_id,
        application_reference=_application_reference(),
        channel="internal_client_offer",
        requested_amount=payload.requested_amount,
        term_count=payload.term_count,
        repayment_type=payload.repayment_type,
        purpose=payload.purpose,
        first_payment_date=payload.installment_due_dates[0],
        preferred_payment_day=None,
        installment_due_dates=[value.isoformat() for value in payload.installment_due_dates],
        status="submitted",
        affordability_snapshot={
            "monthly_income": str(borrower.monthly_income or 0),
            "existing_loan_total": str(external_balance_total),
            "external_debt_balance_total": str(external_balance_total),
            "external_debt_monthly_commitment": str(external_monthly_commitment),
            "external_debts": [
                {
                    "id": str(row.id),
                    "creditor": row.creditor,
                    "started_on": row.started_on.isoformat() if row.started_on else None,
                    "current_balance": str(row.current_balance or 0),
                    "installment_amount": str(row.installment_amount or 0),
                    "installment_frequency": row.installment_frequency or "monthly",
                    "monthly_installment": str(row.monthly_installment or 0),
                    "remaining_installments": row.remaining_installments,
                    "next_due_date": row.next_due_date.isoformat() if row.next_due_date else None,
                    "status": row.status or "unknown",
                }
                for row in external_obligations
            ],
        },
        credit_warning=warning,
        submitted_at=datetime.now(timezone.utc),
        captured_by_user_id=context.user.id,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return InternalClientLoanRequestRead.model_validate(
        application,
        from_attributes=True,
    )
