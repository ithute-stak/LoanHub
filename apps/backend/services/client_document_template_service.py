from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from core.access_control import TenantContext
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import LoanStatus
from database.models.person import Person
from database.models.user import User
from services.company_client_service import company_client_or_404


CLIENT_LETTER_TEMPLATE_KEYS = {
    "client_confirmation_letter",
    "good_standing_confirmation_letter",
    "paid_up_letter",
    "settlement_letter",
}

LOAN_REQUIRED_TEMPLATE_KEYS = {
    "paid_up_letter",
    "settlement_letter",
}


@dataclass(frozen=True)
class ClientLetterContext:
    values: dict[str, str]
    account: CompanyBorrowerAccount
    loan: ClientCompanyLoan | None


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _money_text(value: Any) -> str:
    return f"LSL {_money(value):,.2f}"


def _display_name(user: User | None) -> str:
    person = getattr(user, "person", None) if user else None
    if person:
        full_name = " ".join(
            part.strip()
            for part in (
                getattr(person, "first_name", None),
                getattr(person, "middle_name", None),
                getattr(person, "last_name", None),
            )
            if part and str(part).strip()
        )
        if full_name:
            return full_name
    return (
        str(getattr(user, "email", "") or "").strip()
        or str(getattr(user, "phone", "") or "").strip()
        or "Authorised representative"
    )


def _client_title(person: Person | None) -> tuple[str, str, str, str]:
    gender = _enum_value(getattr(person, "gender", None)).lower()
    marital = _enum_value(getattr(person, "marital_status", None)).lower()
    if gender == "male":
        return "Mr", "he", "him", "his"
    if gender == "female":
        return ("Mrs" if marital == "married" else "Ms"), "she", "her", "her"
    return "Mx", "they", "them", "their"


def _active_company_loans(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
) -> list[ClientCompanyLoan]:
    active_statuses = (
        LoanStatus.APPROVED,
        LoanStatus.ACTIVE,
        LoanStatus.DEFAULTED,
    )
    return (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.company_id == company_id,
            ClientCompanyLoan.borrower_id == borrower_id,
            ClientCompanyLoan.status.in_(active_statuses),
        )
        .order_by(ClientCompanyLoan.created_at.desc())
        .all()
    )


def _selected_loan_or_404(
    db: Session,
    *,
    context: TenantContext,
    account: CompanyBorrowerAccount,
    loan_id: UUID | None,
) -> ClientCompanyLoan | None:
    if loan_id is None:
        return None
    loan = (
        db.query(ClientCompanyLoan)
        .options(joinedload(ClientCompanyLoan.installments))
        .filter(
            ClientCompanyLoan.id == loan_id,
            ClientCompanyLoan.company_id == context.company_id,
            ClientCompanyLoan.borrower_id == account.borrower_id,
        )
        .first()
    )
    if not loan:
        raise HTTPException(
            status_code=404,
            detail="The selected loan does not belong to this company client.",
        )
    return loan


def _has_current_arrears(loans: list[ClientCompanyLoan]) -> bool:
    return any(bool(getattr(loan, "is_overdue", False)) for loan in loans)


def _require_letter_eligibility(
    *,
    template_key: str,
    selected_loan: ClientCompanyLoan | None,
    current_loans: list[ClientCompanyLoan],
) -> None:
    if template_key in LOAN_REQUIRED_TEMPLATE_KEYS and selected_loan is None:
        raise HTTPException(
            status_code=422,
            detail="Select the loan that this letter relates to.",
        )

    if template_key in {
        "client_confirmation_letter",
        "good_standing_confirmation_letter",
    } and _has_current_arrears(current_loans):
        raise HTTPException(
            status_code=409,
            detail=(
                "LoanHub currently shows arrears for this client. "
                "A no-arrears confirmation cannot be generated until the account is up to date."
            ),
        )

    if template_key == "paid_up_letter":
        assert selected_loan is not None
        open_installments = [
            row
            for row in (selected_loan.installments or [])
            if _enum_value(getattr(row, "status", None)).lower() not in {"paid", "waived"}
            and _money(getattr(row, "total_due", 0)) > _money(getattr(row, "paid_amount", 0))
        ]
        if _money(selected_loan.balance) > 0 or open_installments:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This loan is not fully settled. "
                    "A paid-up letter can only be generated after the ledger balance reaches zero."
                ),
            )

    if template_key == "settlement_letter":
        assert selected_loan is not None
        if _money(selected_loan.balance) <= 0:
            raise HTTPException(
                status_code=409,
                detail="This loan is already settled. Use the Paid-Up Letter template instead.",
            )
        if bool(getattr(selected_loan, "is_overdue", False)):
            raise HTTPException(
                status_code=409,
                detail=(
                    "The selected loan currently has arrears. "
                    "The settlement/no-arrears letter cannot be generated until arrears are resolved."
                ),
            )


def build_client_letter_context(
    db: Session,
    *,
    context: TenantContext,
    template_key: str,
    company_client_id: UUID | None,
    loan_id: UUID | None,
    signer_name: str | None,
    signer_title: str | None,
    company_bank_accounts: str | None,
) -> ClientLetterContext | None:
    if template_key not in CLIENT_LETTER_TEMPLATE_KEYS:
        return None
    if not context.company_id:
        raise HTTPException(
            status_code=403,
            detail="Customer letters require an active lending company.",
        )
    if company_client_id is None:
        raise HTTPException(
            status_code=422,
            detail="Select the customer for this letter.",
        )

    account = company_client_or_404(
        db,
        account_id=company_client_id,
        company_id=context.company_id,
    )
    borrower = account.borrower
    user = borrower.user if borrower else None
    person = user.person if user else None
    company = account.company
    selected_loan = _selected_loan_or_404(
        db,
        context=context,
        account=account,
        loan_id=loan_id,
    )
    current_loans = _active_company_loans(
        db,
        company_id=context.company_id,
        borrower_id=account.borrower_id,
    )
    _require_letter_eligibility(
        template_key=template_key,
        selected_loan=selected_loan,
        current_loans=current_loans,
    )

    client_name = _display_name(user)
    client_title, subject_pronoun, object_pronoun, possessive_pronoun = _client_title(person)
    identity = (
        str(getattr(person, "national_id", "") or "").strip()
        or str(getattr(person, "passport_number", "") or "").strip()
        or "Not recorded"
    )
    role = _enum_value(getattr(context.user, "role", None)).replace("_", " ").title()
    today = date.today()
    values = {
        "date": today.strftime("%d %B %Y"),
        "client_name": client_name,
        "client_title": client_title,
        "client_national_id": identity,
        "subject_pronoun": subject_pronoun,
        "object_pronoun": object_pronoun,
        "possessive_pronoun": possessive_pronoun,
        "company_name": str(getattr(company, "name", None) or "the lending company"),
        "company_phone": str(getattr(company, "phone", None) or "").strip(),
        "company_email": str(getattr(company, "email", None) or "").strip(),
        "company_address": str(getattr(company, "address", None) or "").strip(),
        "account_reference": str(getattr(account, "account_reference", None) or "").strip(),
        "signer_name": (signer_name or "").strip() or _display_name(context.user),
        "signer_title": (signer_title or "").strip() or role or "Authorised representative",
        "company_bank_accounts": (company_bank_accounts or "").strip() or "[Insert company bank account details]",
        "credit_check_explanation": (
            "If an earlier amount still appears on an external credit check, "
            "it may reflect a reporting or synchronisation delay. "
            "Please contact the company directly if verification is required."
        ),
        "loan_reference": "",
        "loan_balance": "LSL 0.00",
        "loan_installment_amount": "LSL 0.00",
        "loan_total_repayable": "LSL 0.00",
    }
    if selected_loan:
        values.update(
            {
                "loan_reference": str(selected_loan.loan_reference or ""),
                "loan_balance": _money_text(selected_loan.balance),
                "loan_installment_amount": _money_text(selected_loan.installment_amount),
                "loan_total_repayable": _money_text(selected_loan.total_repayable),
            }
        )

    return ClientLetterContext(values=values, account=account, loan=selected_loan)
