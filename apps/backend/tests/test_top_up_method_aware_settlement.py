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
