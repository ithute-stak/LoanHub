"""Real PostgreSQL concurrency smoke test for signed-document row locking.

Uses disposable schema + two independent connections. No production tables are
modified. The goal is to certify actual PostgreSQL FOR SHARE NOWAIT behavior
and visibility of conflicting updates, not to simulate it with Mock objects.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


@pytest.mark.parametrize("table", ["client_company_loan", "loan_contracts", "managed_files"])
def test_shared_source_lock_blocks_concurrent_mutation_on_postgresql(table):
    url = os.getenv("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Real PostgreSQL test URL required")
    engine = create_engine(url, pool_size=2, max_overflow=0)
    schema = "contract_lock_" + uuid4().hex[:12]
    target_id = uuid4()
    try:
        # Create and commit disposable fixtures so both connections see them.
        with engine.begin() as setup:
            setup.execute(text(f'CREATE SCHEMA "{schema}"'))
            for name in ("client_company_loan", "loan_contracts", "managed_files"):
                setup.execute(text(
                    f'CREATE TABLE "{schema}"."{name}" '
                    '(id uuid PRIMARY KEY, version integer NOT NULL DEFAULT 1)'
                ))
                setup.execute(text(
                    f'INSERT INTO "{schema}"."{name}" (id, version) VALUES (:id, 1)'
                ), {"id": target_id})

        with engine.connect() as reader, engine.connect() as writer:
            read_tx = reader.begin()
            write_tx = writer.begin()
            try:
                # Match the registration-time SQLAlchemy read=True, nowait=True
                # lock semantics; keep this lock held until commit/rollback.
                reader.execute(text(
                    f'SELECT id FROM "{schema}"."{table}" '
                    'WHERE id = :id FOR SHARE NOWAIT'
                ), {"id": target_id}).one()
                writer.execute(text("SET LOCAL lock_timeout = '150ms'"))
                savepoint = writer.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as locked:
                        writer.execute(text(
                            f'UPDATE "{schema}"."{table}" SET version = 2 WHERE id = :id'
                        ), {"id": target_id})
                    assert locked.value.orig is not None
                finally:
                    savepoint.rollback()
                # No concurrent change became visible.
                assert reader.execute(text(
                    f'SELECT version FROM "{schema}"."{table}" WHERE id = :id'
                ), {"id": target_id}).scalar_one() == 1
            finally:
                write_tx.rollback()
                read_tx.rollback()
        # Once the reader transaction closes the lock is gone.
        with engine.begin() as free:
            free.execute(text(
                f'UPDATE "{schema}"."{table}" SET version = 2 WHERE id = :id'
            ), {"id": target_id})
            assert free.execute(text(
                f'SELECT version FROM "{schema}"."{table}" WHERE id = :id'
            ), {"id": target_id}).scalar_one() == 2
    finally:
        try:
            with engine.begin() as teardown:
                teardown.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            engine.dispose()
