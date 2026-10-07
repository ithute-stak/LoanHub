from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Literal


MONEY = Decimal("0.01")
DEFAULT_MINIMUM_AFFORDABILITY = Decimal("10.00")
DEFAULT_SETTLEMENT_TOLERANCE = Decimal("0.01")
AUTOPILOT_WINDOW_START_DAY = 14
AUTOPILOT_WINDOW_END_DAY = 20


Action = Literal["none", "shorten_term", "top_up", "settle"]


def money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY)


def _ceil_installments(balance: Decimal, deduction: Decimal) -> int:
    if balance <= 0 or deduction <= 0:
        return 0
    return int((balance / deduction).to_integral_value(rounding=ROUND_CEILING))


def affordability_window_open(value: date) -> bool:
    return AUTOPILOT_WINDOW_START_DAY <= value.day <= AUTOPILOT_WINDOW_END_DAY


@dataclass(frozen=True, slots=True)
class CdasAutopilotDecision:
    action: Action
    effective_balance: Decimal
    current_deduction: Decimal
    proposed_deduction: Decimal
    available_affordability: Decimal
    current_remaining_installments: int
    proposed_remaining_installments: int
    final_installment_amount: Decimal
    execute_automatically: bool
    reason: str

    def as_dict(self) -> dict:
        payload = asdict(self)
        for key in (
            "effective_balance",
            "current_deduction",
            "proposed_deduction",
            "available_affordability",
            "final_installment_amount",
        ):
            payload[key] = f"{payload[key]:.2f}"
        return payload


def decide_cdas_autopilot(
    *,
    outstanding_balance: Decimal | int | float | str,
    current_deduction: Decimal | int | float | str,
    available_affordability: Decimal | int | float | str = 0,
    pending_confirmed_payments: Decimal | int | float | str = 0,
    evaluation_date: date,
    dynamic_top_up_consent: bool,
    mandate_maximum: Decimal | int | float | str | None = None,
    minimum_affordability: Decimal | int | float | str = DEFAULT_MINIMUM_AFFORDABILITY,
    settlement_tolerance: Decimal | int | float | str = DEFAULT_SETTLEMENT_TOLERANCE,
    payment_triggered: bool = False,
) -> CdasAutopilotDecision:
    """Return the safe desired CDAS state without contacting the provider.

    available_affordability is additional CDAS headroom above the currently
    active deduction. Provider mutation is deliberately separated from this
    deterministic decision so retries cannot accidentally double-top-up.

    Cash/bank payments reduce the effective balance first. A zero balance
    produces settlement; otherwise payment-triggered decisions shorten the
    remaining installment count at the current deduction before affordability
    optimisation is considered.
    """

    balance = max(money(outstanding_balance) - money(pending_confirmed_payments), Decimal("0.00"))
    deduction = max(money(current_deduction), Decimal("0.00"))
    headroom = max(money(available_affordability), Decimal("0.00"))
    minimum = max(money(minimum_affordability), Decimal("0.00"))
    tolerance = max(money(settlement_tolerance), Decimal("0.00"))

    current_terms = _ceil_installments(balance, deduction)

    if balance <= tolerance:
        return CdasAutopilotDecision(
            action="settle",
            effective_balance=balance,
            current_deduction=deduction,
            proposed_deduction=Decimal("0.00"),
            available_affordability=headroom,
            current_remaining_installments=current_terms,
            proposed_remaining_installments=0,
            final_installment_amount=Decimal("0.00"),
            execute_automatically=True,
            reason="The authoritative effective balance is settled; remove the remaining CDAS deduction.",
        )

    if deduction <= 0:
        return CdasAutopilotDecision(
            action="none",
            effective_balance=balance,
            current_deduction=deduction,
            proposed_deduction=deduction,
            available_affordability=headroom,
            current_remaining_installments=0,
            proposed_remaining_installments=0,
            final_installment_amount=Decimal("0.00"),
            execute_automatically=False,
            reason="No active monthly CDAS deduction exists to optimise.",
        )

    current_terms = _ceil_installments(balance, deduction)
    current_final = money(balance - (deduction * max(current_terms - 1, 0)))
    if current_final <= 0:
        current_final = min(balance, deduction)

    if payment_triggered:
        return CdasAutopilotDecision(
            action="shorten_term",
            effective_balance=balance,
            current_deduction=deduction,
            proposed_deduction=deduction,
            available_affordability=headroom,
            current_remaining_installments=current_terms,
            proposed_remaining_installments=current_terms,
            final_installment_amount=current_final,
            execute_automatically=True,
            reason="A confirmed non-CDAS payment reduced the balance; keep the deduction and shorten the remaining term.",
        )

    if not affordability_window_open(evaluation_date):
        return CdasAutopilotDecision(
            action="none",
            effective_balance=balance,
            current_deduction=deduction,
            proposed_deduction=deduction,
            available_affordability=headroom,
            current_remaining_installments=current_terms,
            proposed_remaining_installments=current_terms,
            final_installment_amount=current_final,
            execute_automatically=False,
            reason="Affordability optimisation runs only from the 14th through the 20th.",
        )

    if headroom < minimum:
        return CdasAutopilotDecision(
            action="none",
            effective_balance=balance,
            current_deduction=deduction,
            proposed_deduction=deduction,
            available_affordability=headroom,
            current_remaining_installments=current_terms,
            proposed_remaining_installments=current_terms,
            final_installment_amount=current_final,
            execute_automatically=False,
            reason="Available CDAS affordability is below the configured top-up threshold.",
        )

    proposed = deduction + headroom
    if mandate_maximum is not None:
        proposed = min(proposed, max(money(mandate_maximum), Decimal("0.00")))
    proposed = min(proposed, balance)

    if proposed <= deduction:
        return CdasAutopilotDecision(
            action="none",
            effective_balance=balance,
            current_deduction=deduction,
            proposed_deduction=deduction,
            available_affordability=headroom,
            current_remaining_installments=current_terms,
            proposed_remaining_installments=current_terms,
            final_installment_amount=current_final,
            execute_automatically=False,
            reason="The mandate ceiling leaves no safe room to increase the deduction.",
        )

    proposed_terms = _ceil_installments(balance, proposed)
    if proposed_terms >= current_terms:
        return CdasAutopilotDecision(
            action="none",
            effective_balance=balance,
            current_deduction=deduction,
            proposed_deduction=deduction,
            available_affordability=headroom,
            current_remaining_installments=current_terms,
            proposed_remaining_installments=current_terms,
            final_installment_amount=current_final,
            execute_automatically=False,
            reason="The available affordability would not reduce the remaining payroll periods.",
        )

    final_amount = money(balance - (proposed * max(proposed_terms - 1, 0)))
    if final_amount <= 0:
        final_amount = min(balance, proposed)

    return CdasAutopilotDecision(
        action="top_up",
        effective_balance=balance,
        current_deduction=deduction,
        proposed_deduction=proposed,
        available_affordability=headroom,
        current_remaining_installments=current_terms,
        proposed_remaining_installments=proposed_terms,
        final_installment_amount=final_amount,
        execute_automatically=dynamic_top_up_consent,
        reason=(
            "Available affordability reduces the remaining term and is within the mandate ceiling."
            if dynamic_top_up_consent
            else "A beneficial top-up is available, but the mandate requires customer approval before increasing the deduction."
        ),
    )
