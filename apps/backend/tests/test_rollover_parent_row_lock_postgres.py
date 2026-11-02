"""PostgreSQL row-lock contention contract for rollover parent serialization.

Uses two *independent* PostgreSQL connections, not a mocked query object.
This proves the database rejects a competing NOWAIT writer while the first
writer holds the parent lock. It does not enable either production entrypoint.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def test_rollover_parent_lock_prevents_parallel_writer_and_releases_after_commit():
    url = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL integration URL not configured")
    engine = create_engine(url, pool_size=2, max_overflow=0)
    schema = "rollover_lock_" + uuid4().hex[:12]
    loan_id = uuid4()
    try:
        with engine.begin() as setup:
            setup.execute(text(f'CREATE SCHEMA "{schema}"'))
            setup.execute(text(f'CREATE TABLE "{schema}".client_company_loan '
                               '(id uuid PRIMARY KEY, balance numeric(15,2) NOT NULL)'))
            setup.execute(text(f'INSERT INTO "{schema}".client_company_loan '
                               '(id, balance) VALUES (:id, 60)'), {"id": loan_id})

        lock_sql = text(f'SELECT balance FROM "{schema}".client_company_loan '
                        'WHERE id=:id FOR UPDATE NOWAIT')
        with engine.connect() as first, engine.connect() as second:
            tx_first = first.begin()
            try:
                assert first.execute(lock_sql, {"id": loan_id}).scalar_one() == 60
                tx_second = second.begin()
                try:
                    with pytest.raises(OperationalError) as conflict:
                        second.execute(lock_sql, {"id": loan_id}).scalar_one()
                    assert getattr(conflict.value.orig, "pgcode", None) == "55P03" or (
                        getattr(conflict.value.orig, "sqlstate", None) == "55P03"
                    ), "PostgreSQL must reject a locked parent row (55P03)"
                finally:
                    tx_second.rollback()
            finally:
                tx_first.commit()

            # The competing transaction can now lock the same parent.
            with second.begin():
                assert second.execute(lock_sql, {"id": loan_id}).scalar_one() == 60
                second.execute(text(f'UPDATE "{schema}".client_company_loan '
                                    'SET balance=59 WHERE id=:id'), {"id": loan_id})
        with engine.connect() as verify:
            assert verify.execute(text(f'SELECT balance FROM "{schema}".client_company_loan '
                                       'WHERE id=:id'), {"id": loan_id}).scalar_one() == 59
    finally:
        with engine.begin() as cleanup:
            cleanup.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
