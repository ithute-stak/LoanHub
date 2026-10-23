"""Regression checks for the early-settlement payment router/service interface."""

import ast
import inspect
from pathlib import Path

from services.early_settlement_service import initiate_early_settlement_payment


def test_early_settlement_router_passes_only_supported_service_arguments():
    router_path = Path(__file__).resolve().parents[1] / "routers" / "loans.py"
    module = ast.parse(router_path.read_text(encoding="utf-8"))
    endpoint = next(
        node for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "pay_early_settlement"
    )
    calls = [
        node for node in ast.walk(endpoint)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "initiate_early_settlement_payment"
    ]
    assert len(calls) == 1
    call = calls[0]
    assert all(keyword.arg is not None for keyword in call.keywords)
    provided = {keyword.arg for keyword in call.keywords}
    accepted = set(inspect.signature(initiate_early_settlement_payment).parameters)
    assert provided <= accepted
    assert "owner_override_verified" not in provided
    assert "owner_override_reason" not in provided
