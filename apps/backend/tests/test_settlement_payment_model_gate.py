"""The standard settlement endpoints must not charge Principal x% loans."""
import ast
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from payment_engine.principal_x_policy import PaymentModel
from services import settlement_payment_model_gate as gate


def _loan():
    return SimpleNamespace(id=uuid4(), company_id=uuid4())


def test_legacy_unassigned_and_explicit_existing_models_are_allowed(monkeypatch):
    for model in (PaymentModel.EXISTING,):
        called = []
        def read(db, *, loan_id, company_id):
            called.append((loan_id, company_id))
            return model
        monkeypatch.setattr(gate, "read_loan_payment_model", read)
        loan = _loan()
        gate.require_standard_settlement_model(object(), loan=loan)
        assert called == [(str(loan.id), str(loan.company_id))]


def test_principal_x_cannot_be_quoted_or_paid_by_standard_engine(monkeypatch):
    monkeypatch.setattr(
        gate, "read_loan_payment_model",
        lambda db, **kwargs: PaymentModel.PRINCIPAL_X,
    )
    with pytest.raises(HTTPException) as exc:
        gate.require_standard_settlement_model(object(), loan=_loan())
    assert exc.value.status_code == 409
    assert "Principal x%" in exc.value.detail


def test_corrupt_assignment_fails_closed(monkeypatch):
    def invalid(db, **kwargs):
        raise ValueError("Unknown persisted loan payment model")
    monkeypatch.setattr(gate, "read_loan_payment_model", invalid)
    with pytest.raises(HTTPException) as exc:
        gate.require_standard_settlement_model(object(), loan=_loan())
    assert exc.value.status_code == 409
    assert "invalid" in exc.value.detail


def test_both_live_early_settlement_endpoints_enforce_model_gate():
    source = (
        Path(__file__).resolve().parents[1] / "routers" / "loans.py"
    ).read_text(encoding="utf-8")
    module = ast.parse(source)
    for name in ("create_early_settlement_quote", "pay_early_settlement"):
        fn = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name)
        gates = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "require_standard_settlement_model"
        ]
        assert len(gates) == 1, name
