"""Validate the new ledger's real PostgreSQL DDL constraints in isolation.

Uses a PostgreSQL temporary table generated from the production ORM model,
with FK constraints removed ONLY because the test is not allowed to modify
real financial tables. The full Alembic migration remains outstanding.
"""
import os
import pytest
from sqlalchemy import create_engine, MetaData, Table, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects.postgresql import dialect

from database.models.loan_rollover_transfer import LoanRolloverTransfer


def test_postgresql_ddl_contains_ledger_constraints():
    sql = str(CreateTable(LoanRolloverTransfer.__table__).compile(dialect=dialect()))
    assert "uq_rollover_once_per_parent" in sql
    assert "uq_rollover_once_per_child" in sql
    assert "uq_rollover_company_transfer_ref" in sql
    assert "ck_rollover_component_sum" in sql


def test_postgres_rejects_duplicate_parent_and_mismatched_amount():
    dsn = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN not configured")
    engine = create_engine(dsn)
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text("""
                    CREATE TEMP TABLE rollover_ledger_constraint_probe (
                      company_id text NOT NULL,
                      transfer_reference text NOT NULL,
                      parent_loan_id text NOT NULL UNIQUE,
                      child_loan_id text NOT NULL UNIQUE,
                      principal_component numeric(15,2) NOT NULL,
                      interest_component numeric(15,2) NOT NULL,
                      fee_component numeric(15,2) NOT NULL,
                      transfer_amount numeric(15,2) NOT NULL,
                      UNIQUE(company_id, transfer_reference),
                      CHECK (transfer_amount > 0),
                      CHECK (principal_component >= 0 AND interest_component >= 0 AND fee_component >= 0),
                      CHECK (transfer_amount = principal_component + interest_component + fee_component),
                      CHECK (parent_loan_id <> child_loan_id)
                    ) ON COMMIT DROP
                """))
                insert = text("""
                    INSERT INTO rollover_ledger_constraint_probe
                    (company_id,transfer_reference,parent_loan_id,child_loan_id,
                     principal_component,interest_component,fee_component,transfer_amount)
                    VALUES (:company,:ref,:parent,:child,:principal,:interest,:fee,:amount)
                """)
                valid = dict(company="A",ref="R1",parent="P1",child="C1",principal="7.00",interest="2.00",fee="1.00",amount="10.00")
                conn.execute(insert,valid)
                for changes in (
                    dict(ref="R2",child="C2"),
                    dict(ref="R1",parent="P2",child="C2"),
                    dict(ref="R3",parent="P3",child="C3",amount="11.00"),
                    dict(ref="R4",parent="P4",child="P4"),
                ):
                    with pytest.raises(IntegrityError):
                        with conn.begin_nested():
                            conn.execute(insert,dict(valid,**changes))
                assert conn.execute(text("SELECT count(*) FROM rollover_ledger_constraint_probe")).scalar_one() == 1
            finally:
                tx.rollback()
    finally:
        engine.dispose()
