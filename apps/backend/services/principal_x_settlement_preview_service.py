"""Read-only LoanHub database integration for opt-in Principal x% quotes.

No mutation, no calculator calls, no legacy inference, and no automatic settlement.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json

from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from database.models.payment import PaymentTransaction
from payment_engine.principal_x_schedule_adapter import quote_from_approved_schedule
from payment_engine.principal_x_settlement import DatedCredit, PrincipalXQuote


@dataclass(frozen=True)
class PrincipalXSnapshotQuote:
    """Change-detection fingerprint, NOT certified payment or consent evidence."""
    quote: PrincipalXQuote
    snapshot_revision: str


def quote_principal_x_for_loan_with_revision(
    db: Session, *, loan: ClientCompanyLoan, settlement_date: date
) -> PrincipalXSnapshotQuote:
    """Compute preview and advisory source fingerprint from the same snapshot."""
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
    quote = quote_from_approved_schedule(
        principal=Decimal(str(loan.principal_amount)),
        rate_percent=Decimal(str(loan.interest_rate)),
        schedule_rows=rows,
        settlement_date=settlement_date,
        successful_credits=[
            DatedCredit(p.completed_at.date(), Decimal(str(p.amount))) for p in payments
        ],
    )

    # This digest is a read-only change detector, not a durable ledger revision
    # or permission to post. A production posting service must re-read and
    # reconcile ALL financial sources under an actual loan row lock.
    fingerprint = {
        "version": 1,
        "company_id": str(loan.company_id),
        "loan_id": str(loan.id),
        "principal": str(Decimal(str(loan.principal_amount))),
        "rate": str(Decimal(str(loan.interest_rate))),
        "contractual_total": str(Decimal(str(loan.total_repayable))),
        "amount_paid": str(Decimal(str(loan.amount_paid))),
        "settlement_date": settlement_date.isoformat(),
        "schedule": [
            [str(r.installment_number), r.due_date.isoformat(), str(Decimal(str(r.total_due)))]
            for r in rows
        ],
        "repayments": sorted([
            [str(p.id), p.completed_at.isoformat(), str(Decimal(str(p.amount)))]
            for p in payments
        ]),
    }
    revision = sha256(
        json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return PrincipalXSnapshotQuote(quote=quote, snapshot_revision=revision)


def quote_principal_x_for_loan(
    db: Session, *, loan: ClientCompanyLoan, settlement_date: date
) -> PrincipalXQuote:
    """Backward-compatible non-payable Principal x% quote."""
    return quote_principal_x_for_loan_with_revision(
        db, loan=loan, settlement_date=settlement_date,
    ).quote
