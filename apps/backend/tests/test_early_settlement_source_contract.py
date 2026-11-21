"""Source-contract guards for legacy early-settlement retention.

These tests intentionally avoid database writes and are not substitutes for
transactional integration tests. They protect the existing retention and
reversal assignments while the legacy opening-balance evidence is reviewed.
"""
import ast
from pathlib import Path


SERVICE = Path(__file__).resolve().parents[1] / "services" / "early_settlement_service.py"


def _function(name: str) -> ast.FunctionDef:
    module = ast.parse(SERVICE.read_text(encoding="utf-8"))
    return next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _assignments(function: ast.FunctionDef) -> set[str]:
    return {
        ast.unparse(target)
        for node in ast.walk(function)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
    }


def test_finalization_supersedes_without_erasing_paid_amount():
    function = _function("finalize_early_settlement_payment")
    assignments = _assignments(function)
    assert "installment.status" in assignments
    assert "installment.is_superseded" in assignments
    assert "installment.superseded_at" in assignments
    assert "installment.paid_amount" not in assignments


def test_reversal_restores_installment_paid_amount_and_supersession():
    function = _function("reverse_early_settlement")
    assignments = _assignments(function)
    assert {
        "installment.status",
        "installment.paid_amount",
        "installment.paid_at",
        "installment.is_superseded",
        "installment.superseded_at",
    }.issubset(assignments)


def test_snapshot_captures_paid_amount_and_supersession():
    function = _function("_installment_snapshot")
    keys = {
        key.value
        for node in ast.walk(function)
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert {"id", "status", "paid_amount", "paid_at", "is_superseded", "superseded_at"}.issubset(keys)
