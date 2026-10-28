"""Ensure the rollover ledger migration follows the verified revision and matches ORM constraints."""
from pathlib import Path
from database.models.loan_rollover_transfer import LoanRolloverTransfer

MIGRATION = Path(__file__).resolve().parents[1] / "alembic/versions/r8l1t2x3f467_loan_rollover_transfer_ledger.py"


def test_ledger_migration_uses_confirmed_single_head():
    source = MIGRATION.read_text()
    assert 'down_revision = "c7d2h4s6t820"' in source
    assert 'op.create_table(\n        "loan_rollover_transfers"' in source
    assert "op.create_index(" in source


def test_ledger_migration_includes_model_financial_constraints():
    source = MIGRATION.read_text()
    for constraint in LoanRolloverTransfer.__table__.constraints:
        if getattr(constraint, "name", None) and constraint.name.startswith(("ck_rollover_", "uq_rollover_")):
            assert constraint.name in source
    assert 'sa.ForeignKey("repayment_installments.id"' in source
    assert 'sa.ForeignKey("client_company_loan.id"' in source
