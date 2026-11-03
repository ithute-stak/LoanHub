"""Read-only integrity checks for exact-source loan payment reversals.

No database mutations, no gateway refunds and no ledger writes. A future
transactional adapter must enforce tenant scope, row locking, treasury/journal
integrity and the proper payment-method-specific approval workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .policy import money


@dataclass(frozen=True)
class ReversalAllocation:
    installment_id: str
    original_amount: Decimal
    installment_current_paid: Decimal
    is_superseded: bool = False


@dataclass(frozen=True)
class ReversalRequest:
    payment_id: str
    payment_status: str
    payment_method: str
    payment_amount: Decimal
    loan_amount_paid: Decimal
    loan_total_repayable: Decimal
    allocations: tuple[ReversalAllocation, ...]
    is_latest_repayment: bool
    original_journal_exists: bool
    treasury_entry_exists: bool
    treasury_entry_voided: bool = False
    has_downstream_restructure: bool = False


@dataclass(frozen=True)
class ReversalImpact:
    payment_id: str
    result: str
    reversed_amount: Decimal
    loan_paid_after: Decimal
    loan_balance_after: Decimal
    installment_paid_after: tuple[tuple[str, Decimal], ...]


def preview_cash_reversal(request: ReversalRequest) -> ReversalImpact:
    """Validate one ordinary cash repayment's exact recorded allocation.

    Only ordinary cash repayment candidates are eligible. Electronic payments,
    refunds and early settlements have separate flows. The calling adapter must
    verify the payment purpose and linkage before using this pure preview.
    """
    if not request.payment_id:
        raise ValueError("Payment ID is required")
    if request.payment_status == "reversed":
        raise ValueError("Already reversed: return the stored reversal result instead")
    if request.payment_status != "succeeded":
        raise ValueError("Only successful payments can be reversed")
    if request.payment_method != "cash":
        raise ValueError("Only cash repayments are eligible for this reversal preview")
    if not request.is_latest_repayment:
        raise ValueError("A later repayment exists")
    if request.has_downstream_restructure:
        raise ValueError("Linked restructure or rollover must be reversed first")
    if not request.original_journal_exists:
        raise ValueError("Original accounting journal is missing")
    if not request.treasury_entry_exists or request.treasury_entry_voided:
        raise ValueError("Valid, unvoided treasury entry is required")
    payment = money(request.payment_amount)
    paid = money(request.loan_amount_paid)
    total = money(request.loan_total_repayable)
    if payment <= 0 or paid < payment or total < 0:
        raise ValueError("Payment and loan totals are inconsistent")
    if not request.allocations:
        raise ValueError("Original payment allocations are missing")
    identified: set[str] = set()
    allocated_total = Decimal("0.00")
    remaining_paid: list[tuple[str, Decimal]] = []
    for entry in request.allocations:
        if not entry.installment_id or entry.installment_id in identified:
            raise ValueError("Duplicate or missing installment allocation identifier")
        identified.add(entry.installment_id)
        if entry.is_superseded:
            raise ValueError("Cannot reverse allocations on a superseded schedule")
        allocated = money(entry.original_amount)
        current = money(entry.installment_current_paid)
        if allocated <= 0 or current < allocated:
            raise ValueError("Original allocation exceeds current installment paid amount")
        allocated_total = money(allocated_total + allocated)
        remaining_paid.append((entry.installment_id, money(current - allocated)))
    if allocated_total != payment:
        raise ValueError("Recorded allocations do not reconcile with payment amount")
    after = money(paid - payment)
    return ReversalImpact(
        payment_id=request.payment_id,
        result="eligible",
        reversed_amount=payment,
        loan_paid_after=after,
        loan_balance_after=max(money(total - after), Decimal("0.00")),
        installment_paid_after=tuple(remaining_paid),
    )
