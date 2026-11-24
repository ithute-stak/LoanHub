"""Restricted-role PostgreSQL proof for signed-contract row locking.

A SELECT-only, non-owner, NOBYPASSRLS issuer must not be silently treated
as capable of FOR SHARE. Do not grant UPDATE solely to make this pass: an
audited, scoped locking strategy is still required before activation.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


@pytest.mark.parametrize("table", (
    "client_company_loan", "loan_contracts", "managed_files",
))
def test_select_only_runtime_role_cannot_silently_acquire_share_lock(table):
    url = os.getenv("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Real PostgreSQL test URL required")
    engine = create_engine(url)
    suffix = uuid4().hex[:12]
    schema = "source_role_" + suffix
    role = "source_reader_" + suffix
    row_id = uuid4()
    try:
        # Roll back schema AND ephemeral role together; no persistent grants.
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(
                    f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB '
                    'NOCREATEROLE NOREPLICATION NOBYPASSRLS'
                ))
                conn.execute(text(
                    f'CREATE TABLE "{schema}"."{table}" '
                    '(id uuid PRIMARY KEY, version integer NOT NULL)'
                ))
                conn.execute(text(
                    f'INSERT INTO "{schema}"."{table}" VALUES (:id, 1)'
                ), {"id": row_id})
                conn.execute(text(
                    f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'
                ))
                conn.execute(text(
                    f'GRANT SELECT ON "{schema}"."{table}" TO "{role}"'
                ))
                conn.execute(text(f'SET LOCAL ROLE "{role}"'))
                assert conn.execute(text(
                    "SELECT rolbypassrls OR rolsuper "
                    "FROM pg_roles WHERE rolname = current_user"
                )).scalar_one() is False
                assert conn.execute(text(
                    f'SELECT version FROM "{schema}"."{table}" WHERE id=:id'
                ), {"id": row_id}).scalar_one() == 1
                # The exact locking syntax used by the Python adapters.
                savepoint = conn.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as denied:
                        conn.execute(text(
                            f'SELECT id FROM "{schema}"."{table}" '
                            'WHERE id=:id FOR SHARE NOWAIT'
                        ), {"id": row_id}).one()
                    # PostgreSQL reports insufficient privilege (42501).
                    assert getattr(denied.value.orig, "pgcode", None) == "42501" or (
                        getattr(denied.value.orig, "sqlstate", None) == "42501"
                    )
                finally:
                    savepoint.rollback()
                conn.execute(text("RESET ROLE"))
            finally:
                tx.rollback()
    finally:
        engine.dispose()
