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
from database.models.enums import (
    PaymentDirection, PaymentMethod, PaymentPurpose, PaymentStatus, TreasuryDirection,
    TreasuryEntryType,
)
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
    nonfinal_allocation_payment_count: int = 0
    cash_overapplied_count: int = 0
    invalid_cash_amount_count: int = 0
    cash_direction_mismatch_count: int = 0
    treasury_amount_mismatch_count: int = 0
    treasury_currency_mismatch_count: int = 0
    treasury_direction_mismatch_count: int = 0
    voided_linked_treasury_count: int = 0
    unposted_linked_treasury_count: int = 0
    missing_posted_treasury_evidence_count: int = 0
    missing_posted_refund_treasury_count: int = 0
    refund_treasury_type_mismatch_count: int = 0
    treasury_entry_type_mismatch_count: int = 0
    duplicate_posted_treasury_payment_count: int = 0
    duplicate_cash_payment_count: int = 0
    duplicate_allocation_pair_count: int = 0


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
    cash_counts = {}
    for row in cash:
        if row.payment_id in payment_ids:
            cash_counts[row.payment_id] = cash_counts.get(row.payment_id, 0) + 1
    cash_payment_ids = set(cash_counts)
    duplicate_cash = sum(1 for count in cash_counts.values() if count > 1)
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
    allocation_pair_counts = {}
    for allocation in allocations:
        installment_id = getattr(allocation, "installment_id", None)
        if allocation.payment_id in payment_ids and installment_id is not None:
            key = (allocation.payment_id, installment_id)
            allocation_pair_counts[key] = allocation_pair_counts.get(key, 0) + 1
    duplicate_allocation_pairs = sum(1 for count in allocation_pair_counts.values() if count > 1)
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
    # An allocation linked to a real but unfinished/failed/outbound payment
    # must never be mistaken for an established borrower repayment.
    nonfinal_allocation_payments = sum(
        1 for payment_id in allocated_by_payment
        if (
            getattr(payment_by_id[payment_id], "status", None) != PaymentStatus.SUCCEEDED
            or getattr(payment_by_id[payment_id], "purpose", None) != PaymentPurpose.LOAN_REPAYMENT
            or getattr(payment_by_id[payment_id], "direction", None) != PaymentDirection.INBOUND
        )
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
    cash_direction_mismatches = 0
    for row in cash:
        payment = payment_by_id.get(row.payment_id)
        if payment is None:
            continue
        if (
            getattr(row, "direction", None) != getattr(payment, "direction", None)
            or getattr(row, "direction", None) not in (
                PaymentDirection.INBOUND, PaymentDirection.OUTBOUND,
            )
        ):
            cash_direction_mismatches += 1
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
    treasury_direction_mismatches = 0
    treasury_entry_type_mismatches = 0
    refund_treasury_type_mismatches = 0
    voided_linked_treasury = 0
    unposted_linked_treasury = 0
    for entry in treasury:
        payment = payment_by_id.get(entry.payment_transaction_id)
        if payment is None:
            continue
        # Only successful inbound loan repayments are candidates for
        # collection corroboration. Voided or unposted linked treasury
        # evidence needs explicit review, not silent exclusion.
        is_collected_repayment = (
            getattr(payment, "status", None) == PaymentStatus.SUCCEEDED
            and getattr(payment, "purpose", None) == PaymentPurpose.LOAN_REPAYMENT
            and getattr(payment, "direction", None) == PaymentDirection.INBOUND
        )
        if getattr(entry, "is_voided", False):
            if is_collected_repayment:
                voided_linked_treasury += 1
            continue
        approval = getattr(entry, "approval_status", None)
        # Missing/unknown status is NOT a posted treasury entry.
        if getattr(approval, "value", approval) != "posted":
            if is_collected_repayment:
                unposted_linked_treasury += 1
            continue
        # A posted loan collection must be classified as a loan collection,
        # not as a branch adjustment, expense or unrelated income.
        if is_collected_repayment and (
            getattr(entry, "entry_type", None) != TreasuryEntryType.LOAN_COLLECTION
        ):
            treasury_entry_type_mismatches += 1
        is_completed_refund = (
            getattr(payment, "status", None) == PaymentStatus.SUCCEEDED
            and getattr(payment, "purpose", None) == PaymentPurpose.REFUND
            and getattr(payment, "direction", None) == PaymentDirection.OUTBOUND
        )
        if is_completed_refund and (
            getattr(entry, "entry_type", None) != TreasuryEntryType.REFUND
        ):
            refund_treasury_type_mismatches += 1
        treasury_direction = getattr(entry, "direction", None)
        payment_direction = getattr(payment, "direction", None)
        expected_treasury_direction = {
            PaymentDirection.INBOUND: TreasuryDirection.MONEY_IN,
            PaymentDirection.OUTBOUND: TreasuryDirection.MONEY_OUT,
        }.get(payment_direction)
        if (
            expected_treasury_direction is None
            or treasury_direction != expected_treasury_direction
        ):
            treasury_direction_mismatches += 1
        treasury_currency = getattr(entry, "currency", None)
        payment_currency = getattr(payment, "currency", None)
        # Missing currency evidence is a mismatch too. A linked treasury
        # record is not corroborated unless both currency values exist and
        # agree; this diagnostic never authorizes a collection.
        if (
            not isinstance(treasury_currency, str)
            or not treasury_currency.strip()
            or not isinstance(payment_currency, str)
            or not payment_currency.strip()
            or treasury_currency != payment_currency
        ):
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

    # A successful inbound loan repayment with no posted, non-voided
    # treasury link is a gap for review. Historical collections may use
    # different accounting paths; this is NOT proof of a missing payment.
    # Multiple posted entries for the same payment require review even if
    # each entry independently matches the payment amount.
    posted_counts = {}
    for entry in treasury:
        if (
            entry.payment_transaction_id in payment_ids
            and not getattr(entry, "is_voided", False)
            and getattr(getattr(entry, "approval_status", None), "value",
                        getattr(entry, "approval_status", None)) == "posted"
        ):
            key = entry.payment_transaction_id
            posted_counts[key] = posted_counts.get(key, 0) + 1
    duplicate_posted = sum(1 for count in posted_counts.values() if count > 1)
    posted_treasury_payment_ids = {
        entry.payment_transaction_id for entry in treasury
        if entry.payment_transaction_id in payment_ids
        and not getattr(entry, "is_voided", False)
        and getattr(getattr(entry, "approval_status", None), "value",
                    getattr(entry, "approval_status", None)) == "posted"
    }
    missing_posted_treasury = sum(
        1 for row in payments
        if (
            getattr(row, "status", None) == PaymentStatus.SUCCEEDED
            and getattr(row, "purpose", None) == PaymentPurpose.LOAN_REPAYMENT
            and getattr(row, "direction", None) == PaymentDirection.INBOUND
            and row.id not in posted_treasury_payment_ids
        )
    )
    # Refunds also require a posted, non-voided treasury link, but this
    # diagnostic does NOT verify the refund against its original collection.
    missing_posted_refund_treasury = sum(
        1 for row in payments
        if (
            getattr(row, "status", None) == PaymentStatus.SUCCEEDED
            and getattr(row, "purpose", None) == PaymentPurpose.REFUND
            and getattr(row, "direction", None) == PaymentDirection.OUTBOUND
            and row.id not in posted_treasury_payment_ids
        )
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
        overallocated_payment_count=overallocated,
        invalid_allocation_count=invalid_allocations,
        nonfinal_allocation_payment_count=nonfinal_allocation_payments,
        cash_overapplied_count=cash_overapplied,
        invalid_cash_amount_count=invalid_cash,
        cash_direction_mismatch_count=cash_direction_mismatches,
        treasury_amount_mismatch_count=treasury_amount_mismatches,
        treasury_currency_mismatch_count=treasury_currency_mismatches,
        treasury_direction_mismatch_count=treasury_direction_mismatches,
        treasury_entry_type_mismatch_count=treasury_entry_type_mismatches,
        duplicate_posted_treasury_payment_count=duplicate_posted,
        duplicate_cash_payment_count=duplicate_cash,
        duplicate_allocation_pair_count=duplicate_allocation_pairs,
        voided_linked_treasury_count=voided_linked_treasury,
        unposted_linked_treasury_count=unposted_linked_treasury,
        missing_posted_treasury_evidence_count=missing_posted_treasury,
        missing_posted_refund_treasury_count=missing_posted_refund_treasury,
        refund_treasury_type_mismatch_count=refund_treasury_type_mismatches,
        missing_cash_evidence_count=sum(
            1 for row in payments
            if getattr(row, "payment_method", None) == PaymentMethod.CASH
            and row.id not in cash_payment_ids
        ),
    )
