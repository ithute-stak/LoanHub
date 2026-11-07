"""Disposable PostgreSQL tenant isolation/relational integrity tests.

This suite is NOT a production database migration or certification of
LoanHub's full tenant schema. Requires a disposable PostgreSQL CI database.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.pool import NullPool

URL = os.environ.get("LOANHUB_BATLOKOA_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not URL or not URL.startswith("postgresql+psycopg2://"),
    reason="Explicit disposable PostgreSQL CI URL required",
)

TENANT_A = UUID("4236a21f-5164-48aa-90f3-a35eccd23ae2")
TENANT_B = UUID("00000000-0000-4000-8000-000000000002")
LOAN_A = UUID("00000000-0000-4000-8000-000000000003")
BORROWER_A = UUID("00000000-0000-4000-8000-000000000004")
LOAN_B = UUID("00000000-0000-4000-8000-000000000005")
BORROWER_B = UUID("00000000-0000-4000-8000-000000000006")


@pytest.fixture
def isolated_tenant_database():
    suffix = uuid4().hex[:12]
    schema = f"phase37_{suffix}"
    actor = f"phase37_actor_{suffix}"
    admin = create_engine(URL, poolclass=NullPool)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE ROLE "{actor}" NOLOGIN NOBYPASSRLS'))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = create_engine(
        URL, poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        fixture_sql = (
            Path(__file__).parent / "fixtures" / "batlokoa_phase37_isolated_rls.sql"
        ).read_text(encoding="utf-8")
        with scoped.begin() as connection:
            for statement in fixture_sql.split(";"):
                # Avoid semicolons inside strings (fixture does not use any).
                if statement.strip():
                    connection.execute(text(statement))
            for company, loan, borrower in (
                (TENANT_A, LOAN_A, BORROWER_A),
                (TENANT_B, LOAN_B, BORROWER_B),
            ):
                connection.execute(text("INSERT INTO phase37_company VALUES (:c)"), {"c": company})
                connection.execute(
                    text("INSERT INTO phase37_loan VALUES (:c, :l)"),
                    {"c": company, "l": loan},
                )
                connection.execute(
                    text("INSERT INTO phase37_borrower VALUES (:c, :b)"),
                    {"c": company, "b": borrower},
                )
            connection.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{actor}"'))
            connection.execute(text(
                f'GRANT SELECT, INSERT ON phase37_reservation TO "{actor}"'
            ))
        yield scoped, actor
    finally:
        scoped.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            connection.execute(text(f'DROP ROLE IF EXISTS "{actor}"'))
        admin.dispose()


def as_actor(connection, actor: str, company: UUID | None, scope: str = "tenant"):
    connection.execute(text(f'SET LOCAL ROLE "{actor}"'))
    connection.execute(text(
        "SELECT set_config('loanhub.company_id', :company, true)"
    ), {"company": str(company) if company else ""})
    connection.execute(text(
        "SELECT set_config('loanhub.actor_scope', :scope, true)"
    ), {"scope": scope})


def insert_reservation(conn, *, company=TENANT_A, loan=LOAN_A,
                       borrower=BORROWER_A, key="collect_request_A123456"):
    conn.execute(text("""
        INSERT INTO phase37_reservation (
            reservation_id, company_id, loan_id, borrower_id, amount,
            request_fingerprint, idempotency_key
        ) VALUES (:id, :company, :loan, :borrower, 100.00,
                  :fp, :key)
    """), {"id": uuid4(), "company": company, "loan": loan,
           "borrower": borrower, "fp": "a" * 64, "key": key})


def count_visible(conn):
    return conn.scalar(text("SELECT count(*) FROM phase37_reservation"))


def test_tenant_can_only_see_own_company(isolated_tenant_database):
    db, actor = isolated_tenant_database
    with db.begin() as conn:
        as_actor(conn, actor, TENANT_A)
        insert_reservation(conn)
        assert count_visible(conn) == 1
    with db.begin() as conn:
        as_actor(conn, actor, TENANT_B)
        assert count_visible(conn) == 0
        insert_reservation(conn, company=TENANT_B, loan=LOAN_B,
                           borrower=BORROWER_B, key="collect_request_B123456")
        assert count_visible(conn) == 1
    with db.begin() as conn:
        as_actor(conn, actor, TENANT_A)
        assert count_visible(conn) == 1


def test_missing_scope_returns_no_records(isolated_tenant_database):
    db, actor = isolated_tenant_database
    with db.begin() as conn:
        insert_reservation(conn)  # fixture setup only, admin role
    with db.begin() as conn:
        conn.execute(text(f'SET LOCAL ROLE "{actor}"'))
        assert count_visible(conn) == 0
    with db.begin() as conn:
        as_actor(conn, actor, TENANT_A, scope="platform")
        assert count_visible(conn) == 0


def test_cross_tenant_insert_rejected_by_rls(isolated_tenant_database):
    db, actor = isolated_tenant_database
    with pytest.raises(ProgrammingError):
        with db.begin() as conn:
            as_actor(conn, actor, TENANT_A)
            insert_reservation(conn, company=TENANT_B,
                               loan=LOAN_B, borrower=BORROWER_B)


def test_composite_fk_rejects_mismatched_company_loan(isolated_tenant_database):
    db, actor = isolated_tenant_database
    with pytest.raises(IntegrityError):
        with db.begin() as conn:
            as_actor(conn, actor, TENANT_A)
            insert_reservation(conn, company=TENANT_A, loan=LOAN_B)


def test_composite_fk_rejects_mismatched_company_borrower(isolated_tenant_database):
    db, actor = isolated_tenant_database
    with pytest.raises(IntegrityError):
        with db.begin() as conn:
            as_actor(conn, actor, TENANT_A)
            insert_reservation(conn, company=TENANT_A, borrower=BORROWER_B)


def test_runtime_actor_cannot_update_or_delete(isolated_tenant_database):
    db, actor = isolated_tenant_database
    with db.begin() as conn:
        insert_reservation(conn)
    with pytest.raises(ProgrammingError):
        with db.begin() as conn:
            as_actor(conn, actor, TENANT_A)
            conn.execute(text(
                "UPDATE phase37_reservation SET amount = 20 WHERE company_id = :c"
            ), {"c": TENANT_A})
    with pytest.raises(ProgrammingError):
        with db.begin() as conn:
            as_actor(conn, actor, TENANT_A)
            conn.execute(text("DELETE FROM phase37_reservation"))


def test_scope_is_transaction_local(isolated_tenant_database):
    db, actor = isolated_tenant_database
    with db.begin() as conn:
        insert_reservation(conn)
    with db.begin() as conn:
        as_actor(conn, actor, TENANT_A)
        assert count_visible(conn) == 1
    with db.begin() as conn:
        conn.execute(text(f'SET LOCAL ROLE "{actor}"'))
        assert count_visible(conn) == 0
