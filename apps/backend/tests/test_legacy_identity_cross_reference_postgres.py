"""Isolated PostgreSQL proof of privacy-safe legacy identity overlap counts."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from services.legacy_identity_cross_reference import (
    LegacyIdentityAuditUnavailable, inspect_legacy_identity_cross_reference,
)


def test_cross_source_identity_overlaps_in_disposable_postgres():
    dsn = os.getenv("LOANHUB_REGISTRATION_E2E_POSTGRES_URL")
    ack = os.getenv("LOANHUB_REGISTRATION_E2E_ACK")
    if not dsn or ack != "isolated_disposable_database":
        pytest.skip("Explicit synthetic PostgreSQL sandbox required")
    engine = create_engine(dsn)
    schema = "legacy_overlap_" + uuid4().hex[:16]
    try:
        if engine.dialect.name != "postgresql":
            pytest.skip("PostgreSQL only")
        with engine.connect() as connection:
            assert connection.execute(text(
                "SELECT current_database()"
            )).scalar_one().endswith("_sandbox")
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
            connection.execute(text(f"""
                CREATE TABLE {schema}.people (
                    national_id text, passport_number text)
            """))
            connection.execute(text(f"""
                CREATE TABLE {schema}.legacy_loan_captures (
                    national_id text, passport_number text)
            """))
            connection.execute(text(f"""
                INSERT INTO {schema}.people VALUES
                (' ABC-100 ', ' PASS-201 '), ('XYZ-102', NULL)
            """))
            connection.execute(text(f"""
                INSERT INTO {schema}.legacy_loan_captures VALUES
                ('abc-100', 'pass-201'), ('ABC-100', ' PASS-201 '),
                ('UNRELATED', 'PASS-300')
            """))
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text(f"SET LOCAL search_path TO {schema}"))
                with Session(bind=connection) as db:
                    with db.begin():
                        result = inspect_legacy_identity_cross_reference(db)
                assert result.national_id_overlap_groups == 1
                assert result.passport_overlap_groups == 1
                assert result.repeated_legacy_passport_groups == 1
                assert result.requires_historical_review is True
                assert "ABC-100" not in str(result)
                assert "PASS-201" not in str(result)
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text(f"SET LOCAL search_path TO {schema}"))
                with Session(bind=connection) as db:
                    with db.begin():
                        with pytest.raises(
                            LegacyIdentityAuditUnavailable, match="Read-only"
                        ):
                            inspect_legacy_identity_cross_reference(db)
    finally:
        try:
            if "schema" in locals():
                with engine.begin() as connection:
                    connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        finally:
            engine.dispose()
