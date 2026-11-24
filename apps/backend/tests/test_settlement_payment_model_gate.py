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



def test_principal_x_preview_route_requires_assigned_model_and_is_read_only():
    source = (
        Path(__file__).resolve().parents[1] / "routers" / "loans.py"
    ).read_text(encoding="utf-8")
    module = ast.parse(source)
    fn = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "preview_principal_x_settlement"
    )
    calls = {
        node.func.id for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "read_loan_payment_model" in calls
    assert "quote_principal_x_for_loan_with_revision" in calls
    assert "require_tenant_roles" in calls
    assert "_tenant_loan_or_404" in calls
    assert "initiate_early_settlement_payment" not in calls
    assert "initiate_gateway_payment" not in calls


def test_principal_x_example_1500_at_20_percent_second_period():
    from datetime import date
    from decimal import Decimal

    from payment_engine.principal_x_settlement import DatedCredit, quote_principal_x

    quote = quote_principal_x(
        principal=Decimal("1500"),
        rate_percent=Decimal("20"),
        due_dates=[
            date(2026, 10, 20),
            date(2026, 11, 20),
            date(2026, 12, 20),
        ],
        settlement_date=date(2026, 11, 21),
        successful_credits=[DatedCredit(date(2026, 10, 20), Decimal("696"))],
        contractual_total=Decimal("2088"),
    )
    assert quote.period == 2
    assert quote.total_credited == Decimal("696.00")
    assert quote.collectible_due == Decimal("1324.80")
    assert quote.contractual_remaining == Decimal("1392.00")



def test_core_settlement_service_checks_assignment_at_all_mutation_boundaries():
    service_path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "early_settlement_service.py"
    )
    module = ast.parse(service_path.read_text(encoding="utf-8"))
    for name in (
        "quote_early_settlement",
        "initiate_early_settlement_payment",
        "finalize_early_settlement_payment",
    ):
        fn = next(
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        gates = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "require_standard_settlement_model"
        ]
        assert len(gates) == 1, name
        # Check occurs before changes to the payment state or quote record.
        if name == "initiate_early_settlement_payment":
            commits = [
                node.lineno for node in ast.walk(fn)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "commit"
            ]
            assert commits and gates[0].lineno < min(commits), name
        if name == "finalize_early_settlement_payment":
            statuses = [
                node.lineno for node in ast.walk(fn)
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Attribute) and target.attr == "status"
                    for target in node.targets
                )
            ]
            assert statuses and gates[0].lineno < min(statuses), name



def test_principal_x_readiness_is_tenant_scoped_and_never_postable():
    """Readiness must not be mistaken for authorization to collect."""
    source = (
        Path(__file__).resolve().parents[1] / "routers" / "loans.py"
    ).read_text(encoding="utf-8")
    module = ast.parse(source)
    fn = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "principal_x_settlement_readiness"
    )
    calls = {
        node.func.id for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {"require_tenant_roles", "_tenant_loan_or_404", "read_loan_payment_model",
            "inspect_loanhub_payment_evidence"} <= calls
    assert "initiate_early_settlement_payment" not in calls
    assert "coordinate_principal_x_collection" not in calls
    assert any(
        isinstance(node, ast.keyword)
        and node.arg == "can_post_settlement"
        and isinstance(node.value, ast.Constant)
        and node.value.value is False
        for node in ast.walk(fn)
    )


def test_principal_x_readiness_schema_rejects_true_posting_capability():
    from database.schemas.early_settlement import PrincipalXSettlementReadinessRead
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PrincipalXSettlementReadinessRead(
            loan_id=uuid4(), payment_model="principal_x",
            can_post_settlement=True, payment_rows_reviewed=0,
            unresolved_payment_rows=0, blocking_reasons=[],
        )


def test_revalidation_endpoint_is_scoped_to_principal_x_and_never_posts():
    source = (
        Path(__file__).resolve().parents[1] / "routers" / "loans.py"
    ).read_text(encoding="utf-8")
    module = ast.parse(source)
    fn = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "revalidate_principal_x_settlement"
    )
    calls = {
        node.func.id for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {
        "require_tenant_roles", "_tenant_loan_or_404",
        "read_loan_payment_model",
        "quote_principal_x_for_loan_with_revision",
        "require_unchanged_preview_snapshot",
    } <= calls
    assert "initiate_early_settlement_payment" not in calls
    assert "coordinate_principal_x_collection" not in calls
    assert any(
        isinstance(node, ast.keyword)
        and node.arg == "payment_enabled"
        and isinstance(node.value, ast.Constant)
        and node.value.value is False
        for node in ast.walk(fn)
    )


def test_revalidation_response_cannot_enable_payment():
    from datetime import date
    from decimal import Decimal
    from pydantic import ValidationError
    from database.schemas.early_settlement import (
        PrincipalXSettlementRevalidateRequest,
        PrincipalXSettlementRevalidateRead,
    )

    payload = PrincipalXSettlementRevalidateRequest(
        settlement_date=date(2026, 11, 21),
        snapshot_revision="a" * 64,
    )
    assert payload.snapshot_revision == "a" * 64
    with pytest.raises(ValidationError):
        PrincipalXSettlementRevalidateRequest(
            settlement_date=date(2026, 11, 21),
            snapshot_revision="invalid",
        )
    with pytest.raises(ValidationError):
        PrincipalXSettlementRevalidateRead(
            loan_id=uuid4(),
            snapshot_revision="a" * 64,
            settlement_date=date(2026, 11, 21),
            settlement_amount=Decimal("1324.80"),
            payment_enabled=True,
        )
