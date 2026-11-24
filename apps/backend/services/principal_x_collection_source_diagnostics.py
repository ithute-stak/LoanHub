"""Read-only cross-source LoanHub collection reconciliation diagnostics.

Payment, cash, allocations and treasury are not independent amounts to sum:
cash/allocations/treasury often describe the SAME payment. This audit checks
linkage and surfaces unlinked entries without double-counting or certifying a
complete lifetime ledger. Never use the result to authorize live posting.
"""
from dataclasses import dataclass
from decimal import Decimal
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
    overallocated_payment_count: int = 0
    invalid_allocation_count: int = 0
    cash_overapplied_count: int = 0
    invalid_cash_amount_count: int = 0
    treasury_amount_mismatch_count: int = 0
    treasury_currency_mismatch_count: int = 0


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
    # Allocations can spread one payment over multiple installments. Count
    # each payment only once and flag allocations larger than its recorded
    # amount; never sum allocation totals as separate cash collections.
    payment_by_id = {row.id: row for row in payments}
    allocated_by_payment = {}
    invalid_allocations = 0
    for allocation in allocations:
        # Orphans are reported separately; never assume a payment amount.
        if allocation.payment_id not in payment_by_id:
            continue
        try:
            amount = Decimal(str(allocation.amount))
        except (ValueError, TypeError, ArithmeticError):
            invalid_allocations += 1
            continue
        if not amount.is_finite() or amount <= 0:
            invalid_allocations += 1
            continue
        allocated_by_payment[allocation.payment_id] = (
            allocated_by_payment.get(allocation.payment_id, Decimal("0")) + amount
        )
    overallocated = 0
    for payment_id, allocated in allocated_by_payment.items():
        try:
            paid = Decimal(str(payment_by_id[payment_id].amount))
        except (ValueError, TypeError, ArithmeticError):
            invalid_allocations += 1
            continue
        if not paid.is_finite() or paid < 0:
            invalid_allocations += 1
        elif allocated > paid:
            # Monetary records use cents; even M0.01 overage is an issue.
            overallocated += 1
    # Cash evidence is corroborating documentation, not an additional
    # collection to sum. Flag records claiming more cash applied than the
    # corresponding payment received, without requiring equality (change,
    # forwarding and split handling may differ).
    cash_overapplied = 0
    invalid_cash = 0
    for row in cash:
        payment = payment_by_id.get(row.payment_id)
        if payment is None:
            continue
        try:
            applied = Decimal(str(row.applied_amount))
            received = Decimal(str(payment.amount))
        except (ValueError, TypeError, ArithmeticError, AttributeError):
            invalid_cash += 1
            continue
        if not applied.is_finite() or not received.is_finite() or applied < 0 or received < 0:
            invalid_cash += 1
        elif applied > received:
            cash_overapplied += 1
    treasury = (
        db.query(TreasuryEntry)
        .filter(TreasuryEntry.company_id == company_id,
                TreasuryEntry.loan_id == loan_id)
        .all()
    )
    # Treasury entries represent bookkeeping of a payment, NOT an extra
    # collection. Compare linked, posted, non-voided entries for diagnostics
    # only; refunds/reversals and external sources still need certification.
    treasury_amount_mismatches = 0
    treasury_currency_mismatches = 0
    for entry in treasury:
        payment = payment_by_id.get(entry.payment_transaction_id)
        if payment is None or getattr(entry, "is_voided", False):
            continue
        approval = getattr(entry, "approval_status", None)
        if approval is not None and getattr(approval, "value", approval) != "posted":
            continue
        treasury_currency = getattr(entry, "currency", None)
        payment_currency = getattr(payment, "currency", None)
        if treasury_currency is not None and payment_currency is not None:
            if treasury_currency != payment_currency:
                treasury_currency_mismatches += 1
        try:
            treasury_amount = Decimal(str(entry.amount))
            payment_amount = Decimal(str(payment.amount))
        except (ValueError, TypeError, ArithmeticError, AttributeError):
            treasury_amount_mismatches += 1
            continue
        if (
            not treasury_amount.is_finite()
            or not payment_amount.is_finite()
            or treasury_amount < 0
            or payment_amount < 0
            or treasury_amount != payment_amount
        ):
            treasury_amount_mismatches += 1

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
        overallocated_payment_count=overallocated,
        invalid_allocation_count=invalid_allocations,
        cash_overapplied_count=cash_overapplied,
        invalid_cash_amount_count=invalid_cash,
        treasury_amount_mismatch_count=treasury_amount_mismatches,
        treasury_currency_mismatch_count=treasury_currency_mismatches,
        missing_cash_evidence_count=sum(
            1 for row in payments
            if getattr(row, "payment_method", None) == PaymentMethod.CASH
            and row.id not in cash_payment_ids
        ),
    )
