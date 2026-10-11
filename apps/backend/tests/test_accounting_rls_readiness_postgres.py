"""Run the accounting RLS readiness audit against PostgreSQL's real catalog."""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.accounting_rls_readiness import accounting_rls_readiness


def test_accounting_rls_readiness_inspects_real_postgres_catalog():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN is not configured")
    engine = create_engine(dsn)
    with Session(engine) as db:
        result = accounting_rls_readiness(db)
        assert result["advisory_only"] is True
        assert set(result["tables"]) == {
            "accounting_accounts", "journal_entries", "journal_lines"
        }
        for name, details in result["tables"].items():
            assert isinstance(details["rls_enabled"], bool), name
            assert isinstance(details["policy_commands"], list), name
        assert result["ready"] == (not result["findings"])
        assert not db.new and not db.dirty and not db.deleted
    engine.dispose()
