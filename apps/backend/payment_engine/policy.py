"""Pure, deterministic arrears policy calculations; no database mutations.

Amounts are Decimal strings/currency decimals. This module does NOT post payments.
Additional default interest is disabled pending company-specific legal verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

CENT = Decimal("0.01")


def money(value: Decimal | str | int) -> Decimal:
    result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    if not result.is_finite():
        raise ValueError("Amounts must be finite")
    return result


class ArrearsRule(str, Enum):
    CARRY_WITH_INTEREST = "carry_with_interest"
    SIMPLE_CARRY = "simple_carry"
    FIXED_SCHEDULE = "fixed_schedule"


@dataclass(frozen=True)
class ArrearsPolicy:
    rule: ArrearsRule = ArrearsRule.SIMPLE_CARRY
    version: int = 1
    periodic_arrears_rate_percent: Decimal = Decimal("0")
    additional_interest_authorized: bool = False


@dataclass(frozen=True)
class ArrearsPreview:
    scheduled_installment: Decimal
    carried_arrears: Decimal
    permitted_additional_interest: Decimal
    next_schedule_amount: Decimal
    separately_tracked_arrears: Decimal
    total_due: Decimal


def preview_arrears(
    *,
    scheduled_installment: Decimal,
    prior_installment_due: Decimal,
    paid_toward_prior: Decimal,
    policy: ArrearsPolicy,
) -> ArrearsPreview:
    scheduled = money(scheduled_installment)
    prior = money(prior_installment_due)
    paid = money(paid_toward_prior)
    rate = Decimal(str(policy.periodic_arrears_rate_percent))
    if min(scheduled, prior, paid) < 0 or paid > prior:
        raise ValueError("Invalid installment amounts or payment exceeds previous due")
    if policy.version < 1 or not rate.is_finite() or rate < 0 or rate > 100:
        raise ValueError("Invalid policy version or interest rate")
    arrears = money(prior - paid)
    interest = Decimal("0.00")
    if policy.rule == ArrearsRule.CARRY_WITH_INTEREST:
        if not policy.additional_interest_authorized:
            raise ValueError("Arrears interest requires explicit legal/contract authorization")
        interest = money(arrears * rate / Decimal("100"))
    if policy.rule == ArrearsRule.FIXED_SCHEDULE:
        next_amount = scheduled
        separate = arrears
    else:
        next_amount = money(scheduled + arrears + interest)
        separate = Decimal("0.00")
    return ArrearsPreview(
        scheduled_installment=scheduled,
        carried_arrears=arrears,
        permitted_additional_interest=interest,
        next_schedule_amount=next_amount,
        separately_tracked_arrears=separate,
        total_due=money(next_amount + separate),
    )
