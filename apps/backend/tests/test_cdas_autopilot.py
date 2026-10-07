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


def test_affordability_of_ten_can_top_up_inside_window_when_it_saves_a_period() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("1200"),
        current_deduction=Decimal("100"),
        available_affordability=Decimal("10"),
        evaluation_date=date(2026, 10, 14),
        dynamic_top_up_consent=True,
    )

    assert decision.action == "top_up"
    assert decision.proposed_deduction == Decimal("110.00")
    assert decision.current_remaining_installments == 12
    assert decision.proposed_remaining_installments == 11
    assert decision.execute_automatically is True


def test_top_up_is_not_used_when_extra_affordability_saves_no_period() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("500"),
        current_deduction=Decimal("100"),
        available_affordability=Decimal("10"),
        evaluation_date=date(2026, 10, 14),
        dynamic_top_up_consent=True,
    )

    assert decision.action == "none"
    assert decision.proposed_deduction == Decimal("100.00")


def test_top_up_requires_dynamic_mandate_consent_for_auto_execution() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("12000"),
        current_deduction=Decimal("1000"),
        available_affordability=Decimal("500"),
        evaluation_date=date(2026, 10, 17),
        dynamic_top_up_consent=False,
    )

    assert decision.action == "top_up"
    assert decision.proposed_remaining_installments == 8
    assert decision.execute_automatically is False


def test_mandate_ceiling_limits_top_up() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("12000"),
        current_deduction=Decimal("1000"),
        available_affordability=Decimal("800"),
        evaluation_date=date(2026, 10, 17),
        dynamic_top_up_consent=True,
        mandate_maximum=Decimal("1400"),
    )

    assert decision.action == "top_up"
    assert decision.proposed_deduction == Decimal("1400.00")
    assert decision.proposed_remaining_installments == 9


def test_final_installment_is_capped_to_true_balance() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("2350"),
        current_deduction=Decimal("1000"),
        evaluation_date=date(2026, 10, 7),
        dynamic_top_up_consent=False,
        payment_triggered=True,
    )

    assert decision.action == "shorten_term"
    assert decision.proposed_remaining_installments == 3
    assert decision.final_installment_amount == Decimal("350.00")


def test_no_affordability_top_up_outside_14_to_20_window() -> None:
    decision = decide_cdas_autopilot(
        outstanding_balance=Decimal("12000"),
        current_deduction=Decimal("1000"),
        available_affordability=Decimal("500"),
        evaluation_date=date(2026, 10, 21),
        dynamic_top_up_consent=True,
    )

    assert decision.action == "none"
    assert decision.execute_automatically is False
