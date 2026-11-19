"""Offline migration safety checks; no database required."""
import ast
from pathlib import Path

from scripts.audit_principal_x_alembic_graph import audit_graph


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/p1x2m3o4d590_principal_x_payment_model_tables.py"
)


def test_principal_x_migration_extends_verified_head():
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    assignments = {
        node.target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "p1x2m3o4d590",
        "down_revision": "a1r2i3d4e690",
    }


def test_principal_x_migration_graph_remains_single_head():
    heads, errors, count = audit_graph(MIGRATION.parent)
    assert count >= 154
    assert not errors, errors
    assert heads == ["p1x2m3o4d590"]


def test_principal_x_migration_is_schema_only():
    source = MIGRATION.read_text(encoding="utf-8")
    for forbidden in (
        "op.execute(",
        "op.bulk_insert(",
        "UPDATE loan",
        "INSERT INTO",
        "DELETE FROM",
    ):
        assert forbidden not in source
    assert "server_default=\"existing\"" in source
    assert 'server_default=sa.text("false")' in source


def test_principal_x_migration_enforces_tenant_ownership():
    source = MIGRATION.read_text(encoding="utf-8")
    assert '"fk_loan_payment_model_assignment_owner"' in source
    assert '"uq_client_loan_id_company"' in source
    assert '"uq_loan_payment_model_assignment_loan"' in source
