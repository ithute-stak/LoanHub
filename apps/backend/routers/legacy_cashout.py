from __future__ import annotations

import calendar
import hashlib
import json
import re
import secrets
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from core.security import hash_password
from database.models.audit_log import AuditLog
from database.models.borrower import Borrower
from database.models.borrower_contact import BorrowerContact
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import (
    EmploymentStatus,
    InstallmentStatus,
    LoanStatus,
    RepaymentType,
    RiskLevel,
    UserRole,
)
from database.models.legacy_loan_capture import LegacyLoanCapture
from database.models.origination import BorrowerBankAccount, LoanContract
from database.models.person import Person
from database.models.repayment import RepaymentInstallment
from database.models.user import User
from services.credential_service import encrypt_credential
from database.schemas.legacy_cashout import (
    LegacyCashoutCaptureCreate,
    LegacyCashoutCaptureRead,
    LegacyCashoutReviewCreate,
    normalise_legacy_capture_status,
)
from database.session import get_db


router = APIRouter(prefix="/legacy-cashout-register", tags=["Legacy Cash-out Register"])

_CAPTURE_ROLES = COMPANY_MANAGEMENT_ROLES | LENDING_ROLES
_POST_ROLES = COMPANY_MANAGEMENT_ROLES
MONEY_QUANTUM = Decimal("0.01")


def _amount(value: Decimal | int | float | None) -> Decimal:
    return Decimal(value or 0).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _tenant_company_id(context: TenantContext) -> UUID:
    if context.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Select an active loan company before using the legacy cash-out register",
        )
    return context.company_id


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _capture_values(payload: LegacyCashoutCaptureCreate) -> dict:
    """Map a validated request into storage fields without ever returning a bank number."""

    identity = payload.identity_number
    return {
        "folio_number": payload.folio_number,
        "cashout_book_number": _clean(payload.cashout_book_number),
        "page_number": _clean(payload.page_number),
        "entry_number": _clean(payload.entry_number),
        "book_date": payload.loan_date,
        "names": _clean(payload.first_names),
        "surname": _clean(payload.surname),
        "national_id": identity if payload.identity_type == "national_id" else None,
        "passport_number": identity if payload.identity_type == "passport" else None,
        "passport_expiry_date": payload.passport_expiry_date if payload.identity_type == "passport" else None,
        "residential_address": _clean(payload.residential_address),
        "postal_address": _clean(payload.postal_address),
        "employer": _clean(payload.employer),
        "occupation": _clean(payload.occupation),
        "net_pay": payload.net_salary,
        "cell_phone": _clean(payload.cell_phone),
        "home_phone": _clean(payload.home_phone),
        "work_phone": _clean(payload.work_phone),
        "next_of_kin_name": _clean(payload.emergency_name),
        "next_of_kin_contact": _clean(payload.emergency_cell_phone),
        "next_of_kin_work_phone": _clean(payload.emergency_work_phone),
        "next_of_kin_relationship": _clean(payload.emergency_relationship),
        "borrowed_amount": payload.amount_taken,
        "total_repayable": payload.total_repayable,
        "amount_paid": payload.amount_paid,
        "installment_count": payload.installment_count,
        "installment_amount": payload.installment_amount,
        "repayment_type": payload.repayment_type.value,
        "calculation_method": _clean(payload.calculator_method),
        "banking_info": {
            "bank_name": payload.bank_name.strip(),
            "bank_account_holder": payload.bank_account_holder.strip(),
            "bank_branch_name": _clean(payload.bank_branch_name),
            "bank_branch_code": _clean(payload.bank_branch_code),
            "bank_account_type": payload.bank_account_type.strip(),
        },
        "bank_account_number_encrypted": encrypt_credential(payload.bank_account_number),
        "bank_account_number_last4": payload.bank_account_number[-4:],
        "paper_snapshot": {
            "source": "cashout_book",
            "captured_identity_type": payload.identity_type,
            "identity_number": identity,
            "bank_account_number_last4": payload.bank_account_number[-4:],
            "passport_expiry_date": payload.passport_expiry_date.isoformat() if payload.passport_expiry_date else None,
            "calculator_snapshot": payload.calculator_snapshot,
            "capture_notes": _clean(payload.capture_notes),
            "captured_amount_taken": str(payload.amount_taken),
            "captured_total_repayable": str(payload.total_repayable),
            "captured_amount_paid": str(payload.amount_paid),
        },
    }


def _add_months(value: date, months: int) -> date:
    target = value.month - 1 + months
    year = value.year + target // 12
    month = target % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _next_due_date(loan_date: date, number: int, repayment_type: str) -> date:
    if repayment_type == RepaymentType.DAILY.value:
        return loan_date + timedelta(days=number)
    if repayment_type == RepaymentType.WEEKLY.value:
        return loan_date + timedelta(days=number * 7)
    if repayment_type == RepaymentType.CUSTOM.value:
        # A cash-out book generally records a single periodic payment figure.
        # Treat an unspecified custom cadence as monthly until a reviewer
        # corrects it; the original method stays in the immutable snapshot.
        return _add_months(loan_date, number)
    return _add_months(loan_date, number)


def _account_reference(db: Session, *, folio: str) -> str:
    stem = re.sub(r"[^A-Z0-9]+", "-", folio.upper()).strip("-")[:30] or "ENTRY"
    for _ in range(20):
        candidate = f"LEG-{stem}-{secrets.token_hex(3).upper()}"
        if not db.query(CompanyBorrowerAccount.id).filter(
            CompanyBorrowerAccount.account_reference == candidate
        ).first():
            return candidate
    raise HTTPException(status_code=503, detail="Could not reserve a legacy client account reference")


def _loan_reference(db: Session, *, folio: str) -> str:
    stem = re.sub(r"[^A-Z0-9]+", "-", folio.upper()).strip("-")[:30] or "ENTRY"
    for _ in range(20):
        candidate = f"LEG-{stem}-{secrets.token_hex(3).upper()}"
        if not db.query(ClientCompanyLoan.id).filter(
            ClientCompanyLoan.loan_reference == candidate
        ).first():
            return candidate
    raise HTTPException(status_code=503, detail="Could not reserve a legacy loan reference")


def _capture_or_404(
    db: Session,
    *,
    context: TenantContext,
    capture_id: UUID,
) -> LegacyLoanCapture:
    row = (
        db.query(LegacyLoanCapture)
        .filter(
            LegacyLoanCapture.id == capture_id,
            LegacyLoanCapture.company_id == _tenant_company_id(context),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Legacy cash-out entry was not found")
    assert_branch_scope(context, row.branch_id)
    return row


def _read(row: LegacyLoanCapture, loan: ClientCompanyLoan | None = None) -> LegacyCashoutCaptureRead:
    identity_number = row.national_id or row.passport_number
    identity_type = "national_id" if row.national_id else ("passport" if row.passport_number else None)
    details = row.banking_info or {}
    snapshot = row.paper_snapshot or {}
    total_repayable = _amount(row.total_repayable or row.borrowed_amount)
    amount_paid = _amount(row.amount_paid)
    return LegacyCashoutCaptureRead(
        id=row.id,
        folio_number=row.folio_number,
        cashout_book_number=row.cashout_book_number,
        page_number=row.page_number,
        entry_number=row.entry_number,
        loan_date=row.book_date,
        borrower_name=" ".join(part for part in [row.names, row.surname] if part).strip() or "Unspecified borrower",
        first_names=row.names,
        surname=row.surname,
        identity_number=identity_number,
        identity_type=identity_type,
        passport_expiry_date=row.passport_expiry_date if identity_type == "passport" else None,
        residential_address=row.residential_address,
        postal_address=row.postal_address,
        employer=row.employer,
        occupation=row.occupation,
        net_salary=row.net_pay,
        cell_phone=row.cell_phone,
        home_phone=row.home_phone,
        work_phone=row.work_phone,
        emergency_name=row.next_of_kin_name,
        emergency_cell_phone=row.next_of_kin_contact,
        emergency_work_phone=row.next_of_kin_work_phone,
        emergency_relationship=row.next_of_kin_relationship,
        bank_name=details.get("bank_name"),
        bank_account_holder=details.get("bank_account_holder"),
        bank_branch_name=details.get("bank_branch_name"),
        bank_branch_code=details.get("bank_branch_code"),
        bank_account_type=details.get("bank_account_type"),
        bank_account_last4=row.bank_account_number_last4,
        has_bank_account_number=bool(row.bank_account_number_encrypted),
        amount_taken=_amount(row.borrowed_amount),
        total_repayable=total_repayable,
        amount_paid=amount_paid,
        balance=max(total_repayable - amount_paid, Decimal("0.00")),
        installment_count=int(row.installment_count or 0),
        installment_amount=_amount(row.installment_amount),
        repayment_type=row.repayment_type or RepaymentType.MONTHLY.value,
        calculator_method=row.calculation_method,
        calculator_snapshot=snapshot.get("calculator_snapshot") if isinstance(snapshot.get("calculator_snapshot"), dict) else {},
        capture_notes=snapshot.get("capture_notes"),
        status=normalise_legacy_capture_status(row.status),
        review_notes=row.review_notes,
        loan_reference=loan.loan_reference if loan else None,
        borrower_profile_ready=bool(row.borrower_id and row.company_borrower_account_id),
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
        converted_at=row.converted_at,
    )

def _audit(
    db: Session,
    *,
    context: TenantContext,
    capture: LegacyLoanCapture,
    action: str,
    description: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=context.user.id,
            company_id=capture.company_id,
            branch_id=capture.branch_id,
            action=action,
            table_name=LegacyLoanCapture.__tablename__,
            entity_type="legacy_cashout_capture",
            record_id=capture.id,
            description=description,
            actor_role=context.role.value,
            before_data=before or {},
            after_data=after or {},
            changed_fields=[],
            event_data={
                "folio_number": capture.folio_number,
                "cashout_book_number": capture.cashout_book_number,
                "page_number": capture.page_number,
            },
        )
    )


def _posting_missing_fields(capture: LegacyLoanCapture) -> list[str]:
    details = capture.banking_info or {}
    required = {
        "borrower first names": capture.names,
        "borrower surname": capture.surname,
        "national ID or passport number": capture.national_id or capture.passport_number,
        "borrower cell number": capture.cell_phone,
        "amount taken": capture.borrowed_amount and Decimal(capture.borrowed_amount) > 0,
        "total repayable": capture.total_repayable and Decimal(capture.total_repayable) > 0,
        "number of installments": capture.installment_count and int(capture.installment_count) > 0,
        "installment amount": capture.installment_amount and Decimal(capture.installment_amount) > 0,
        "bank name": details.get("bank_name"),
        "bank account holder": details.get("bank_account_holder"),
        "bank account number": capture.bank_account_number_encrypted,
    }
    return [label for label, value in required.items() if not value]


def _ensure_borrower_bank_account(
    db: Session,
    *,
    capture: LegacyLoanCapture,
    borrower: Borrower,
) -> None:
    details = capture.banking_info or {}
    bank_name = _clean(details.get("bank_name"))
    account_holder = _clean(details.get("bank_account_holder"))
    if not bank_name or not account_holder or not capture.bank_account_number_encrypted:
        raise HTTPException(status_code=422, detail="Complete secure banking details before posting")

    existing = (
        db.query(BorrowerBankAccount)
        .filter(
            BorrowerBankAccount.borrower_id == borrower.id,
            BorrowerBankAccount.bank_name == bank_name,
            BorrowerBankAccount.account_number_last4 == capture.bank_account_number_last4,
        )
        .first()
    )
    if existing is None:
        db.add(
            BorrowerBankAccount(
                company_id=capture.company_id,
                borrower_id=borrower.id,
                account_holder=account_holder,
                bank_name=bank_name,
                branch_name=_clean(details.get("bank_branch_name")),
                branch_code=_clean(details.get("bank_branch_code")),
                account_type=_clean(details.get("bank_account_type")) or "savings",
                currency="LSL",
                account_number_encrypted=capture.bank_account_number_encrypted,
                account_number_last4=capture.bank_account_number_last4,
                salary_account=True,
                verification_status="unverified",
            )
        )


def _find_or_create_borrower(
    db: Session,
    *,
    capture: LegacyLoanCapture,
) -> Borrower:
    person_query = db.query(Person)
    person = (
        person_query.filter(Person.national_id == capture.national_id).first()
        if capture.national_id
        else person_query.filter(Person.passport_number == capture.passport_number).first()
    )

    if person is not None:
        user = db.get(User, person.user_id)
        borrower = db.query(Borrower).filter(Borrower.user_id == person.user_id).first()
        if borrower is not None:
            return borrower
        if user is None or user.role != UserRole.BORROWER:
            raise HTTPException(
                status_code=409,
                detail="This identity belongs to an existing non-borrower account and must be resolved before posting",
            )
        borrower = Borrower(
            user_id=user.id,
            employment_status=EmploymentStatus.EMPLOYED if (capture.employer or capture.occupation) else EmploymentStatus.UNEMPLOYED,
            employer_name=capture.employer,
            job_title=capture.occupation,
            monthly_income=_amount(capture.net_pay),
            net_monthly_income=_amount(capture.net_pay),
        )
        db.add(borrower)
        db.flush()
        return borrower

    phone_owner = db.query(User).filter(User.phone == capture.cell_phone).first()
    if phone_owner is not None:
        raise HTTPException(
            status_code=409,
            detail="This mobile number already belongs to another LoanHub account; resolve the borrower identity before posting",
        )

    user = User(
        phone=capture.cell_phone,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=UserRole.BORROWER,
        is_active=False,
        is_verified=False,
        must_change_password=True,
    )
    db.add(user)
    db.flush()

    person = Person(
        user_id=user.id,
        first_name=(capture.names or "Unknown").split()[0],
        middle_name=" ".join((capture.names or "").split()[1:]) or None,
        last_name=capture.surname or "Unknown",
        national_id=capture.national_id,
        passport_number=capture.passport_number,
        date_of_birth=capture.date_of_birth,
        physical_address=capture.residential_address,
    )
    borrower = Borrower(
        user_id=user.id,
        employment_status=EmploymentStatus.EMPLOYED if (capture.employer or capture.occupation) else EmploymentStatus.UNEMPLOYED,
        employer_name=capture.employer,
        job_title=capture.occupation,
        monthly_income=_amount(capture.net_pay),
        net_monthly_income=_amount(capture.net_pay),
        consent_to_share_profile=False,
        consent_to_share_documents=False,
        consent_to_credit_checks=False,
    )
    db.add_all([person, borrower])
    db.flush()
    return borrower


def _ensure_company_account(
    db: Session,
    *,
    capture: LegacyLoanCapture,
    borrower: Borrower,
    user_id: UUID,
) -> CompanyBorrowerAccount:
    account = (
        db.query(CompanyBorrowerAccount)
        .filter(
            CompanyBorrowerAccount.company_id == capture.company_id,
            CompanyBorrowerAccount.borrower_id == borrower.id,
        )
        .first()
    )
    if account:
        return account

    account = CompanyBorrowerAccount(
        company_id=capture.company_id,
        branch_id=capture.branch_id,
        borrower_id=borrower.id,
        opened_by_user_id=user_id,
        account_reference=_account_reference(db, folio=capture.folio_number),
        source="legacy_cashout",
        status="active",
        opening_fee_amount=Decimal("0"),
        opening_fee_currency="LSL",
        opening_fee_status="not_required",
    )
    db.add(account)
    db.flush()
    return account


def _add_authorised_contact(
    db: Session,
    *,
    borrower_id: UUID,
    full_name: str,
    relationship: str,
    phone: str | None,
) -> None:
    phone = _clean(phone)
    if not phone:
        return
    exists = db.query(BorrowerContact.id).filter(
        BorrowerContact.borrower_id == borrower_id,
        BorrowerContact.phone == phone,
    ).first()
    if not exists:
        db.add(
            BorrowerContact(
                borrower_id=borrower_id,
                full_name=full_name,
                relationship=relationship,
                phone=phone,
                is_primary=False,
                is_call_permitted=True,
            )
        )


def _calculator_schedule_rows(
    calculator_snapshot: dict | None,
    *,
    total_repayable: Decimal,
    installment_count: int,
) -> list[dict]:
    """Return a validated official calculator schedule, or no rows for old records."""

    rows = (calculator_snapshot or {}).get("schedule")
    if not isinstance(rows, list) or len(rows) != installment_count:
        return []

    normalised: list[dict] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            return []
        try:
            due_date = date.fromisoformat(str(row.get("due_date", ""))[:10])
        except ValueError:
            return []

        total_due = _amount(row.get("total_due"))
        if total_due <= 0:
            return []
        normalised.append({
            "number": int(row.get("installment_number") or index),
            "due_date": due_date,
            "principal_due": _amount(row.get("principal_due")),
            "interest_due": _amount(row.get("interest_due")),
            "fee_due": _amount(row.get("fee_due")),
            "total_due": total_due,
        })

    normalised.sort(key=lambda row: row["number"])
    schedule_total = sum((row["total_due"] for row in normalised), Decimal("0"))
    if abs(_amount(schedule_total) - _amount(total_repayable)) > Decimal("0.02"):
        return []
    return normalised


def _create_historical_schedule(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    loan_date: date,
    repayment_type: str,
    total_repayable: Decimal,
    principal: Decimal,
    amount_paid: Decimal,
    installment_count: int,
    calculator_snapshot: dict | None = None,
) -> bool:
    """Create the official schedule and allocate historic payments oldest-first.

    Historical cash-book payments affect only the opening balance and installment
    status. They never create a PaymentTransaction, CashTransaction or receipt.
    Old entries without a calculation snapshot use the legacy equal-split fallback.
    """

    total_repayable = _amount(total_repayable)
    principal = _amount(principal)
    calculated_rows = _calculator_schedule_rows(
        calculator_snapshot,
        total_repayable=total_repayable,
        installment_count=installment_count,
    )
    if calculated_rows:
        schedule_rows = calculated_rows
    else:
        remaining_due = total_repayable
        remaining_principal = principal
        base_due = (total_repayable / installment_count).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        schedule_rows = []
        for number in range(1, installment_count + 1):
            total_due = base_due if number < installment_count else _amount(remaining_due)
            remaining_due = _amount(remaining_due - total_due)
            principal_due = min(total_due, remaining_principal)
            remaining_principal = _amount(remaining_principal - principal_due)
            schedule_rows.append({
                "number": number,
                "due_date": _next_due_date(loan_date, number, repayment_type),
                "principal_due": principal_due,
                "interest_due": _amount(total_due - principal_due),
                "fee_due": Decimal("0"),
                "total_due": total_due,
            })

    historical_paid = _amount(amount_paid)
    is_overdue = False
    for row in schedule_rows:
        due = row["total_due"]
        paid_amount = min(due, historical_paid)
        historical_paid = _amount(historical_paid - paid_amount)

        if paid_amount >= due:
            installment_status = InstallmentStatus.PAID
        elif paid_amount > 0:
            installment_status = InstallmentStatus.PARTIALLY_PAID
        elif row["due_date"] < date.today():
            installment_status = InstallmentStatus.OVERDUE
            is_overdue = True
        else:
            installment_status = InstallmentStatus.PENDING

        db.add(
            RepaymentInstallment(
                loan_id=loan.id,
                installment_number=row["number"],
                due_date=row["due_date"],
                principal_due=row["principal_due"],
                interest_due=row["interest_due"],
                fee_due=row["fee_due"],
                total_due=due,
                paid_amount=paid_amount,
                status=installment_status,
                # The book confirms a total paid, not each payment date.
                paid_at=None,
            )
        )
    return is_overdue

@router.get("", response_model=list[LegacyCashoutCaptureRead])
def list_legacy_cashout_entries(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    require_tenant_roles(context, _CAPTURE_ROLES)
    company_id = _tenant_company_id(context)
    query = db.query(LegacyLoanCapture).filter(LegacyLoanCapture.company_id == company_id)
    if status_filter:
        query = query.filter(LegacyLoanCapture.status == status_filter.strip().lower())
    rows = query.order_by(LegacyLoanCapture.created_at.desc()).limit(limit).all()
    loans = {
        loan.id: loan
        for loan in db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.id.in_([row.loan_id for row in rows if row.loan_id is not None]))
        .all()
    } if rows else {}
    return [_read(row, loans.get(row.loan_id)) for row in rows]


@router.post("", response_model=LegacyCashoutCaptureRead, status_code=status.HTTP_201_CREATED)
def capture_legacy_cashout_entry(
    payload: LegacyCashoutCaptureCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    require_tenant_roles(context, _CAPTURE_ROLES)
    company_id = _tenant_company_id(context)
    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)

    capture = LegacyLoanCapture(
        company_id=company_id,
        branch_id=branch_id,
        captured_by_user_id=context.user.id,
        conversion_data={},
        status="draft",
        **_capture_values(payload),
    )
    db.add(capture)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This company already has a legacy cash-out entry with that folio number",
        ) from error

    _audit(
        db,
        context=context,
        capture=capture,
        action="legacy_cashout.captured",
        description="Captured a cash-out book entry for review",
        after={"status": "draft"},
    )
    db.commit()
    db.refresh(capture)
    return _read(capture)


@router.put("/{capture_id}", response_model=LegacyCashoutCaptureRead)
def update_legacy_cashout_entry(
    capture_id: UUID,
    payload: LegacyCashoutCaptureCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Continue or correct a draft without exposing the encrypted bank account number."""

    require_tenant_roles(context, _CAPTURE_ROLES)
    capture = _capture_or_404(db, context=context, capture_id=capture_id)
    if capture.status not in {"draft", "returned"}:
        raise HTTPException(
            status_code=409,
            detail="Only a draft or returned cash-out entry can be changed",
        )

    branch_id = payload.branch_id or capture.branch_id
    assert_branch_scope(context, branch_id)
    before = {
        "status": capture.status,
        "folio_number": capture.folio_number,
        "loan_date": capture.book_date.isoformat() if capture.book_date else None,
        "bank_account_last4": capture.bank_account_number_last4,
    }
    for field, value in _capture_values(payload).items():
        setattr(capture, field, value)
    capture.branch_id = branch_id
    capture.status = "draft"
    capture.review_notes = None
    capture.reviewed_by_user_id = None
    capture.reviewed_at = None

    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This company already has a legacy cash-out entry with that folio number",
        ) from error

    _audit(
        db,
        context=context,
        capture=capture,
        action="legacy_cashout.updated",
        description="Continued or corrected a legacy cash-out draft",
        before=before,
        after={
            "status": capture.status,
            "folio_number": capture.folio_number,
            "loan_date": capture.book_date.isoformat() if capture.book_date else None,
            "bank_account_last4": capture.bank_account_number_last4,
        },
    )
    db.commit()
    db.refresh(capture)
    return _read(capture)


@router.post("/{capture_id}/review", response_model=LegacyCashoutCaptureRead)
def review_legacy_cashout_entry(
    capture_id: UUID,
    payload: LegacyCashoutReviewCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    require_tenant_roles(context, _CAPTURE_ROLES)
    capture = _capture_or_404(db, context=context, capture_id=capture_id)
    if capture.status == "posted":
        raise HTTPException(status_code=409, detail="A posted cash-out entry cannot be reviewed again")

    if payload.approve_for_posting:
        missing = _posting_missing_fields(capture)
        if missing:
            raise HTTPException(
                status_code=422,
                detail="Complete before approval: " + ", ".join(missing),
            )

    before_status = capture.status
    capture.status = "reviewed" if payload.approve_for_posting else "returned"
    capture.review_notes = _clean(payload.notes)
    capture.reviewed_by_user_id = context.user.id
    capture.reviewed_at = datetime.now(timezone.utc)
    _audit(
        db,
        context=context,
        capture=capture,
        action="legacy_cashout.reviewed",
        description="Approved legacy entry for posting" if payload.approve_for_posting else "Returned legacy entry for correction",
        before={"status": before_status},
        after={"status": capture.status},
    )
    db.commit()
    db.refresh(capture)
    return _read(capture)


@router.post("/{capture_id}/post", response_model=LegacyCashoutCaptureRead)
def post_legacy_cashout_entry(
    capture_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    require_tenant_roles(context, _POST_ROLES)
    capture = _capture_or_404(db, context=context, capture_id=capture_id)
    if capture.status != "reviewed":
        raise HTTPException(status_code=422, detail="Only a reviewed cash-out entry can be posted")
    if capture.loan_id is not None:
        raise HTTPException(status_code=409, detail="This cash-out entry has already been posted")
    if not capture.book_date:
        raise HTTPException(status_code=422, detail="Loan date is required before posting")
    if not capture.cell_phone:
        raise HTTPException(status_code=422, detail="A borrower cell number is required before posting")

    missing = _posting_missing_fields(capture)
    if missing:
        raise HTTPException(
            status_code=422,
            detail="Complete before posting: " + ", ".join(missing),
        )

    total_repayable = _amount(capture.total_repayable or capture.borrowed_amount)
    amount_paid = _amount(capture.amount_paid)
    principal = _amount(capture.borrowed_amount)
    installment_count = int(capture.installment_count or 0)
    if total_repayable <= 0 or principal <= 0 or installment_count <= 0:
        raise HTTPException(status_code=422, detail="Complete the loan amounts and number of installments before posting")
    if amount_paid > total_repayable:
        raise HTTPException(status_code=422, detail="Amount paid cannot exceed the recorded total repayable")

    borrower = _find_or_create_borrower(db, capture=capture)
    _ensure_borrower_bank_account(db, capture=capture, borrower=borrower)
    account = _ensure_company_account(
        db,
        capture=capture,
        borrower=borrower,
        user_id=context.user.id,
    )
    borrower_name = " ".join(part for part in [capture.names, capture.surname] if part).strip() or "Borrower"
    _add_authorised_contact(
        db,
        borrower_id=borrower.id,
        full_name=borrower_name,
        relationship="home phone",
        phone=capture.home_phone,
    )
    _add_authorised_contact(
        db,
        borrower_id=borrower.id,
        full_name=borrower_name,
        relationship="work phone",
        phone=capture.work_phone,
    )
    _add_authorised_contact(
        db,
        borrower_id=borrower.id,
        full_name=capture.next_of_kin_name or "Emergency contact",
        relationship=capture.next_of_kin_relationship or "emergency contact",
        phone=capture.next_of_kin_contact,
    )
    _add_authorised_contact(
        db,
        borrower_id=borrower.id,
        full_name=capture.next_of_kin_name or "Emergency contact",
        relationship=f"{capture.next_of_kin_relationship or 'emergency contact'} work",
        phone=capture.next_of_kin_work_phone,
    )

    repayment_type = capture.repayment_type or RepaymentType.MONTHLY.value
    calculator_snapshot = (capture.paper_snapshot or {}).get("calculator_snapshot", {})
    calculator_snapshot = calculator_snapshot if isinstance(calculator_snapshot, dict) else {}
    calculated_rows = _calculator_schedule_rows(
        calculator_snapshot,
        total_repayable=total_repayable,
        installment_count=installment_count,
    )
    first_payment_due = calculated_rows[0]["due_date"] if calculated_rows else _next_due_date(capture.book_date, 1, repayment_type)
    maturity_date = calculated_rows[-1]["due_date"] if calculated_rows else _next_due_date(capture.book_date, installment_count, repayment_type)
    calculation_rate = _amount(calculator_snapshot.get("rate_percent"))
    calculation_fee = _amount(calculator_snapshot.get("processing_fee"))
    calculation_method = _clean(str(calculator_snapshot.get("method") or "")) or capture.calculation_method or "legacy_cashout_book"
    balance = _amount(total_repayable - amount_paid)
    loan = ClientCompanyLoan(
        company_id=capture.company_id,
        branch_id=capture.branch_id,
        borrower_id=borrower.id,
        loan_reference=_loan_reference(db, folio=capture.folio_number),
        origination_channel="legacy_cashout",
        principal_amount=principal,
        interest_rate=calculation_rate,
        processing_fee=calculation_fee,
        total_repayable=total_repayable,
        repayment_type=RepaymentType(repayment_type),
        repayment_period=installment_count,
        installment_amount=_amount(capture.installment_amount),
        calculation_method=calculation_method,
        calculation_breakdown={
            "source": "legacy_cashout_book",
            "folio_number": capture.folio_number,
            "cashout_book_number": capture.cashout_book_number,
            "page_number": capture.page_number,
            "entry_number": capture.entry_number,
            "historical_calculator_method": calculation_method,
            "historical_calculator_snapshot": calculator_snapshot,
            "historical_payment_allocation": "opening_balance_only_no_loanhub_cash_transaction",
            "requires_normal_loan_review": True,
        },
        approved_at=datetime.combine(capture.book_date, time.min),
        disbursed_at=datetime.combine(capture.book_date, time.min),
        first_payment_due=first_payment_due,
        preferred_payment_day=capture.book_date.day,
        maturity_date=maturity_date,
        amount_paid=amount_paid,
        balance=balance,
        status=LoanStatus.COMPLETED if balance == 0 else LoanStatus.ACTIVE,
        risk_level=RiskLevel.LOW,
        approved_by_user_id=context.user.id,
        disbursed_by_user_id=None,
    )
    db.add(loan)
    db.flush()

    historical_terms = {
        "source": "legacy_cashout_book",
        "historical_record": True,
        "folio_number": capture.folio_number,
        "cashout_book_number": capture.cashout_book_number,
        "page_number": capture.page_number,
        "loan_date": capture.book_date.isoformat(),
        "principal_amount": str(principal),
        "total_repayable": str(total_repayable),
        "amount_paid_at_migration": str(amount_paid),
        "installment_count": installment_count,
        "repayment_type": repayment_type,
        "calculator_method": calculation_method,
        "calculator_snapshot": calculator_snapshot,
        "contract_requires_post_migration_verification": True,
    }
    db.add(
        LoanContract(
            company_id=capture.company_id,
            borrower_id=borrower.id,
            loan_id=loan.id,
            contract_number="LEG-CONTRACT-" + loan.loan_reference,
            status="historical_record",
            terms_snapshot=historical_terms,
            contract_hash=hashlib.sha256(
                json.dumps(historical_terms, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )
    )

    schedule_is_overdue = _create_historical_schedule(
        db,
        loan=loan,
        loan_date=capture.book_date,
        repayment_type=repayment_type,
        total_repayable=total_repayable,
        principal=principal,
        amount_paid=amount_paid,
        installment_count=installment_count,
        calculator_snapshot=calculator_snapshot,
    )
    loan.is_overdue = False if balance == 0 else schedule_is_overdue

    capture.borrower_id = borrower.id
    capture.company_borrower_account_id = account.id
    capture.loan_id = loan.id
    capture.posted_by_user_id = context.user.id
    capture.status = "posted"
    capture.converted_at = datetime.now(timezone.utc)
    capture.conversion_data = {
        **(capture.conversion_data or {}),
        "conversion_type": "historical_opening_balance",
        "loan_reference": loan.loan_reference,
        "borrower_profile_created_or_linked": True,
        "company_account_reference": account.account_reference,
        "normal_loan_review_required": True,
        "payment_transactions_created": 0,
        "contract_number": "LEG-CONTRACT-" + loan.loan_reference,
        "contract_status": "historical_record",
    }
    _audit(
        db,
        context=context,
        capture=capture,
        action="legacy_cashout.posted",
        description="Posted historic cash-out entry as a normal loan opening balance",
        before={"status": "reviewed"},
        after={"status": "posted", "loan_reference": loan.loan_reference},
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A conflicting borrower, client account, or loan record prevented this entry from being posted",
        ) from error
    db.refresh(capture)
    return _read(capture, loan)
