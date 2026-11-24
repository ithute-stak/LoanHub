"""Exercise legacy-link triage SQL with a synthetic disposable PostgreSQL schema.

The test only mutates a confirmed *_sandbox database and always drops its
isolated schema. The implementation under test must execute in READ ONLY mode.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from services.legacy_link_triage import (
    LegacyLinkTriageUnavailable, inspect_legacy_link_triage,
)


def test_legacy_link_triage_against_synthetic_postgres():
    dsn = os.getenv("LOANHUB_REGISTRATION_E2E_POSTGRES_URL")
    if not dsn or os.getenv("LOANHUB_REGISTRATION_E2E_ACK") != "isolated_disposable_database":
        pytest.skip("Explicit isolated disposable PostgreSQL database required")
    engine = create_engine(dsn)
    schema = "legacy_triage_" + uuid4().hex[:16]
    try:
        if engine.dialect.name != "postgresql":
            pytest.skip("PostgreSQL only")
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")).scalar_one()
            assert database_name.endswith("_sandbox")
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
            connection.execute(text(f"""
                CREATE TABLE {schema}.people (
                    user_id uuid NOT NULL, national_id text)
            """))
            connection.execute(text(f"""
                CREATE TABLE {schema}.borrowers (
                    id uuid PRIMARY KEY, user_id uuid NOT NULL)
            """))
            connection.execute(text(f"""
                CREATE TABLE {schema}.legacy_loan_captures (
                    id uuid PRIMARY KEY, borrower_id uuid,
                    company_id uuid, national_id text)
            """))
            connection.execute(text(f"""
                CREATE TABLE {schema}.company_borrower_accounts (
                    borrower_id uuid NOT NULL, company_id uuid NOT NULL)
            """))
            company, person1, person2, person3, borrower1, borrower2 = [
                uuid4() for _ in range(6)]
            for user_id, nid in [
                (person1, " SYNTHETIC-A "),
                (person2, "SYNTHETIC-B"),
                (person3, "SYNTHETIC-C"),
            ]:
                connection.execute(
                    text(f"INSERT INTO {schema}.people VALUES (:u, :nid)"),
                    {"u": user_id, "nid": nid})
            for b_id, user_id in [(borrower1, person1), (borrower2, person2)]:
                connection.execute(
                    text(f"INSERT INTO {schema}.borrowers VALUES (:b, :u)"),
                    {"b": b_id, "u": user_id})
                connection.execute(text(
                    f"INSERT INTO {schema}.company_borrower_accounts VALUES (:b, :c)"),
                    {"b": b_id, "c": company})
            for identifier, borrower, nid in [
                (uuid4(), borrower1, "synthetic-a"),
                (uuid4(), None, "SYNTHETIC-A"),
                (uuid4(), None, "synthetic-b"),
                (uuid4(), None, "synthetic-c"),
                (uuid4(), None, "not-in-people"),
            ]:
                connection.execute(
                    text(f"""INSERT INTO {schema}.legacy_loan_captures
                        VALUES (:id, :b, :c, :nid)"""),
                    {"id": identifier, "b": borrower, "c": company, "nid": nid})
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text(f"SET LOCAL search_path TO {schema}"))
                with Session(bind=connection) as db:
                    with db.begin():
                        result = inspect_legacy_link_triage(db)
                assert result.matching_identity_groups == 3
                assert result.linked_only_groups == 0
                assert result.mixed_linkage_groups == 1
                assert result.unlinked_only_groups == 2
                assert result.unlinked_legacy_rows == 3
                assert result.unlinked_with_single_borrower_and_company_account == 2
                assert result.unlinked_needing_manual_review == 3
                assert result.registration_enabled is False
                assert result.automatic_repairs_allowed is False
                assert "SYNTHETIC" not in str(result)
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text(f"SET LOCAL search_path TO {schema}"))
                with Session(bind=connection) as db:
                    with db.begin():
                        with pytest.raises(
                            LegacyLinkTriageUnavailable, match="Read-only"):
                            inspect_legacy_link_triage(db)
    finally:
        try:
            with engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        finally:
            engine.dispose()
