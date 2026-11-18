"""Phase 74 opt-in PostgreSQL integration tests for normalized identity indexes.

Uses a one-off schema and synthetic rows. Does NOT read or write LoanHub
people/users, borrowers, loans, repayments, or other application records.
No staging DSN => skip. Never point this to a production database.
"""
from __future__ import annotations

import os
import re
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.atomic_new_client_registration import (
    AtomicRegistrationUnavailable, require_normalized_identity_constraints,
)

DSN = "LOANHUB_REGISTRATION_STAGING_POSTGRES_URL"
ACK = "LOANHUB_REGISTRATION_STAGING_ACK"


@pytest.fixture
def isolated_schema():
    url = os.getenv(DSN)
    if not url:
        pytest.skip("Dedicated disposable PostgreSQL staging database not configured")
    if os.getenv(ACK) != "isolated_disposable_database":
        pytest.skip("Explicit isolated-database acknowledgement is required")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        if engine.dialect.name != "postgresql":
            pytest.skip("PostgreSQL required")
        with engine.connect() as conn:
            database_name = conn.execute(text("SELECT current_database()")).scalar_one()
        if not re.search(r"(?:_test|_ci|_sandbox)$", database_name, re.I):
            pytest.skip("Database name must end _test, _ci or _sandbox")

        schema = "loanhub_phase74_" + uuid4().hex[:14]
        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        try:
            with engine.begin() as conn:
                conn.execute(text(f"""
                    CREATE TABLE {schema}.people (
                        id bigserial PRIMARY KEY,
                        national_id text,
                        passport_number text
                    )
                """))
                conn.execute(text(f"""
                    CREATE TABLE {schema}.users (
                        id bigserial PRIMARY KEY,
                        phone text NOT NULL,
                        email text
                    )
                """))
            yield engine, schema
        finally:
            with engine.begin() as conn:
                conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    finally:
        engine.dispose()


_INDEXES = (
    ("people", "national_id", "uq_people_national_id_normalized"),
    ("people", "passport_number", "uq_people_passport_normalized"),
    ("users", "phone", "uq_users_phone_normalized"),
    ("users", "email", "uq_users_email_normalized"),
)


def install_fixture_indexes(engine, schema):
    # Only UUID-generated isolated schema names are interpolated here.
    with engine.begin() as conn:
        for table, column, name in _INDEXES:
            conn.execute(text(f"""
                CREATE UNIQUE INDEX {name}
                ON {schema}.{table} (lower(btrim({column})))
                WHERE {column} IS NOT NULL AND btrim({column}) <> ''
            """))


def test_index_gate_requires_all_four_real_postgres_indexes(isolated_schema):
    engine, schema = isolated_schema
    with Session(engine) as session:
        session.execute(text(f"SET search_path TO {schema}"))
        with pytest.raises(AtomicRegistrationUnavailable):
            require_normalized_identity_constraints(session)
        session.rollback()

    install_fixture_indexes(engine, schema)
    with Session(engine) as session:
        session.execute(text(f"SET search_path TO {schema}"))
        require_normalized_identity_constraints(session)
        session.rollback()


@pytest.mark.parametrize("table,column,first,second", [
    ("people", "national_id", " NID-A1 ", "nid-a1"),
    ("people", "passport_number", " Pass-9 ", "PASS-9"),
    ("users", "phone", " 59000001 ", "59000001"),
    ("users", "email", " EXAMPLE@TEST.LS ", "example@test.ls"),
])
def test_normalized_duplicates_rollback_without_affecting_prior_row(
    isolated_schema, table, column, first, second,
):
    engine, schema = isolated_schema
    install_fixture_indexes(engine, schema)
    with engine.begin() as conn:
        if table == "users":
            conn.execute(text(
                f"INSERT INTO {schema}.users (phone, email) VALUES "
                "(:phone, :email)"
            ), {"phone": first if column == "phone" else "58000001",
                "email": first if column == "email" else None})
        else:
            conn.execute(text(
                f"INSERT INTO {schema}.people ({column}) VALUES (:value)"
            ), {"value": first})

        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                if table == "users":
                    conn.execute(text(
                        f"INSERT INTO {schema}.users (phone, email) "
                        "VALUES (:phone, :email)"
                    ), {"phone": second if column == "phone" else "58000002",
                        "email": second if column == "email" else None})
                else:
                    conn.execute(text(
                        f"INSERT INTO {schema}.people ({column}) VALUES (:value)"
                    ), {"value": second})
        assert conn.execute(text(
            f"SELECT count(*) FROM {schema}.{table}"
        )).scalar_one() == 1
        assert conn.execute(text(
            f"SELECT {column} FROM {schema}.{table}"
        )).scalar_one() == first


def test_failed_index_creation_preserves_original_rows(isolated_schema):
    engine, schema = isolated_schema
    with engine.begin() as conn:
        conn.execute(text(
            f"INSERT INTO {schema}.people (national_id) VALUES "
            "(' NID-1 '), ('nid-1')"
        ))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(f"""
                CREATE UNIQUE INDEX uq_people_national_id_normalized
                ON {schema}.people (lower(btrim(national_id)))
                WHERE national_id IS NOT NULL AND btrim(national_id) <> ''
            """))
    with engine.connect() as conn:
        assert conn.execute(text(
            f"SELECT count(*) FROM {schema}.people"
        )).scalar_one() == 2
