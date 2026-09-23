from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus


_MONEY = Decimal("0.01")
_COLLECTION_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}
_VISIBLE_STATUSES = {LoanStatus.APPROVED, LoanStatus.ACTIVE, LoanStatus.DEFAULTED}


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _money(value: object) -> Decimal:
    return _decimal(value).quantize(_MONEY)


def _status_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "")


def calculate_collection_proposal(*, outstanding: object, affordability: object) -> dict[str, Any]:
    """Calculate a simple current-balance/current-capacity collection proposal.

    This is intentionally not a new-credit decision or a replacement for the
    loan amortisation engine. It answers only: if the current positive LoanHub
    balance were collected using the current positive CDAS available amount,
    what monthly amount and approximate whole-month period would that imply?
    """
    balance = max(_money(outstanding), Decimal("0.00"))
    available = max(_money(affordability), Decimal("0.00"))
    suggested = min(balance, available) if balance > 0 and available > 0 else Decimal("0.00")

    months: int | None = None
    if suggested > 0:
        months = int((balance / suggested).to_integral_value(rounding=ROUND_CEILING))

    return {
        "total_outstanding": float(balance),
        "available_affordability": float(available),
        "suggested_monthly_deduction": float(suggested),
        "estimated_collection_months": months,
        "can_add_deduction": bool(balance > 0 and available > 0),
        "calculation_basis": "CURRENT_LOANHUB_BALANCE_DIVIDED_BY_CURRENT_CDAS_AVAILABLE_DEDUCTION",
        "warning": (
            "Collection proposal only. Registration or modification must still pass LoanHub loan terms, borrower consent, role controls and the official CDAS lifecycle."
        ),
    }


def build_borrower_loan_intelligence(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
    affordability: object,
) -> dict[str, Any]:
    loans = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.company_id == company_id,
            ClientCompanyLoan.borrower_id == borrower_id,
            ClientCompanyLoan.status.in_(_VISIBLE_STATUSES),
        )
        .order_by(ClientCompanyLoan.created_at.desc())
        .all()
    )

    serialized: list[dict[str, Any]] = []
    collection_balance = Decimal("0.00")
    approved_not_active_balance = Decimal("0.00")
    contractual_monthly = Decimal("0.00")

    for loan in loans:
        balance = max(_money(loan.balance), Decimal("0.00"))
        installment = max(_money(loan.installment_amount), Decimal("0.00"))
        if loan.status in _COLLECTION_STATUSES:
            collection_balance += balance
            contractual_monthly += installment
        elif loan.status == LoanStatus.APPROVED:
            approved_not_active_balance += balance

        serialized.append(
            {
                "loan_id": str(loan.id),
                "loan_reference": loan.loan_reference,
                "status": _status_value(loan.status),
                "balance": float(balance),
                "amount_paid": float(_money(loan.amount_paid)),
                "principal_amount": float(_money(loan.principal_amount)),
                "installment_amount": float(installment),
                "repayment_period": int(loan.repayment_period or 0),
                "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else None,
                "is_overdue": bool(loan.is_overdue),
                "eligible_existing_obligation": bool(loan.status in _COLLECTION_STATUSES and balance > 0),
            }
        )

    proposal = calculate_collection_proposal(
        outstanding=collection_balance,
        affordability=affordability,
    )
    proposal["current_contractual_monthly_installments"] = float(contractual_monthly.quantize(_MONEY))

    return {
        "total_outstanding": float(collection_balance.quantize(_MONEY)),
        "approved_not_active_balance": float(approved_not_active_balance.quantize(_MONEY)),
        "active_or_defaulted_loan_count": sum(
            1 for loan in loans if loan.status in _COLLECTION_STATUSES and _money(loan.balance) > 0
        ),
        "approved_not_active_loan_count": sum(
            1 for loan in loans if loan.status == LoanStatus.APPROVED and _money(loan.balance) > 0
        ),
        "loans": serialized,
        "collection_proposal": proposal,
    }
