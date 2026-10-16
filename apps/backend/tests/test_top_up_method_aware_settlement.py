from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from services.top_up_settlement import preview_top_up_settlement, replacement_principal


def test_replacement_principal_uses_quoted_settlement_not_scheduled_balance():
    quote = SimpleNamespace(settlement_amount=Decimal("866.67"))
    assert replacement_principal(quote, Decimal("200")) == Decimal("1066.67")
    with pytest.raises(HTTPException):
        replacement_principal(quote, Decimal("0"))


def test_quote_is_read_only_and_matches_existing_engine(monkeypatch):
    observed = {}

    def fake_quote(db, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(
            settlement_amount=Decimal("866.67"),
            overpayment_credit=Decimal("0.00"),
        )

    monkeypatch.setattr("services.top_up_settlement.quote_early_settlement", fake_quote)
    result = preview_top_up_settlement(
        Mock(), loan=SimpleNamespace(id="loan-1"), actor_user_id="operator-1"
    )
    assert result.settlement_amount == Decimal("866.67")
    assert observed["persist"] is False


def test_no_positive_credit_is_silently_rolled_into_topup(monkeypatch):
    monkeypatch.setattr(
        "services.top_up_settlement.quote_early_settlement",
        lambda *args, **kwargs: SimpleNamespace(
            settlement_amount=Decimal("0"),
            overpayment_credit=Decimal("10"),
        ),
    )
    with pytest.raises(HTTPException) as exc:
        preview_top_up_settlement(Mock(), loan=SimpleNamespace(id="loan-1"), actor_user_id="operator-1")
    assert exc.value.status_code == 409


def test_contract_integration_reuses_same_settlement_quote():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    router = (root / "routers/origination.py").read_text()
    service = (root / "services/loan_service.py").read_text()
    assert "requested_amount = replacement_principal(settlement_quote, top_up_cash_requested)" in router
    assert "application.requested_amount = replacement_principal(settlement_quote, cash_requested)" in router
    assert "settlement_quote = preview_top_up_settlement(" in service
    assert "settlement_amount = money(settlement_quote.settlement_amount)" in service


def test_thabo_micro_loan_uses_method_earned_interest_not_flat_rebate():
    from datetime import date
    from database.models.enums import LoanCalculationMethod
    from services.early_settlement_service import calculate_method_earned_interest
    from services.interest_calculation_service import calculate_loan_terms

    first = date(2026, 2, 1)
    due_dates = [date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)]
    earned, periods, _ = calculate_method_earned_interest(
        method=LoanCalculationMethod.MICRO_LOAN,
        principal=Decimal("1000"),
        rate_percent=Decimal("20"),
        original_term_months=3,
        start_date=date(2026, 1, 1),
        due_dates=due_dates,
        settlement_date=first,
    )
    assert periods == 1
    assert earned == Decimal("200.00")
    # Original contract M1,392, one successful installment M464.
    # Settlement uses principal + earned interest - actual payments.
    settlement = Decimal("1000") + earned - Decimal("464")
    assert settlement == Decimal("736.00")
    principal = replacement_principal(SimpleNamespace(settlement_amount=settlement), Decimal("200"))
    assert principal == Decimal("936.00")
    monthly, total, _ = calculate_loan_terms(
        principal=principal,
        rate_percent=Decimal("20"),
        term_months=2,
        interest_method=LoanCalculationMethod.MICRO_LOAN,
        start_date=date(2026, 2, 1),
        due_dates=[date(2026, 3, 1), date(2026, 4, 1)],
    )
    assert monthly == Decimal("617.76")
    assert total == Decimal("1235.52")
