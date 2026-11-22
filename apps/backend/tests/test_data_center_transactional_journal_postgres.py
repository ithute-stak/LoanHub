"""Transactional journal certification using a throwaway PostgreSQL DB only."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]


def test_journal_capture_is_off_until_explicitly_approved():
    source = os.environ.get("LOANHUB_MIGRATION_CERTIFICATION_POSTGRES_URL")
    if os.environ.get("CI") != "true" or not source:
        pytest.skip("Requires explicit disposable PostgreSQL certification in CI")
    url = make_url(source)
    assert url.get_backend_name() == "postgresql"
    assert url.host in ("localhost", "127.0.0.1") and url.database == "loan_db"

    name = "loanhub_dc_cert_" + uuid4().hex[:16]
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    created = False
    try:
        with admin.connect() as con:
            con.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        env = os.environ.copy()
        database_url = url.set(database=name)
        env["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
        env["DB_NAME"] = name
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND, env=env, check=True, timeout=600,
        )

        engine = create_engine(database_url)
        try:
            company = uuid4()
            entity = uuid4()
            another_company = uuid4()
            with engine.begin() as con:
                inspector = inspect(con)
                for table in ("loanhub_dc_capture", "loanhub_dc_clock", "loanhub_dc_event"):
                    assert inspector.has_table(table)
                assert con.execute(text(
                    "SELECT count(*) FROM loanhub_dc_capture"
                )).scalar_one() == 0
                for table in (
                    "company_branches", "loan_products", "company_staff",
                    "company_borrower_accounts", "client_company_loan", "payment_transactions",
                ):
                    assert con.execute(text("""
                        SELECT count(*) FROM pg_trigger
                        WHERE tgrelid = CAST(:table_name AS regclass)
                          AND tgname = 'loanhub_dc_change_capture'
                          AND NOT tgisinternal
                    """), {"table_name": table}).scalar_one() == 1

                # Capture must do NOTHING before an operator opts a tenant in.
                con.execute(text("""
                    SELECT public.loanhub_dc_append_change(
                        :company, 'clients', :entity, NULL, 'created'
                    )
                """), {"company": company, "entity": entity})
                assert con.execute(text("SELECT count(*) FROM loanhub_dc_event")).scalar_one() == 0

                con.execute(text("""
                    INSERT INTO loanhub_dc_capture (company_id, enabled, enabled_at)
                    VALUES (:company, true, now())
                """), {"company": company})

                con.execute(text("""
                    SELECT public.loanhub_dc_append_change(
                        :company, 'clients', :entity, NULL, 'created'
                    )
                """), {"company": company, "entity": entity})
                con.execute(text("""
                    SELECT public.loanhub_dc_append_change(
                        :company, 'clients', :entity, NULL, 'updated'
                    )
                """), {"company": company, "entity": entity})
                events = con.execute(text("""
                    SELECT cursor, resource, action FROM loanhub_dc_event
                    WHERE company_id = :company ORDER BY cursor
                """), {"company": company}).all()
                assert events == [(1, "clients", "created"), (2, "clients", "updated")]
                assert con.execute(text("""
                    SELECT cursor FROM loanhub_dc_clock WHERE company_id = :company
                """), {"company": company}).scalar_one() == 2

            # A failed transaction must not leave a cursor or event gap.
            with engine.connect() as con:
                transaction = con.begin()
                con.execute(text("""
                    SELECT public.loanhub_dc_append_change(
                        :company, 'clients', :entity, NULL, 'deleted'
                    )
                """), {"company": company, "entity": entity})
                transaction.rollback()
            with engine.begin() as con:
                con.execute(text("""
                    SELECT public.loanhub_dc_append_change(
                        :company, 'clients', :entity, NULL, 'deleted'
                    )
                """), {"company": company, "entity": entity})
                assert con.execute(text("""
                    SELECT array_agg(cursor ORDER BY cursor) FROM loanhub_dc_event
                    WHERE company_id = :company
                """), {"company": company}).scalar_one() == [1, 2, 3]
                con.execute(text("""
                    SELECT public.loanhub_dc_append_change(
                        :company, 'clients', :entity, NULL, 'created'
                    )
                """), {"company": another_company, "entity": entity})
                assert con.execute(text("""
                    SELECT count(*) FROM loanhub_dc_event WHERE company_id = :company
                """), {"company": another_company}).scalar_one() == 0

                # RLS is enabled; actual tenant permission certification is
                # required before the replay API is activated.
                rows = con.execute(text("""
                    SELECT relname, relrowsecurity FROM pg_class
                    WHERE relname IN (
                        'loanhub_dc_capture', 'loanhub_dc_clock', 'loanhub_dc_event'
                    ) ORDER BY relname
                """)).all()
                assert len(rows) == 3 and all(enabled for _, enabled in rows)
        finally:
            engine.dispose()
    finally:
        if created:
            with admin.connect() as con:
                con.execute(text("""
                    SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                    WHERE datname = :database AND pid <> pg_backend_pid()
                """), {"database": name})
                con.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()
