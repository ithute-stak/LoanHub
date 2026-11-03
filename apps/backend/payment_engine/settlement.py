"""Pure settlement quotation with explicit legally approved caps.

No live loan posting, status mutation or automatic legal determination.
A total paid at 2x original principal is an informational review signal,
NOT a universal settlement rule. In-duplum limits must be derived from
legally verified interest components and a jurisdiction-specific policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .policy import money


@dataclass(frozen=True)
class SettlementComponents:
    original_principal: Decimal
    principal_collectible: Decimal
    ordinary_interest_collectible: Decimal
    additional_interest_collectible: Decimal = Decimal("0")
    permitted_fees_collectible: Decimal = Decimal("0")
    total_historical_paid: Decimal = Decimal("0")


@dataclass(frozen=True)
class VerifiedInterestLimit:
    """Interest ceiling supplied by a separately approved legal rule.

    This is an absolute maximum collectible interest amount for the supplied
    snapshot, NOT an instruction to compute 2x original principal.
    """
    maximum_collectible_interest: Decimal
    legal_basis_reference: str
    verified: bool = False


@dataclass(frozen=True)
class SettlementPreview:
    total_claimed: Decimal
    collectible_obligation: Decimal
    total_paid: Decimal
    outstanding: Decimal
    overpayment_for_reconciliation: Decimal
    interest_reduction: Decimal
    twice_original_principal_reached: bool
    state: str


def preview_settlement(
    *, components: SettlementComponents,
    interest_limit: VerifiedInterestLimit | None = None,
) -> SettlementPreview:
    original = money(components.original_principal)
    principal = money(components.principal_collectible)
    regular_interest = money(components.ordinary_interest_collectible)
    extra_interest = money(components.additional_interest_collectible)
    fees = money(components.permitted_fees_collectible)
    paid = money(components.total_historical_paid)
    if original <= 0 or any(value < 0 for value in (principal, regular_interest, extra_interest, fees, paid)):
        raise ValueError("Principal must be positive and monetary components nonnegative")
    if principal > original:
        raise ValueError("Collectible principal cannot exceed original principal")
    claimed_interest = money(regular_interest + extra_interest)
    allowed_interest = claimed_interest
    if interest_limit is not None:
        cap = money(interest_limit.maximum_collectible_interest)
        if cap < 0 or not interest_limit.verified or not interest_limit.legal_basis_reference.strip():
            raise ValueError("An interest cap requires a nonnegative verified legal limit and reference")
        allowed_interest = min(claimed_interest, cap)
    claimed = money(principal + claimed_interest + fees)
    collectible = money(principal + allowed_interest + fees)
    outstanding = max(money(collectible - paid), Decimal("0.00"))
    excess = max(money(paid - collectible), Decimal("0.00"))
    return SettlementPreview(
        total_claimed=claimed,
        collectible_obligation=collectible,
        total_paid=paid,
        outstanding=outstanding,
        overpayment_for_reconciliation=excess,
        interest_reduction=money(claimed_interest - allowed_interest),
        twice_original_principal_reached=paid >= money(original * 2),
        state="overpaid" if excess > 0 else "settled" if outstanding == 0 else "outstanding",
    )
