"""Pure non-posting allocation proposal for an LSL loan repayment.

Future-only engineering reference. Never imported by active LoanHub APIs.
Allocation order requires per-company contractual and legal approval.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

CENT = Decimal("0.01")
COMPONENTS = ("permitted_charges", "interest", "principal")

class AllocationError(ValueError):
    pass

def cents(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise AllocationError("Amounts must be nonnegative finite Decimals")
    if value != value.quantize(CENT):
        raise AllocationError("Amounts must be exact LSL cents")
    if value > Decimal("9999999999999999.99"):
        raise AllocationError("Amount out of range")
    return value

@dataclass(frozen=True)
class Allocation:
    requested: Decimal
    allocated: Mapping[str, Decimal]
    unapplied: Decimal
    policy_version: str

    @property
    def allocated_total(self) -> Decimal:
        return sum(self.allocated.values(), Decimal("0.00"))

def propose_allocation(*, amount: Decimal, balances: Mapping[str, Decimal],
                       approved_order: tuple[str, ...], policy_version: str) -> Allocation:
    cents(amount)
    if amount <= 0 or not isinstance(policy_version, str) or not policy_version.strip():
        raise AllocationError("Positive amount and approved policy version required")
    if not isinstance(balances, Mapping) or set(balances) != set(COMPONENTS):
        raise AllocationError("Must supply all and only approved components")
    if (not isinstance(approved_order, tuple) or len(approved_order) != len(COMPONENTS)
            or set(approved_order) != set(COMPONENTS)):
        raise AllocationError("Explicit, complete allocation order required")
    for value in balances.values():
        cents(value)
    outstanding = sum(balances.values(), Decimal("0.00"))
    if amount > outstanding:
        raise AllocationError("Overpayment requires separate customer funds workflow")
    remaining = amount
    allocated = {name: Decimal("0.00") for name in COMPONENTS}
    for name in approved_order:
        applied = min(remaining, balances[name])
        allocated[name] = applied
        remaining -= applied
    if remaining != Decimal("0.00") or sum(allocated.values()) != amount:
        raise AllocationError("Allocation imbalance")
    return Allocation(amount, allocated, remaining, policy_version)
