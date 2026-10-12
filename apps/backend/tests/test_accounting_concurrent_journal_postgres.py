"""PostgreSQL concurrent journal-allocation integration test.

Exercises transaction lock, reference-idempotency, and unique journal-number
allocation using a disposable, isolated shared table. This is not a substitute
for an end-to-end test of the full ORM posting service.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from services.accounting_service import _lock_journal_scope


def test_simultaneous_posting_same_reference_creates_one_balanced_journal():
    dsn = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN not configured")
    engine = create_engine(dsn, pool_size=3, max_overflow=0)
    suffix = uuid4().hex[:16]
    table = f"journal_concurrency_probe_{suffix}"
    scope = f"company:{suffix}"
    gate = Barrier(2)
    with engine.begin() as conn:
        conn.execute(text(f"""CREATE TABLE {table} (
            id bigserial PRIMARY KEY, scope text NOT NULL,
            entry_number text NOT NULL, reference text NOT NULL,
            debit numeric(18,2) NOT NULL, credit numeric(18,2) NOT NULL,
            UNIQUE (scope, entry_number), UNIQUE (scope, reference),
            CHECK (debit > 0 AND debit = credit)
        )"""))

    def worker():
        gate.wait(timeout=10)
        with Session(engine) as db:
            with db.begin():
                _lock_journal_scope(db, scope)
                existing = db.execute(text(
                    f"SELECT id FROM {table} WHERE scope=:scope AND reference=:reference"
                ), {"scope": scope, "reference": "payment-one"}).scalar()
                if existing is not None:
                    return existing
                count = db.execute(
                    text(f"SELECT count(*) FROM {table} WHERE scope=:scope"),
                    {"scope": scope},
                ).scalar_one()
                return db.execute(text(f"""INSERT INTO {table}
                    (scope, entry_number, reference, debit, credit)
                    VALUES (:scope, :number, :reference, :debit, :credit)
                    RETURNING id"""), {
                        "scope": scope, "number": f"JRN-{date.today():%Y%m}-{count+1:06d}",
                        "reference": "payment-one", "debit": Decimal("250.25"),
                        "credit": Decimal("250.25"),
                }).scalar_one()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            ids = [future.result(timeout=20) for future in futures]
        assert ids[0] == ids[1]
        with engine.connect() as db:
            result = db.execute(text(f"""
                SELECT count(*), sum(debit), sum(credit) FROM {table}
            """)).one()
            assert result == (1, Decimal("250.25"), Decimal("250.25"))
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        engine.dispose()
