"""Phase 75: real LoanHub registration transaction on a disposable PostgreSQL schema.

Uses clones of production ORM tables (columns/defaults/indexes/checks) with
NO rows copied, in an isolated CI-only database. No public API is activated.
This suite must not be pointed at any production or shared database.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.enums import EmploymentStatus, Gender, UserRole
from database.models.user import User
from database.schemas.company_clients import AssistedCompanyClientCreate
from services.atomic_new_client_registration import (
    AtomicRegistrationUnavailable, create_new_client_atomically,
)

DB_ENV = "LOANHUB_REGISTRATION_E2E_POSTGRES_URL"
ACK_ENV = "LOANHUB_REGISTRATION_E2E_ACK"
TABLES = (
    "users", "people", "borrowers", "company_borrower_accounts",
    "audit_logs", "legacy_loan_captures",
    "new_client_registration_attempts",
    "company_account_opening_fee_configurations",
)
INDEXES = (
    ("people", "national_id", "uq_people_national_id_normalized"),
    ("people", "passport_number", "uq_people_passport_normalized"),
    ("users", "phone", "uq_users_phone_normalized"),
    ("users", "email", "uq_users_email_normalized"),
)


@pytest.fixture
def real_models_sandbox():
    url = os.getenv(DB_ENV)
    if not url or os.getenv(ACK_ENV) != "isolated_disposable_database":
        pytest.skip("Explicit disposable registration E2E DB not configured")
    engine = create_engine(url, pool_size=4, max_overflow=0, pool_pre_ping=True)
    try:
        if engine.dialect.name != "postgresql":
            pytest.skip("PostgreSQL only")
        with engine.connect() as conn:
            name = conn.execute(text("SELECT current_database()")).scalar_one()
        if not name.endswith("_sandbox"):
            pytest.skip("Only a dedicated *_sandbox database is allowed")

        schema = "newclient_e2e_" + uuid4().hex[:16]
        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        try:
            with engine.begin() as conn:
                for table in TABLES:
                    # Clone actual Alembic-migrated SQL columns/defaults/indexes,
                    # never copy production/CI borrower rows or foreign keys.
                    conn.execute(text(
                        f"CREATE TABLE {schema}.{table} "
                        f"(LIKE public.{table} INCLUDING ALL)"
                    ))
                # LIKE copies uniqueness but can rename constraint names.
                # The real reservation uses ON CONFLICT ON CONSTRAINT,
                # so reproduce its canonical production constraint name.
                conn.execute(text(f"""
                    ALTER TABLE {schema}.new_client_registration_attempts
                    ADD CONSTRAINT uq_new_client_registration_company_idempotency
                    UNIQUE (company_id, idempotency_key)
                """))
                for table, column, index_name in INDEXES:
                    conn.execute(text(f"""
                        CREATE UNIQUE INDEX {index_name}
                        ON {schema}.{table} (lower(btrim({column})))
                        WHERE {column} IS NOT NULL AND btrim({column}) <> ''
                    """))
            yield engine, schema
        finally:
            with engine.begin() as conn:
                conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    finally:
        engine.dispose()


def sandbox_session(engine, schema):
    # A new connection is returned for each real service operation so
    # its own db.begin() remains the transaction owner.
    connection = engine.connect()
    connection.execute(text(f"SET SESSION search_path TO {schema}"))
    connection.commit()
    return connection


def staff(company_id, branch_id, employee_id):
    user = User(id=employee_id, role=UserRole.LOAN_OFFICER,
                phone="59998888", password_hash="x" * 60)
    return TenantContext(
        user=user,
        staff=SimpleNamespace(role=UserRole.LOAN_OFFICER),
        company=None, company_id=company_id,
        branch_id=branch_id, is_platform_admin=False,
    )


def applicant(branch_id, *, national_id="SYN-E2E-0001", phone="59000001"):
    return AssistedCompanyClientCreate(
        branch_id=branch_id,
        first_name="Palesa", last_name="Mokoena",
        phone=phone, date_of_birth=date(1993, 5, 11),
        gender=Gender.FEMALE, national_id=national_id,
        district="Maseru", employment_status=EmploymentStatus.EMPLOYED,
        consent_to_share_profile=False, consent_to_credit_checks=False,
    )


def totals(engine, schema):
    with engine.connect() as conn:
        return tuple(conn.execute(text(
            f"SELECT count(*) FROM {schema}.{table}"
        )).scalar_one() for table in (
            "users", "people", "borrowers", "company_borrower_accounts",
            "audit_logs", "new_client_registration_attempts",
        ))


def invoke(engine, schema, context, payload, key):
    with sandbox_session(engine, schema) as conn:
        with Session(bind=conn, expire_on_commit=False) as session:
            return create_new_client_atomically(
                session, context=context, payload=payload,
                idempotency_key=key,
                fingerprint_secret=b"ci-only-registration-hmac-key-64-characters-long",
            )


def test_actual_model_create_replay_and_new_account_scope(real_models_sandbox):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    ctx = staff(company, branch, employee)
    request = applicant(branch)
    first = invoke(engine, schema, ctx, request, "synthetic-registration-key-000001")
    assert first.existing is False
    assert totals(engine, schema) == (1, 1, 1, 1, 1, 1)
    repeat = invoke(engine, schema, ctx, request, "synthetic-registration-key-000001")
    assert repeat.existing is True
    assert repeat.client_account_id == first.client_account_id
    assert totals(engine, schema) == (1, 1, 1, 1, 1, 1)
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT company_id, branch_id, opened_by_user_id, opening_fee_amount,
                   opening_fee_status, source
            FROM {schema}.company_borrower_accounts
        """)).one()
        assert row[:3] == (company, branch, employee)
        assert Decimal(row.opening_fee_amount) == Decimal("0.00")
        assert row.opening_fee_status == "not_required"
        assert row.source == "new_only_registration"


def test_existing_normalized_identity_refused_without_mutation(real_models_sandbox):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    ctx = staff(company, branch, employee)
    first = invoke(engine, schema, ctx, applicant(branch),
                   "synthetic-registration-key-000002")
    before = totals(engine, schema)
    with pytest.raises(AtomicRegistrationUnavailable):
        invoke(engine, schema, ctx, applicant(
            branch, national_id=" syn-e2e-0001 ", phone="59000002"
        ), "synthetic-registration-key-000003")
    assert totals(engine, schema) == before
    assert before == (1, 1, 1, 1, 1, 1)


def test_legacy_capture_rejected_without_modifying_history(real_models_sandbox):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {schema}.legacy_loan_captures
                (id, company_id, folio_number, national_id, status,
                 borrowed_amount, total_repayable, amount_paid,
                 banking_info, paper_snapshot, conversion_data)
            VALUES (:id, :company, 'SYNTH-FOLIO-1', 'syn-e2e-0001',
                    'posted', 500, 650, 300, '{{}}'::jsonb, '{{}}'::jsonb,
                    '{{}}'::jsonb)
        """), {"id": uuid4(), "company": uuid4()})
    with pytest.raises(AtomicRegistrationUnavailable):
        invoke(engine, schema, staff(company, branch, employee),
               applicant(branch), "synthetic-registration-key-000004")
    assert totals(engine, schema) == (0, 0, 0, 0, 0, 0)
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT status, borrowed_amount, total_repayable, amount_paid
            FROM {schema}.legacy_loan_captures
        """)).one()
        assert row == ("posted", Decimal("500"), Decimal("650"), Decimal("300"))


def test_failed_finalization_rolls_back_all_real_rows(
    real_models_sandbox, monkeypatch,
):
    engine, schema = real_models_sandbox
    import services.atomic_new_client_registration as atomic

    def abort_after_staging(*args, **kwargs):
        raise RuntimeError("synthetic failure at idempotency completion")

    monkeypatch.setattr(atomic, "finalize_new_client_registration",
                        abort_after_staging)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        company, branch, employee = uuid4(), uuid4(), uuid4()
        invoke(engine, schema, staff(company, branch, employee),
               applicant(branch), "synthetic-registration-key-000005")
    assert totals(engine, schema) == (0, 0, 0, 0, 0, 0)


def test_concurrent_same_identity_no_second_account(real_models_sandbox):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    ctx = staff(company, branch, employee)
    request = applicant(branch, national_id="SYN-CONCURRENT-001",
                        phone="59000005")
    gate = Barrier(2)

    def register(_i):
        gate.wait(timeout=15)
        return invoke(engine, schema, ctx, request,
                      "synthetic-concurrent-registration-key")

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(register, 1)
        b = pool.submit(register, 2)
        results = [a.result(timeout=35), b.result(timeout=35)]
    assert {r.client_account_id for r in results} == {
        results[0].client_account_id
    }
    assert sorted(r.existing for r in results) == [False, True]
    assert totals(engine, schema) == (1, 1, 1, 1, 1, 1)


def test_configured_company_opening_fee_is_preserved(real_models_sandbox):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {schema}.company_account_opening_fee_configurations
                (id, company_id, name, fee_type, flat_amount, percentage,
                 currency, required_before_activation, allowed_providers, is_active)
            VALUES (:id, :company, 'Synthetic account fee', 'flat', 35.00, 0,
                    'LSL', true, '[]'::jsonb, true)
        """), {"id": uuid4(), "company": company})
    result = invoke(
        engine, schema, staff(company, branch, employee),
        applicant(branch), "synthetic-registration-fee-000001")
    assert result.existing is False
    with engine.connect() as conn:
        fee = conn.execute(text(f"""
            SELECT opening_fee_amount, opening_fee_currency,
                   opening_fee_status, status
            FROM {schema}.company_borrower_accounts
        """)).one()
    assert fee[0] == Decimal("35.00")
    assert fee[1] == "LSL"
    assert fee[2] == "accrued"
    assert fee[3] == "active"
