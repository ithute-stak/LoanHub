"""Non-posting schedule allocation shadow for LoanHub's existing repayment flow.

The legacy repayment ledger is authoritative. This intentionally compares only
installment-level amounts because existing PaymentAllocation rows do not record
the principal/interest/fee split needed for component-level parity.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .policy import money


@dataclass(frozen=True)
class InstallmentSnapshot:
    installment_id: str
    total_due: Decimal
    already_paid: Decimal


@dataclass(frozen=True)
class ScheduleAllocationCheck:
    result: str
    expected_by_installment: tuple[tuple[str, Decimal], ...]
    observed_by_installment: tuple[tuple[str, Decimal], ...]
    unapplied_amount: Decimal
    reason: str | None = None


def compare_allocation(
    *,
    received: Decimal,
    before: tuple[InstallmentSnapshot, ...],
    actual: tuple[tuple[str, Decimal], ...],
) -> ScheduleAllocationCheck:
    """Check that oldest available installments receive payment exactly once.

    The existing system can record an amount_paid larger than scheduled
    allocations; excess is therefore reported, never silently posted again.
    """
    paid_in = money(received)
    if paid_in <= 0:
        raise ValueError("Payment must be positive")
    remaining = paid_in
    expected: list[tuple[str, Decimal]] = []
    seen: set[str] = set()
    for row in before:
        if not row.installment_id or row.installment_id in seen:
            raise ValueError("Installment IDs must be unique")
        seen.add(row.installment_id)
        due = money(row.total_due)
        prior = money(row.already_paid)
        if due < 0 or prior < 0 or prior > due:
            raise ValueError("Invalid installment snapshot")
        available = money(due - prior)
        applied = min(remaining, available)
        if applied > 0:
            expected.append((row.installment_id, applied))
            remaining = money(remaining - applied)
    observed: list[tuple[str, Decimal]] = []
    actual_ids: set[str] = set()
    for installment_id, amount in actual:
        if not installment_id or installment_id in actual_ids:
            raise ValueError("Duplicate observed installment allocation")
        actual_ids.add(installment_id)
        value = money(amount)
        if value <= 0:
            raise ValueError("Observed allocation must be positive")
        observed.append((installment_id, value))
    expected_total = money(sum((amount for _, amount in expected), Decimal("0")))
    observed_total = money(sum((amount for _, amount in observed), Decimal("0")))
    if expected_total + remaining != paid_in:
        raise AssertionError("Shadow conservation invariant failed")
    consistent = tuple(expected) == tuple(observed)
    return ScheduleAllocationCheck(
        result="match" if consistent else "divergence",
        expected_by_installment=tuple(expected),
        observed_by_installment=tuple(observed),
        unapplied_amount=remaining,
        reason=None if consistent else "Installment allocation differs from oldest-first schedule projection",
    )
