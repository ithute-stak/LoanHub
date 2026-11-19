"""Isolated PostgreSQL constraints for durable individual CDAS attempts.

Never accesses production databases. Uses a TEMP table in an explicitly
configured disposable PostgreSQL CI database, then rolls everything back.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

DSN = os.getenv("LOANHUB_MIGRATION_CERTIFICATION_POSTGRES_URL")


@pytest.mark.skipif(not DSN or os.getenv("CI") != "true",
                    reason="Requires CI disposable PostgreSQL certification database")
def test_cdas_attempt_uniqueness_and_isolation_postgres():
    url = make_url(DSN)
    assert url.get_backend_name() == "postgresql"
    assert url.database == "loan_db"
    assert url.host in ("127.0.0.1", "localhost")
    engine = create_engine(url)
    a, b = str(uuid4()), str(uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TEMP TABLE cdas_aff_attempt_constraint_probe (
                    id uuid PRIMARY KEY,
                    company_id uuid NOT NULL,
                    idempotency_key varchar(120) NOT NULL,
                    request_fingerprint varchar(64) NOT NULL,
                    state varchar(24) NOT NULL,
                    UNIQUE (company_id, idempotency_key),
                    CHECK (state IN ('reserved', 'unknown', 'identity_review', 'completed'))
                ) ON COMMIT DROP
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX probe_unresolved_fingerprint
                ON cdas_aff_attempt_constraint_probe(company_id, request_fingerprint)
                WHERE state IN ('reserved', 'unknown')
            """))
            def insert(company, key, fp, state="reserved"):
                conn.execute(text("""
                    INSERT INTO cdas_aff_attempt_constraint_probe
                    VALUES (:id, :company, :key, :fingerprint, :state)
                """), {
                    "id": str(uuid4()), "company": company,
                    "key": key, "fingerprint": fp, "state": state,
                })
            insert(a, "first-key", "f" * 64)
            with pytest.raises(IntegrityError), conn.begin_nested():
                insert(a, "first-key", "g" * 64)
            with pytest.raises(IntegrityError), conn.begin_nested():
                insert(a, "second-key", "f" * 64)
            insert(b, "first-key", "f" * 64)  # company isolation
            insert(a, "third-key", "g" * 64, "completed")
            insert(a, "fourth-key", "g" * 64, "completed")  # historical records allowed
            assert conn.scalar(text(
                "SELECT count(*) FROM cdas_aff_attempt_constraint_probe"
            )) == 4
            with pytest.raises(IntegrityError), conn.begin_nested():
                insert(a, "invalid-status", "h" * 64, "replaying")
    finally:
        engine.dispose()
