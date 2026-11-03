"""Read-only, component-aware allocation and payment conservation contract.

This module does not post money, change loan status, or calculate default
interest. A future posting adapter must lock its loan and enforce idempotency.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
from .policy import money


@dataclass(frozen=True)
class DueComponent:
    installment_id: str
    principal: Decimal
    ordinary_interest: Decimal
    permitted_fees: Decimal = Decimal("0")


@dataclass(frozen=True)
class ComponentAllocation:
    installment_id: str
    principal_paid: Decimal
    ordinary_interest_paid: Decimal
    fees_paid: Decimal


@dataclass(frozen=True)
class AllocationPreview:
    amount_received: Decimal
    amount_applied: Decimal
    unapplied_credit: Decimal
    allocations: tuple[ComponentAllocation, ...]


def preview_allocation(
    *, amount_received: Decimal, installments: Sequence[DueComponent],
    existing_unapplied_credit: Decimal = Decimal("0"),
) -> AllocationPreview:
    """Pay oldest installments in the order fees, interest, principal.

    Component order is a preview contract, not an authorization to impose
    penalties; caller must supply already-validated contractual components.
    """
    received = money(amount_received)
    credit = money(existing_unapplied_credit)
    if received < 0 or credit < 0:
        raise ValueError("Received payment and existing credit cannot be negative")
    available = money(received + credit)
    remaining = available
    results: list[ComponentAllocation] = []
    seen: set[str] = set()
    for row in installments:
        if not row.installment_id or row.installment_id in seen:
            raise ValueError("Installment identifiers must be unique and nonempty")
        seen.add(row.installment_id)
        amounts = [money(row.permitted_fees), money(row.ordinary_interest), money(row.principal)]
        if any(value < 0 for value in amounts):
            raise ValueError("Outstanding installment components cannot be negative")
        assigned = []
        for value in amounts:
            take = min(remaining, value)
            assigned.append(take)
            remaining = money(remaining - take)
        if any(assigned):
            results.append(ComponentAllocation(
                installment_id=row.installment_id,
                fees_paid=assigned[0],
                ordinary_interest_paid=assigned[1],
                principal_paid=assigned[2],
            ))
    applied = money(available - remaining)
    if money(applied + remaining) != available:
        raise AssertionError("Payment conservation invariant violated")
    return AllocationPreview(
        amount_received=received, amount_applied=applied,
        unapplied_credit=remaining, allocations=tuple(results),
    )
