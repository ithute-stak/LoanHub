"""Read-only LoanHub database integration for opt-in Principal x% quotes.

No mutation, no calculator calls, no legacy inference, and no automatic settlement.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from database.models.payment import PaymentTransaction
from payment_engine.principal_x_schedule_adapter import quote_from_approved_schedule
from payment_engine.principal_x_settlement import DatedCredit, PrincipalXQuote


def quote_principal_x_for_loan(
    db: Session, *, loan: ClientCompanyLoan, settlement_date: date
) -> PrincipalXQuote:
    """Preview against persisted contract and succeeded repayment transactions.

    This intentionally refuses legacy, renewed, and mismatched records instead
    of guessing historical payments or merging unrelated renewal schedules.
    """
    if getattr(loan, "origination_channel", None) == "legacy_cashout":
        raise ValueError("Legacy loans require explicit migration and reconciliation")
    if getattr(loan, "renewal_cycle_count", 0):
        raise ValueError("Renewed loans require a cycle-aware settlement adapter")
    if not loan.disbursed_at or settlement_date < loan.disbursed_at.date():
        raise ValueError("Settlement cannot precede disbursement")
    rows = sorted(
        [r for r in loan.installments if not getattr(r, "is_superseded", False)],
        key=lambda r: r.installment_number,
    )
    if len(rows) != int(loan.repayment_period):
        raise ValueError("Persisted repayment schedule is missing or incomplete")
    contractual = sum((Decimal(str(r.total_due)) for r in rows), Decimal("0"))
    if abs(contractual - Decimal(str(loan.total_repayable))) > Decimal("0.01"):
        raise ValueError("Persisted schedule does not reconcile with approved contract")
    payments = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.loan_id == loan.id,
            PaymentTransaction.company_id == loan.company_id,
            PaymentTransaction.purpose == PaymentPurpose.LOAN_REPAYMENT,
            PaymentTransaction.direction == PaymentDirection.INBOUND,
            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        )
        .order_by(PaymentTransaction.completed_at.asc(), PaymentTransaction.created_at.asc())
        .all()
    )
    if any(p.completed_at is None for p in payments):
        raise ValueError("Successful repayment missing completion timestamp")
    if any(p.completed_at.date() > settlement_date for p in payments):
        raise ValueError("Historical quotes with later payments need ledger snapshots")
    total = sum((Decimal(str(p.amount)) for p in payments), Decimal("0"))
    if abs(total - Decimal(str(loan.amount_paid))) > Decimal("0.01"):
        raise ValueError("Repayment ledger does not reconcile with loan amount paid")
    return quote_from_approved_schedule(
        principal=Decimal(str(loan.principal_amount)),
        rate_percent=Decimal(str(loan.interest_rate)),
        schedule_rows=rows,
        settlement_date=settlement_date,
        successful_credits=[
            DatedCredit(p.completed_at.date(), Decimal(str(p.amount))) for p in payments
        ],
    )
