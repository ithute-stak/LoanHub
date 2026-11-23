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
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from services.atomic_new_client_registration import (
    AtomicRegistrationUnavailable, create_new_client_atomically,
    create_full_new_client_atomically,
)

DB_ENV = "LOANHUB_REGISTRATION_E2E_POSTGRES_URL"
ACK_ENV = "LOANHUB_REGISTRATION_E2E_ACK"
TABLES = (
    "users", "company_staff", "people", "borrowers", "company_borrower_accounts",
    "audit_logs", "legacy_loan_captures",
    "new_client_registration_attempts",
    "borrower_debt_obligations", "borrower_debt_obligation_events",
    "borrower_bank_accounts",
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
                # Branch table is intentionally structural only. Insert
                # synthetic active branches before invoking the actual
                # company/branch authorization lookup.
                conn.execute(text(f"""
                    CREATE TABLE {schema}.company_branches (
                        id uuid PRIMARY KEY,
                        company_id uuid NOT NULL,
                        is_active boolean NOT NULL
                    )
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
    user.is_active = True
    return TenantContext(
        user=user,
        staff=SimpleNamespace(
            user_id=employee_id, company_id=company_id,
            branch_id=branch_id, role=UserRole.LOAN_OFFICER,
            is_active=True,
        ),
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
            f"SELECT count(*) FROM {schema}.{table}" +
            (" WHERE role = 'BORROWER'" if table == "users" else "")
        )).scalar_one() for table in (
            "users", "people", "borrowers", "company_borrower_accounts",
            "audit_logs", "new_client_registration_attempts",
        ))


def invoke(engine, schema, context, payload, key):
    # The caller's selected branch must exist as an active row in this
    # synthetic schema before the registered user can create an account.
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {schema}.company_branches (id, company_id, is_active)
            VALUES (:branch, :company, TRUE)
            ON CONFLICT (id) DO NOTHING
        """), {"branch": context.branch_id, "company": context.company_id})
        conn.execute(text(f"""
            INSERT INTO {schema}.users (
                id, phone, password_hash, role, is_active, is_verified,
                must_change_password
            ) VALUES (
                :actor, :phone, 'synthetic-staff-hash-not-credential',
                'LOAN_OFFICER', TRUE, TRUE, FALSE
            ) ON CONFLICT (id) DO NOTHING
        """), {"actor": context.user.id,
                "phone": "6" + str(context.user.id.int % 10000000).zfill(7)})
        conn.execute(text(f"""
            INSERT INTO {schema}.company_staff (
                id, user_id, company_id, branch_id, role, is_primary, is_active
            ) VALUES (
                :id, :actor, :company, :branch,
                'LOAN_OFFICER', TRUE, TRUE
            ) ON CONFLICT DO NOTHING
        """), {
            "id": context.user.id, "actor": context.user.id,
            "company": context.company_id, "branch": context.branch_id,
        })
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


def test_cross_company_legacy_passport_blocks_new_only_registration(
    real_models_sandbox,
):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {schema}.legacy_loan_captures
                (id, company_id, folio_number, passport_number, status,
                 borrowed_amount, total_repayable, amount_paid,
                 banking_info, paper_snapshot, conversion_data)
            VALUES (:id, :other_company, 'SYNTH-PASSPORT-FOLIO',
                    ' pass-syn-001 ', 'posted', 750, 950, 450,
                    '{{}}'::jsonb, '{{}}'::jsonb, '{{}}'::jsonb)
        """), {"id": uuid4(), "other_company": uuid4()})
    request = applicant(
        branch, national_id=None, phone="59000009")
    request.passport_number = "PASS-SYN-001"
    with pytest.raises(AtomicRegistrationUnavailable):
        invoke(
            engine, schema, staff(company, branch, employee),
            request, "synthetic-passport-collision-000001")
    assert totals(engine, schema) == (0, 0, 0, 0, 0, 0)
    with engine.connect() as conn:
        old = conn.execute(text(f"""
            SELECT status, borrowed_amount, total_repayable, amount_paid
            FROM {schema}.legacy_loan_captures
        """)).one()
    assert old == ("posted", Decimal("750"), Decimal("950"), Decimal("450"))


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


def test_revoked_database_membership_denies_new_registration(real_models_sandbox):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    ctx = staff(company, branch, employee)
    invoke(engine, schema, ctx, applicant(branch),
           "synthetic-initial-registration-00001")
    before = totals(engine, schema)
    with engine.begin() as conn:
        conn.execute(text(f"""
            UPDATE {schema}.company_staff SET is_active = FALSE
            WHERE user_id = :actor
        """), {"actor": employee})
    with pytest.raises(AtomicRegistrationUnavailable, match="membership"):
        invoke(engine, schema, ctx, applicant(
            branch, national_id="SYN-E2E-SECOND", phone="59000031"
        ), "synthetic-revoked-registration-00001")
    assert totals(engine, schema) == before


def full_capture(branch_id, *, national_id="SYN-FULL-REG-001", phone="59000070"):
    return FullNewOnlyClientCapture.model_validate({
        "branch_id": branch_id,
        "first_name": "Palesa",
        "middle_name": "K",
        "last_name": "Mokoena",
        "phone": phone,
        "gender": Gender.FEMALE,
        "date_of_birth": date(1993, 5, 11),
        "national_id": national_id,
        "district": "Maseru",
        "town_or_village": "Roma",
        "physical_address": "Synthetic residence",
        "employment_status": EmploymentStatus.EMPLOYED,
        "employment_type": "permanent",
        "employer_name": "Synthetic Employer",
        "job_title": "Clerk",
        "monthly_income": "6000.00",
        "income_day": 25,
        "salary_date": "25",
        "has_existing_loans": True,
        "existing_loan_total": "550.00",
        "external_debts": [{
            "creditor": "Synthetic historical external creditor",
            "original_amount": "700.00",
            "current_balance": "550.00",
            "installment_amount": "55.00",
            "total_installments": 12,
            "installments_paid": 2,
            "remaining_installments": 10,
            "status": "active",
        }],
        "consent_to_share_profile": False,
        "consent_to_credit_checks": True,
    })


def invoke_full(engine, schema, context, payload, key):
    # Seed synthetic staff and company branch through the same fixture
    # helper used by actual minimal registration, without creating clients.
    from database.models.user import User
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {schema}.company_branches (id, company_id, is_active)
            VALUES (:branch, :company, TRUE)
            ON CONFLICT (id) DO NOTHING
        """), {"branch": context.branch_id, "company": context.company_id})
        conn.execute(text(f"""
            INSERT INTO {schema}.users (id, phone, password_hash, role,
                                        is_active, is_verified, must_change_password)
            VALUES (:actor, :phone, 'synthetic-staff-hash-not-credential',
                    'LOAN_OFFICER', TRUE, TRUE, FALSE)
            ON CONFLICT (id) DO NOTHING
        """), {"actor": context.user.id,
                "phone": "6" + str(context.user.id.int % 10000000).zfill(7)})
        conn.execute(text(f"""
            INSERT INTO {schema}.company_staff (
                id, user_id, company_id, branch_id, role, is_primary, is_active)
            VALUES (:id, :actor, :company, :branch, 'LOAN_OFFICER', TRUE, TRUE)
            ON CONFLICT DO NOTHING
        """), {"id": context.user.id, "actor": context.user.id,
                "company": context.company_id, "branch": context.branch_id})
    with sandbox_session(engine, schema) as conn:
        with Session(bind=conn, expire_on_commit=False) as session:
            return create_full_new_client_atomically(
                session, context=context, payload=payload,
                idempotency_key=key,
                fingerprint_secret=b"ci-only-registration-hmac-key-64-characters-long",
            )


def test_full_registration_stages_employment_and_external_debt_atomically(
    real_models_sandbox,
):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    ctx = staff(company, branch, employee)
    request = full_capture(branch)
    result = invoke_full(
        engine, schema, ctx, request, "synthetic-full-registration-00001")
    assert result.existing is False
    with engine.connect() as conn:
        profile = conn.execute(text(f"""
            SELECT p.middle_name, p.town_or_village, p.physical_address,
                   b.employer_name, b.monthly_income,
                   b.has_existing_loans, b.existing_loan_total
            FROM {schema}.people p
            JOIN {schema}.borrowers b ON b.user_id = p.user_id
        """)).one()
        assert profile[0:4] == (
            "K", "Roma", "Synthetic residence", "Synthetic Employer")
        assert profile[4] == Decimal("6000.00")
        assert profile[5] is True
        assert profile[6] == Decimal("550.00")
        debt = conn.execute(text(f"""
            SELECT creditor, current_balance, installment_amount,
                   is_verified, status
            FROM {schema}.borrower_debt_obligations
        """)).one()
        assert debt == (
            "Synthetic historical external creditor", Decimal("550.00"),
            Decimal("55.00"), False, "active")
        assert conn.execute(text(f"""
            SELECT count(*) FROM {schema}.borrower_debt_obligation_events
        """)).scalar_one() == 1
    replay = invoke_full(
        engine, schema, ctx, request, "synthetic-full-registration-00001")
    assert replay.existing is True
    assert replay.client_account_id == result.client_account_id


def test_failed_full_staging_rolls_back_all_new_client_and_debt_rows(
    real_models_sandbox, monkeypatch,
):
    engine, schema = real_models_sandbox
    import services.atomic_new_client_registration as atomic

    def reject_details(*args, **kwargs):
        raise RuntimeError("synthetic post-borrower full-detail failure")

    monkeypatch.setattr(atomic, "stage_full_new_only_client_details",
                        reject_details)
    company, branch, employee = uuid4(), uuid4(), uuid4()
    with pytest.raises(RuntimeError, match="post-borrower"):
        invoke_full(
            engine, schema, staff(company, branch, employee),
            full_capture(branch), "synthetic-full-registration-rollback")
    assert totals(engine, schema) == (0, 0, 0, 0, 0, 0)
    with engine.connect() as conn:
        for table_name in (
            "borrower_debt_obligations", "borrower_debt_obligation_events",
            "borrower_bank_accounts",
        ):
            assert conn.execute(text(
                f"SELECT count(*) FROM {schema}.{table_name}"
            )).scalar_one() == 0



@pytest.mark.parametrize("failure_point", [
    "bank_capture", "debt_after_insert", "finalize_after_details",
])
def test_actual_full_registration_failure_rolls_back_all_new_rows(
    real_models_sandbox, monkeypatch, failure_point,
):
    """Inject faults at distinct points inside the SAME real PG transaction."""
    engine, schema = real_models_sandbox
    import services.full_new_only_client_staging as details
    import services.atomic_new_client_registration as atomic

    if failure_point == "bank_capture":
        def fail_bank(*args, **kwargs):
            raise RuntimeError("injected bank capture failure")
        monkeypatch.setattr(details, "_save_assisted_banking_profile", fail_bank)
    elif failure_point == "debt_after_insert":
        original = details.save_assisted_external_debts

        def fail_after_debt(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("injected after debt insert")
        monkeypatch.setattr(details, "save_assisted_external_debts", fail_after_debt)
    else:
        def fail_finalize(*args, **kwargs):
            raise RuntimeError("injected finalization failure")
        monkeypatch.setattr(atomic, "finalize_new_client_registration",
                            fail_finalize)

    company, branch, employee = uuid4(), uuid4(), uuid4()
    ctx = staff(company, branch, employee)
    request = full_capture(branch)
    with pytest.raises(RuntimeError, match="injected"):
        invoke_full(engine, schema, ctx, request,
                    "synthetic-full-rollback-" + failure_point)

    assert totals(engine, schema) == (0, 0, 0, 0, 0, 0)
    with engine.connect() as conn:
        for table_name in (
            "borrower_debt_obligations", "borrower_debt_obligation_events",
            "borrower_bank_accounts",
        ):
            assert conn.execute(text(
                f"SELECT count(*) FROM {schema}.{table_name}"
            )).scalar_one() == 0

    # The failed idempotency reservation must not poison a subsequent
    # valid registration with the SAME logical request key.
    monkeypatch.undo()
    success = invoke_full(engine, schema, ctx, request,
                          "synthetic-full-rollback-" + failure_point)
    assert success.existing is False
    assert totals(engine, schema) == (1, 1, 1, 1, 1, 1)
    with engine.connect() as conn:
        assert conn.execute(text(f"""
            SELECT count(*) FROM {schema}.borrower_debt_obligations
        """)).scalar_one() == 1
        assert conn.execute(text(f"""
            SELECT count(*) FROM {schema}.borrower_debt_obligation_events
        """)).scalar_one() == 1


def full_capture_with_bank(branch_id):
    """Synthetic account whose prefix and length satisfy FNB validation."""
    request = full_capture(branch_id)
    payload = request.model_dump(mode="python")
    payload["bank_account"] = {
        "account_holder": "Palesa Mokoena",
        "bank_name": "FNB",
        "account_number": "61234567890",
        "salary_account": True,
        "tokenized_card_provider": "synthetic-ci",
        "tokenized_card_reference": "CI-ONLY-TOKEN-REF",
        "verification_status": "unverified",
    }
    return FullNewOnlyClientCapture.model_validate(payload)


def test_bank_account_number_and_provider_token_are_encrypted_in_real_postgres(
    real_models_sandbox,
):
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    ctx = staff(company, branch, employee)
    request = full_capture_with_bank(branch)
    result = invoke_full(
        engine, schema, ctx, request, "synthetic-full-bank-registration-0001")
    assert result.existing is False
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT bank_name, account_number_encrypted, account_number_last4,
                   tokenized_card_reference_encrypted, salary_account,
                   verification_status, verification_reference
            FROM {schema}.borrower_bank_accounts
        """)).one()
    assert row.bank_name == "FNB"
    assert row.account_number_last4 == "7890"
    assert row.account_number_encrypted
    assert "61234567890" not in row.account_number_encrypted
    assert row.tokenized_card_reference_encrypted
    assert "CI-ONLY-TOKEN-REF" not in row.tokenized_card_reference_encrypted
    assert row.salary_account is True
    assert row.verification_status == "unverified"
    assert row.verification_reference is None
    replay = invoke_full(
        engine, schema, ctx, request, "synthetic-full-bank-registration-0001")
    assert replay.existing is True
    with engine.connect() as conn:
        assert conn.execute(text(f"""
            SELECT count(*) FROM {schema}.borrower_bank_accounts
        """)).scalar_one() == 1


def test_debt_failure_after_encrypted_bank_insert_rolls_back_bank_and_identity(
    real_models_sandbox, monkeypatch,
):
    engine, schema = real_models_sandbox
    import services.full_new_only_client_staging as details
    original = details.save_assisted_external_debts

    def fail_after_debt(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic failure after bank and debt insert")

    monkeypatch.setattr(details, "save_assisted_external_debts",
                        fail_after_debt)
    company, branch, employee = uuid4(), uuid4(), uuid4()
    ctx = staff(company, branch, employee)
    request = full_capture_with_bank(branch)
    with pytest.raises(RuntimeError, match="after bank and debt"):
        invoke_full(
            engine, schema, ctx, request,
            "synthetic-full-bank-and-debt-rollback-0001")
    assert totals(engine, schema) == (0, 0, 0, 0, 0, 0)
    with engine.connect() as conn:
        for table_name in (
            "borrower_bank_accounts", "borrower_debt_obligations",
            "borrower_debt_obligation_events",
        ):
            assert conn.execute(text(f"""
                SELECT count(*) FROM {schema}.{table_name}
            """)).scalar_one() == 0
    monkeypatch.undo()
    result = invoke_full(
        engine, schema, ctx, request,
        "synthetic-full-bank-and-debt-rollback-0001")
    assert result.existing is False
    with engine.connect() as conn:
        assert conn.execute(text(f"""
            SELECT count(*) FROM {schema}.borrower_bank_accounts
        """)).scalar_one() == 1
        assert conn.execute(text(f"""
            SELECT count(*) FROM {schema}.borrower_debt_obligations
        """)).scalar_one() == 1


def test_batlokoa_adapter_persists_full_new_client_and_replays_in_sandbox(
    real_models_sandbox,
):
    """Real, disposable PostgreSQL test: client survives a new connection."""
    from contextlib import contextmanager
    from services.batlokoa_new_only_registration_command import (
        BatlokoaRegistrationNotReleased, submit_new_only_client,
    )
    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    context = staff(company, branch, employee)
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {schema}.company_branches (id, company_id, is_active)
            VALUES (:branch, :company, TRUE)
        """), {"branch": branch, "company": company})
        conn.execute(text(f"""
            INSERT INTO {schema}.users (
                id, phone, password_hash, role, is_active, is_verified,
                must_change_password
            ) VALUES (
                :actor, '69998888', 'synthetic-staff-hash-not-credential',
                'LOAN_OFFICER', TRUE, TRUE, FALSE
            )
        """), {"actor": employee})
        conn.execute(text(f"""
            INSERT INTO {schema}.company_staff (
                id, user_id, company_id, branch_id, role, is_primary, is_active
            ) VALUES (
                :actor, :actor, :company, :branch,
                'LOAN_OFFICER', TRUE, TRUE
            )
        """), {"actor": employee, "company": company, "branch": branch})

    # Exercise the complete Batlokoa capture, including employment details
    # and an external debt, not just the minimal borrower identity fields.
    request = full_capture(
        branch, national_id="SYN-BATLOKOA-001", phone="59008881")
    @contextmanager
    def fresh_session():
        with sandbox_session(engine, schema) as connection:
            with Session(bind=connection, expire_on_commit=False) as db:
                yield db

    kwargs = dict(
        context=context, payload=request,
        idempotency_key="batlokoa-full-registration-001",
        fingerprint_secret=b"ci-only-registration-hmac-key-64-characters-long",
        session_factory=fresh_session,
    )
    with pytest.raises(BatlokoaRegistrationNotReleased):
        submit_new_only_client(**kwargs)
    assert totals(engine, schema) == (0, 0, 0, 0, 0, 0)

    created = submit_new_only_client(
        **kwargs, independently_approved_release=True,
    )
    assert created.replayed is False
    assert totals(engine, schema) == (1, 1, 1, 1, 1, 1)

    replay = submit_new_only_client(
        **kwargs, independently_approved_release=True,
    )
    assert replay.client_account_id == created.client_account_id
    assert replay.replayed is True
    assert totals(engine, schema) == (1, 1, 1, 1, 1, 1)
    with engine.connect() as conn:
        persisted = conn.execute(text(f"""
            SELECT company_id, branch_id, opened_by_user_id
            FROM {schema}.company_borrower_accounts
            WHERE id = :account
        """), {"account": created.client_account_id}).one()
        assert persisted == (company, branch, employee)
        # Fresh database connection proves committed details survive the
        # original request/session and the idempotent replay.
        person = conn.execute(text(f"""
            SELECT p.first_name, p.middle_name, p.last_name, p.national_id,
                   b.employer_name, b.monthly_income
            FROM {schema}.company_borrower_accounts a
            JOIN {schema}.borrowers b ON b.id = a.borrower_id
            JOIN {schema}.people p ON p.user_id = b.user_id
            WHERE a.id = :account
        """), {"account": created.client_account_id}).one()
        assert person == (
            "Palesa", "K", "Mokoena", "SYN-BATLOKOA-001",
            "Synthetic Employer", Decimal("6000.00"),
        )
        debt = conn.execute(text(f"""
            SELECT d.creditor, d.current_balance, d.installment_amount
            FROM {schema}.company_borrower_accounts a
            JOIN {schema}.borrower_debt_obligations d
              ON d.borrower_id = a.borrower_id
            WHERE a.id = :account
        """), {"account": created.client_account_id}).one()
        assert debt == (
            "Synthetic historical external creditor",
            Decimal("550.00"), Decimal("55.00"),
        )


def test_isolated_http_save_then_readback_and_retry_uses_actual_postgres(
    real_models_sandbox,
):
    """Synthetic HTTP boundary -> real LoanHub writer -> committed SQL readback.

    This app exists ONLY inside a disposable PostgreSQL CI test. It is not
    LoanHub's public API router and cannot activate production registration.
    """
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient

    engine, schema = real_models_sandbox
    company, branch, employee = uuid4(), uuid4(), uuid4()
    context = staff(company, branch, employee)
    captured = full_capture(
        branch, national_id="SYN-HTTP-PERSIST-001", phone="59008771")
    app = FastAPI()

    def authenticate(authorization, tenant):
        if (authorization != "Bearer synthetic-ci-staff"
                or tenant != str(company)):
            raise HTTPException(401, "Unauthorized")

    @app.post("/isolated-test-only/registration/clients", status_code=201)
    def save(
        payload: FullNewOnlyClientCapture,
        authorization: str = Header(default=""),
        x_company_id: str = Header(default=""),
        idempotency_key: str = Header(default=""),
    ):
        authenticate(authorization, x_company_id)
        # Same synthetic staff and branch provisioning used by existing
        # disposable PostgreSQL tests; no production customer exists here.
        result = invoke_full(engine, schema, context, payload, idempotency_key)
        return {
            "client_account_id": str(result.client_account_id),
            "replayed": result.existing,
        }

    @app.get("/isolated-test-only/company-clients/{account_id}")
    def readback(
        account_id: str,
        authorization: str = Header(default=""),
        x_company_id: str = Header(default=""),
    ):
        authenticate(authorization, x_company_id)
        with engine.connect() as connection:
            row = connection.execute(text(f"""
                SELECT a.id, a.company_id, a.branch_id, a.opened_by_user_id,
                       a.source, p.first_name, p.last_name
                FROM {schema}.company_borrower_accounts a
                JOIN {schema}.borrowers b ON b.id = a.borrower_id
                JOIN {schema}.people p ON p.user_id = b.user_id
                WHERE a.id = :account AND a.company_id = :company
            """), {"account": account_id, "company": company}).one_or_none()
        if row is None:
            raise HTTPException(404, "Client not found")
        return {
            "id": str(row[0]), "company_id": str(row[1]),
            "branch_id": str(row[2]),
            "opened_by_user_id": str(row[3]),
            "source": row[4], "first_name": row[5], "last_name": row[6],
        }

    headers = {
        "Authorization": "Bearer synthetic-ci-staff",
        "X-Company-ID": str(company),
        "Idempotency-Key": "synthetic-http-save-unique-001",
    }
    with TestClient(app) as http:
        invalid = http.post(
            "/isolated-test-only/registration/clients",
            json=captured.model_dump(mode="json"),
            headers={**headers, "X-Company-ID": str(uuid4())},
        )
        assert invalid.status_code == 401
        assert totals(engine, schema) == (0, 0, 0, 0, 0, 0)

        first = http.post(
            "/isolated-test-only/registration/clients",
            json=captured.model_dump(mode="json"), headers=headers)
        assert first.status_code == 201
        created = first.json()
        assert created["replayed"] is False
        assert totals(engine, schema) == (1, 1, 1, 1, 1, 1)
        retrieved = http.get(
            "/isolated-test-only/company-clients/"
            + created["client_account_id"], headers=headers)
        assert retrieved.status_code == 200
        assert retrieved.json() == {
            "id": created["client_account_id"],
            "company_id": str(company),
            "branch_id": str(branch),
            "opened_by_user_id": str(employee),
            "source": "new_only_registration",
            "first_name": "Palesa",
            "last_name": "Mokoena",
        }
        replay = http.post(
            "/isolated-test-only/registration/clients",
            json=captured.model_dump(mode="json"), headers=headers)
        assert replay.status_code == 201
        assert replay.json() == {
            "client_account_id": created["client_account_id"],
            "replayed": True,
        }
        assert totals(engine, schema) == (1, 1, 1, 1, 1, 1)
