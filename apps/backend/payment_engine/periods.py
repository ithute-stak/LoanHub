"""Deterministic, read-only multi-period arrears projections.

No database writes, payment receipts, capitalization or contract changes.
This deliberately excludes default-interest calculations until component-level
principal, interest and charge accounting is available.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .policy import ArrearsPolicy, ArrearsRule, money


@dataclass(frozen=True)
class PeriodInput:
    scheduled_due: Decimal
    amount_received: Decimal


@dataclass(frozen=True)
class PeriodResult:
    period: int
    scheduled_due: Decimal
    opening_arrears: Decimal
    total_collectible_due: Decimal
    amount_received: Decimal
    amount_applied: Decimal
    closing_arrears: Decimal
    carried_into_next_schedule: Decimal
    separately_tracked_arrears: Decimal
    unapplied_credit: Decimal


def preview_periods(
    periods: Sequence[PeriodInput], *, policy: ArrearsPolicy,
) -> list[PeriodResult]:
    """Project cumulative unpaid dues without creating another debt.

    Both simple carry and fixed schedule have identical collectible totals;
    only their presentation differs. A payment pays already due debt first,
    with excess recorded as unapplied credit rather than silently capitalized.
    """
    if policy.rule == ArrearsRule.CARRY_WITH_INTEREST:
        raise ValueError(
            "Multi-period additional interest needs verified component-level "
            "principal/interest allocation and legal authorization"
        )
    if policy.rule not in {ArrearsRule.SIMPLE_CARRY, ArrearsRule.FIXED_SCHEDULE}:
        raise ValueError("Unsupported arrears policy")
    if policy.version < 1 or policy.additional_interest_authorized or Decimal(str(policy.periodic_arrears_rate_percent)) != 0:
        raise ValueError("Invalid policy for interest-free multi-period preview")

    arrears = Decimal("0.00")
    credit = Decimal("0.00")
    results: list[PeriodResult] = []
    for index, period in enumerate(periods, start=1):
        scheduled = money(period.scheduled_due)
        received = money(period.amount_received)
        if scheduled < 0 or received < 0:
            raise ValueError("Scheduled due and received amounts must be nonnegative")
        opening = arrears
        due = money(opening + scheduled)
        available = money(received + credit)
        applied = min(available, due)
        arrears = money(due - applied)
        credit = money(available - applied)
        results.append(PeriodResult(
            period=index,
            scheduled_due=scheduled,
            opening_arrears=opening,
            total_collectible_due=due,
            amount_received=received,
            amount_applied=applied,
            closing_arrears=arrears,
            carried_into_next_schedule=arrears if policy.rule == ArrearsRule.SIMPLE_CARRY else Decimal("0.00"),
            separately_tracked_arrears=arrears if policy.rule == ArrearsRule.FIXED_SCHEDULE else Decimal("0.00"),
            unapplied_credit=credit,
        ))
    return results
