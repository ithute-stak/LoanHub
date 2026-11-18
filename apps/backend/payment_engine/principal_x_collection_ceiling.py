"""Read-only collection ceiling preflight for opt-in Principal x% loans.

This module does not post payments or alter existing LoanHub collection paths.
The caller must reconcile historical payments, reversals, refunds, and fees
before enabling the policy for a real loan.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    if not result.is_finite():
        raise ValueError("Amounts must be finite")
    return result


@dataclass(frozen=True)
class CollectionCeiling:
    principal: Decimal
    net_collected: Decimal
    maximum_lifetime_collection: Decimal
    remaining_allowance: Decimal
    proposed_collection: Decimal
    permitted: bool


def evaluate_collection_ceiling(
    *, original_principal: Decimal, net_collected: Decimal,
    proposed_collection: Decimal,
) -> CollectionCeiling:
    """Enforce 2x principal against cumulative net collections, not debt balance.

    net_collected must be supplied by a reconciled authoritative ledger,
    including all principal, interest, fee and penalty collections net of
    verified refunds/reversals. Never use only installment allocations.
    """
    principal = money(original_principal)
    collected = money(net_collected)
    proposed = money(proposed_collection)
    if principal <= 0:
        raise ValueError("Original principal must be positive")
    if collected < 0:
        raise ValueError("Net collected cannot be negative")
    if proposed <= 0:
        raise ValueError("Proposed collection must be positive")
    limit = money(principal * Decimal("2"))
    allowance = max(Decimal("0.00"), money(limit - collected))
    return CollectionCeiling(
        principal=principal,
        net_collected=collected,
        maximum_lifetime_collection=limit,
        remaining_allowance=allowance,
        proposed_collection=proposed,
        permitted=proposed <= allowance,
    )


def require_collection_within_ceiling(
    *, original_principal: Decimal, net_collected: Decimal,
    proposed_collection: Decimal,
) -> CollectionCeiling:
    result = evaluate_collection_ceiling(
        original_principal=original_principal,
        net_collected=net_collected,
        proposed_collection=proposed_collection,
    )
    if not result.permitted:
        raise ValueError("Proposed collection exceeds the Principal x% lifetime ceiling")
    return result
