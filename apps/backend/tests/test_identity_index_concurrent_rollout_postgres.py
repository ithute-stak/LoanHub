"""Phase 78: PostgreSQL CREATE UNIQUE INDEX CONCURRENTLY rollout rehearsal.

Opt-in tests against an ephemeral, explicitly acknowledged *_sandbox DB only.
Every object is synthetic inside a random schema. Never inspect or alter
LoanHub's real public.people, public.users or historical financial tables.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, DBAPIError

DSN = "LOANHUB_REGISTRATION_ROLLOUT_SANDBOX_URL"
ACK = "LOANHUB_REGISTRATION_ROLLOUT_SANDBOX_ACK"
ACK_VALUE = "isolated_disposable_database"

CASES = (
    ("people", "national_id", "uq_people_national_id_normalized"),
    ("people", "passport_number", "uq_people_passport_normalized"),
    ("users", "phone", "uq_users_phone_normalized"),
    ("users", "email", "uq_users_email_normalized"),
)


@pytest.fixture
def rollout():
    url = os.getenv(DSN)
    if not url or os.getenv(ACK) != ACK_VALUE:
        pytest.skip("Disposable rollout sandbox not configured and acknowledged")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        if engine.dialect.name != "postgresql":
            pytest.skip("Isolated PostgreSQL required")
        with engine.connect() as connection:
            db_name = connection.execute(text("SELECT current_database()")).scalar_one()
            if not db_name.endswith("_sandbox"):
                pytest.skip("Database name must end with _sandbox")
            if connection.execute(text("SELECT pg_is_in_recovery()")).scalar_one():
                pytest.skip("Rehearsal requires a writable isolated PostgreSQL server")
        schema = "identity_rollout_" + uuid4().hex[:16]
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
            connection.execute(text(
                f"CREATE TABLE {schema}.people (id bigint generated always as identity primary key, "
                "national_id text, passport_number text)"
            ))
            connection.execute(text(
                f"CREATE TABLE {schema}.users (id bigint generated always as identity primary key, "
                "phone text, email text)"
            ))
        yield engine, schema
    finally:
        if "schema" in locals():
            with engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        engine.dispose()


def _unique_index(engine, schema, table, column, name):
    # Constant identifiers and generated schema only; never user-supplied SQL.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(
            f"CREATE UNIQUE INDEX CONCURRENTLY {name} ON {schema}.{table} "
            f"(lower(btrim({column}))) "
            f"WHERE {column} IS NOT NULL AND btrim({column}) <> ''"
        ))


def _drop_index(engine, schema, name):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {schema}.{name}"))


def _index_state(engine, schema, name):
    with engine.connect() as connection:
        return connection.execute(text("""
            SELECT i.indisunique, i.indisvalid, i.indisready
            FROM pg_index i
            JOIN pg_class idx ON idx.oid = i.indexrelid
            JOIN pg_namespace ns ON ns.oid = idx.relnamespace
            WHERE ns.nspname = :schema AND idx.relname = :name
        """), {"schema": schema, "name": name}).one_or_none()


@pytest.mark.parametrize("table,column,name", CASES)
def test_concurrent_rollout_and_normalized_duplicate_rejection(
    rollout, table, column, name,
):
    engine, schema = rollout
    with engine.begin() as connection:
        connection.execute(text(
            f"INSERT INTO {schema}.{table} ({column}) VALUES "
            "('  SAMPLE-1  ')"
        ))
    _unique_index(engine, schema, table, column, name)
    assert _index_state(engine, schema, name) == (True, True, True)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text(
                f"INSERT INTO {schema}.{table} ({column}) VALUES "
                "('sample-1')"
            ))
    with engine.connect() as connection:
        rows = connection.execute(text(
            f"SELECT {column} FROM {schema}.{table}"
        )).scalars().all()
    assert rows == ["  SAMPLE-1  "]
    _drop_index(engine, schema, name)
    assert _index_state(engine, schema, name) is None


@pytest.mark.parametrize("table,column,name", CASES)
def test_failed_concurrent_build_invalid_index_cleanup_preserves_rows(
    rollout, table, column, name,
):
    engine, schema = rollout
    with engine.begin() as connection:
        connection.execute(text(
            f"INSERT INTO {schema}.{table} ({column}) "
            "VALUES ('  SAME-ID '), ('same-id')"
        ))
    with pytest.raises((IntegrityError, DBAPIError)):
        _unique_index(engine, schema, table, column, name)
    # A failed concurrent unique index can remain INVALID. It must not be
    # mistaken for a ready uniqueness guard. Operators may need to remove it.
    state = _index_state(engine, schema, name)
    assert state is None or state[1] is False
    _drop_index(engine, schema, name)
    assert _index_state(engine, schema, name) is None
    with engine.connect() as connection:
        rows = connection.execute(text(
            f"SELECT {column} FROM {schema}.{table} ORDER BY id"
        )).scalars().all()
    assert rows == ["  SAME-ID ", "same-id"]


def test_actual_postgres_index_audit_matches_registration_writer(rollout):
    """Same real index metadata must satisfy both the read-only audit and writer.

    This exercises actual pg_index state in disposable PostgreSQL, not mocked
    index rows. No registration occurs; nothing reaches production.
    """
    from types import SimpleNamespace
    from unittest.mock import patch

    from sqlalchemy.orm import Session
    from services.atomic_new_client_registration import (
        AtomicRegistrationUnavailable, require_normalized_identity_constraints,
    )
    from services.identity_index_readiness import inspect_identity_index_readiness

    engine, schema = rollout
    clean = SimpleNamespace(
        person_national_id_groups=0, person_passport_groups=0,
        user_phone_groups=0, user_email_groups=0,
    )

    def verify(*, expected_ready):
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text(f"SET LOCAL search_path TO {schema}"))
                with Session(bind=connection) as db:
                    with db.begin():
                        with patch(
                            "services.identity_index_readiness.inspect_identity_collisions",
                            return_value=clean,
                        ):
                            report = inspect_identity_index_readiness(db)
                        if expected_ready:
                            assert len(report.present_valid_indexes) == 4
                            assert report.missing_or_invalid_indexes == ()
                            require_normalized_identity_constraints(db)
                        else:
                            assert report.missing_or_invalid_indexes
                            with pytest.raises(AtomicRegistrationUnavailable):
                                require_normalized_identity_constraints(db)
                        assert report.registration_enabled is False
                        assert report.safe_to_apply_migration is False

    verify(expected_ready=False)
    for table, column, name in CASES:
        _unique_index(engine, schema, table, column, name)
    verify(expected_ready=True)

    # A structurally valid index with the WRONG partial predicate must not
    # be accepted, even though PostgreSQL marks it unique, valid and ready.
    _drop_index(engine, schema, "uq_people_national_id_normalized")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(
            f"CREATE UNIQUE INDEX CONCURRENTLY "
            f"uq_people_national_id_normalized ON {schema}.people "
            f"(lower(btrim(national_id))) WHERE national_id IS NULL"
        ))
    verify(expected_ready=False)
