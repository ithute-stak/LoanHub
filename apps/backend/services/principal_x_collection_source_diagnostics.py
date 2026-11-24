"""Read-only cross-source LoanHub collection reconciliation diagnostics.

Payment, cash, allocations and treasury are not independent amounts to sum:
cash/allocations/treasury often describe the SAME payment. This audit checks
linkage and surfaces unlinked entries without double-counting or certifying a
complete lifetime ledger. Never use the result to authorize live posting.
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cash import CashTransaction
from database.models.enums import PaymentMethod
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from database.models.treasury import TreasuryEntry


@dataclass(frozen=True)
class CollectionSourceDiagnostics:
    payment_count: int
    cash_link_count: int
    allocation_count: int
    treasury_count: int
    orphan_cash_count: int
    orphan_allocation_count: int
    unlinked_treasury_count: int
    complete: bool = False
    missing_cash_evidence_count: int = 0


def inspect_principal_x_collection_sources(
    db: Session, *, company_id: UUID, loan_id: UUID,
) -> CollectionSourceDiagnostics:
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified company and loan UUIDs required")
    payments = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.company_id == company_id,
                PaymentTransaction.loan_id == loan_id)
        .all()
    )
    payment_ids = {row.id for row in payments}
    cash = (
        db.query(CashTransaction)
        .join(PaymentTransaction, CashTransaction.payment_id == PaymentTransaction.id)
        .filter(PaymentTransaction.company_id == company_id,
                PaymentTransaction.loan_id == loan_id)
        .all()
    )
    cash_payment_ids = {row.payment_id for row in cash}
    allocations = (
        db.query(PaymentAllocation)
        .join(RepaymentInstallment,
              PaymentAllocation.installment_id == RepaymentInstallment.id)
        .filter(RepaymentInstallment.loan_id == loan_id)
        .all()
    )
    treasury = (
        db.query(TreasuryEntry)
        .filter(TreasuryEntry.company_id == company_id,
                TreasuryEntry.loan_id == loan_id)
        .all()
    )
    return CollectionSourceDiagnostics(
        payment_count=len(payments),
        cash_link_count=len(cash),
        allocation_count=len(allocations),
        treasury_count=len(treasury),
        orphan_cash_count=sum(1 for row in cash if row.payment_id not in payment_ids),
        orphan_allocation_count=sum(
            1 for row in allocations if row.payment_id not in payment_ids
        ),
        unlinked_treasury_count=sum(
            1 for row in treasury
            if row.payment_transaction_id not in payment_ids
        ),
        complete=False,
        missing_cash_evidence_count=sum(
            1 for row in payments
            if getattr(row, "payment_method", None) == PaymentMethod.CASH
            and row.id not in cash_payment_ids
        ),
    )
