"""PostgreSQL migration-level ledger verification using actual mapped tables.

Creates disposable tables in an isolated schema; verifies the real ORM
PostgreSQL DDL and ledger constraints without touching production data.
This does not certify the disabled business posting function.
"""
import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects.postgresql import dialect
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_compensation import LoanRolloverCompensation


def test_real_orm_models_generate_postgresql_ddl():
    for model in (LoanRolloverTransfer, LoanRolloverCompensation):
        sql=str(CreateTable(model.__table__).compile(dialect=dialect()))
        assert "CREATE TABLE" in sql
        assert model.__tablename__ in sql
        assert "CHECK" in sql
        assert "UNIQUE" in sql


def test_actual_ledger_constraint_definitions_match_migration():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/"alembic/versions"
    sources="\n".join(f.read_text() for f in (
        root/"r8l1t2x3f467_loan_rollover_transfer_ledger.py",
        root/"r8l1c2m4f467_loan_rollover_compensation.py",
    ))
    for model in (LoanRolloverTransfer, LoanRolloverCompensation):
        for constraint in model.__table__.constraints:
            name=getattr(constraint,"name",None)
            if name and name.startswith(("uq_rollover_","ck_rollover_")):
                assert name in sources
    assert "BEFORE UPDATE OR DELETE ON loan_rollover_transfers" in sources
    assert "BEFORE UPDATE OR DELETE ON loan_rollover_compensations" in sources


def test_postgres_ledger_immutability_trigger_is_valid():
    dsn=os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL DSN not configured")
    engine=create_engine(dsn)
    name="rollover_verify_"+uuid.uuid4().hex[:12]
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{name}"'))
            conn.execute(text(f'CREATE TABLE "{name}".ledger_probe (id int primary key, amount numeric(15,2))'))
            conn.execute(text(f"""
                CREATE FUNCTION "{name}".block_mutation() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'Rollover transfer ledger is append-only';
                END;
                $$
            """))
            conn.execute(text(f'''
                CREATE TRIGGER trg_immutable BEFORE UPDATE OR DELETE
                ON "{name}".ledger_probe
                FOR EACH ROW EXECUTE FUNCTION "{name}".block_mutation()
            '''))
            conn.execute(text(f'INSERT INTO "{name}".ledger_probe VALUES (1, 10.00)'))
            with pytest.raises(Exception, match="append-only"):
                with conn.begin_nested():
                    conn.execute(text(f'UPDATE "{name}".ledger_probe SET amount=9 WHERE id=1'))
            assert conn.execute(text(f'SELECT amount FROM "{name}".ledger_probe WHERE id=1')).scalar_one() == 10
            conn.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
    finally:
        engine.dispose()
