"""Execute the company-wide stale cash-session SQL against disposable PostgreSQL.

This covers actual SQL date comparison semantics rather than merely matching
query text. No LoanHub business tables or production data are used.
"""
import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from scripts.audit_branch_cash_readiness import STALE_SESSIONS_SQL, OUT_OF_RANGE_SESSIONS_SQL


def test_company_wide_open_session_scan_rejects_outside_today_and_bad_dates():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("Disposable PostgreSQL integration DSN not configured")
    engine = create_engine(dsn)
    schema = "cash_audit_probe_" + uuid4().hex[:14]
    company, other = uuid4(), uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            conn.execute(text("""
                CREATE TABLE company_operating_records (
                    company_id uuid NOT NULL,
                    module text NOT NULL,
                    record_type text NOT NULL,
                    status text NOT NULL,
                    data jsonb NOT NULL
                )
            """))
            entries = [
                (company, "open", "2026-10-21"),
                (company, "open", "2026-11-25"),
                (company, "open", "2026-12-01"),
                (company, "open", "not-a-date"),
                (company, "open", None),
                (company, "closed", "2026-10-21"),
                (other, "open", "2026-10-21"),
            ]
            for owner, status, business_day in entries:
                conn.execute(text("""
                    INSERT INTO company_operating_records
                        (company_id, module, record_type, status, data)
                    VALUES (:company, 'cash_control', 'daily_cash_session',
                            :status, jsonb_build_object('business_date', :day))
                """), {"company": owner, "status": status, "day": business_day})
            found = conn.execute(
                STALE_SESSIONS_SQL,
                {"company_id": str(company), "as_of": date(2026, 11, 25).isoformat()},
            ).scalar_one()
            assert found == 4
            excluded = conn.execute(
                OUT_OF_RANGE_SESSIONS_SQL,
                {"company_id": str(company), "from_date": "2026-11-25", "to_date": "2026-11-25"},
            ).scalar_one()
            assert excluded == 5  # old closed day is also outside the audit window
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            engine.dispose()
