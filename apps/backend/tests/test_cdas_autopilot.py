from datetime import date
from decimal import Decimal

from services.cdas_autopilot import affordability_window_open, decide_cdas_autopilot


def test_affordability_window_is_14_through_20_inclusive() -> None:
    assert not affordability_window_open(date(2026, 10, 13))
    assert affordability_window_open(date(2026, 10, 14))
    assert affordability_window_open(date(2026, 10, 20))
    assert not affordability_window_open(date(2026, 10, 21))


def test_cash_payment_keeps_deduction_and_shortens_remaining_period() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("7000"),
        current_deduction=Decimal("1000"),
        evaluation_date=date(2026, 10, 7),
        dynamic_top_up_consent=False,
        payment_triggered=True,
    )

    assert decision.action == "shorten_term"
    assert decision.proposed_deduction == Decimal("1000.00")
    assert decision.proposed_remaining_installments == 7
    assert decision.final_installment_amount == Decimal("1000.00")
    assert decision.execute_automatically is True


def test_cash_settlement_requests_immediate_cdas_settlement() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("0"),
        current_deduction=Decimal("850"),
        evaluation_date=date(2026, 10, 7),
        dynamic_top_up_consent=True,
        payment_triggered=True,
    )

    assert decision.action == "settle"
    assert decision.proposed_deduction == Decimal("0.00")
    assert decision.proposed_remaining_installments == 0
    assert decision.execute_automatically is True


def test_pending_confirmed_cash_is_deducted_before_cdas_decision() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("1000"),
        pending_confirmed_payments=Decimal("1000"),
        current_deduction=Decimal("500"),
        evaluation_date=date(2026, 10, 17),
        dynamic_top_up_consent=True,
    )

    assert decision.action == "settle"
    assert decision.effective_balance == Decimal("0.00")


def test_affordability_of_ten_can_top_up_inside_window_when_consent_allows() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("500"),
        current_deduction=Decimal("100"),
        available_affordability=Decimal("10"),
        evaluation_date=date(2026, 10, 14),
        dynamic_top_up_consent=True,
    )

    assert decision.action == "top_up"
    assert decision.proposed_deduction == Decimal("110.00")
    assert decision.current_remaining_installments == 5
    assert decision.proposed_remaining_installments == 5 - 0 or decision.proposed_remaining_installments == 5
