"""PostgreSQL concurrency regression for ledger-scope transaction locks."""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from services.accounting_service import _lock_journal_scope


def test_journal_scope_lock_blocks_another_transaction():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL accounting test DSN not configured")
    engine = create_engine(dsn, pool_size=2, max_overflow=0)
    key = "company:concurrency-probe"
    sql = text("SELECT pg_try_advisory_xact_lock(hashtextextended(:scope, 20261012))")
    params = {"scope": f"loanhub:journal:{key}"}
    try:
        with engine.connect() as first, engine.connect() as second:
            with first.begin():
                _lock_journal_scope(Session(bind=first), key)
                with second.begin():
                    assert second.execute(sql, params).scalar() is False
                    assert second.execute(sql, {
                        "scope": "loanhub:journal:company:other"
                    }).scalar() is True
            with second.begin():
                assert second.execute(sql, params).scalar() is True
    finally:
        engine.dispose()
