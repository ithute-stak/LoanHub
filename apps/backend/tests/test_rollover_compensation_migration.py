"""Regression contracts for two append-only rollover ledger migrations."""
from pathlib import Path
from database.models.loan_rollover_compensation import LoanRolloverCompensation

ROOT=Path(__file__).resolve().parents[1]/"alembic/versions"
TRANSFER=(ROOT/"r8l1t2x3f467_loan_rollover_transfer_ledger.py").read_text()
COMPENSATION=(ROOT/"r8l1c2m4f467_loan_rollover_compensation.py").read_text()


def test_migration_chain_and_proper_pg_trigger():
    assert 'down_revision = "r8l1t2x3f467"' in COMPENSATION
    assert "LANGUAGE plpgsql AS $$" in TRANSFER
    assert "CREATE TRIGGER trg_rollover_compensation_immutable" in COMPENSATION


def test_compensation_requires_original_and_is_unique():
    table=LoanRolloverCompensation.__table__
    assert any(fk.target_fullname == "loan_rollover_transfers.id" for fk in table.c.transfer_id.foreign_keys)
    assert "uq_rollover_compensation_once" in COMPENSATION
    assert "ck_rollover_compensation_balances" in COMPENSATION


def test_compensation_has_no_live_execution_route():
    # The model and DDL are evidence-only. No automatic reversing of balances
    # is authorized until end-to-end accounting tests and approval flows pass.
    assert "op.create_table(" in COMPENSATION
    assert "loan_rollover_compensations" in COMPENSATION
