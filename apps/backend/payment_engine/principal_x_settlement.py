"""Opt-in pure calculator for LoanHub Principal x% early settlement.

No posting, contract mutation, or assumption of legal in-duplum applicability.
The caller must obtain a borrower-authorised settlement instruction.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class DatedCredit:
    effective_date: date
    amount: Decimal


@dataclass(frozen=True)
class PrincipalXQuote:
    period: int
    uncapped_due: Decimal
    collectible_due: Decimal
    contractual_remaining: Decimal
    lifetime_cap_remaining: Decimal
    total_credited: Decimal
    ceiling_reduction: Decimal


def quote_principal_x(
    *,
    principal: Decimal,
    rate_percent: Decimal,
    due_dates: Sequence[date],
    settlement_date: date,
    successful_credits: Sequence[DatedCredit] = (),
    contractual_total: Decimal,
    enforce_contractual_ceiling: bool = True,
) -> PrincipalXQuote:
    """Accrue x% once per crossed due-date boundary; deduct credits first.

    A settlement ON a due date belongs to the preceding period. After the
    final contractual due date, this model does not add new periods/interest.
    The 2x lifetime cap includes credited payments, not just unpaid debt.
    Credits must be validated as successful, non-reversed and loan-scoped by
    the calling ledger service. No automatic rebate or settlement occurs.
    """
    principal = money(principal)
    rate_percent = Decimal(str(rate_percent))
    contractual_total = money(contractual_total)
    if principal <= 0 or rate_percent < 0 or contractual_total < 0:
        raise ValueError("Invalid principal, rate or contractual total")
    if not due_dates or list(due_dates) != sorted(set(due_dates)):
        raise ValueError("Due dates must be nonempty, unique and ascending")
    credits = sorted(successful_credits, key=lambda x: x.effective_date)
    if any(money(c.amount) <= 0 or c.effective_date > settlement_date for c in credits):
        raise ValueError("Credits must be positive and no later than settlement date")
    rate = rate_percent / Decimal("100")
    balance = money(principal * (1 + rate))
    cursor = 0
    period = 1
    # The due date is inclusive of the period ending on that date.
    for boundary in due_dates[:-1]:
        if settlement_date <= boundary:
            break
        while cursor < len(credits) and credits[cursor].effective_date <= boundary:
            balance = max(Decimal("0"), money(balance - money(credits[cursor].amount)))
            cursor += 1
        balance = money(balance * (1 + rate))
        period += 1
    while cursor < len(credits):
        balance = max(Decimal("0"), money(balance - money(credits[cursor].amount)))
        cursor += 1
    total = money(sum((money(c.amount) for c in credits), Decimal("0")))
    contractual_remaining = max(Decimal("0"), money(contractual_total - total))
    lifetime_remaining = max(Decimal("0"), money(principal * 2 - total))
    due = min(balance, lifetime_remaining)
    if enforce_contractual_ceiling:
        due = min(due, contractual_remaining)
    return PrincipalXQuote(
        period=period,
        uncapped_due=balance,
        collectible_due=due,
        contractual_remaining=contractual_remaining,
        lifetime_cap_remaining=lifetime_remaining,
        total_credited=total,
        ceiling_reduction=money(balance - due),
    )
