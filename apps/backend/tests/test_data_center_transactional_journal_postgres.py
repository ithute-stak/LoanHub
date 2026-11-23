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
                original_generation = con.execute(text("""
                    SELECT generation FROM loanhub_dc_capture WHERE company_id = :company
                """), {"company": company}).scalar_one()
                con.execute(text("""
                    UPDATE loanhub_dc_capture SET enabled = false WHERE company_id = :company
                """), {"company": company})
                con.execute(text("""
                    UPDATE loanhub_dc_capture SET enabled = true WHERE company_id = :company
                """), {"company": company})
                rotated_generation = con.execute(text("""
                    SELECT generation FROM loanhub_dc_capture WHERE company_id = :company
                """), {"company": company}).scalar_one()
                assert rotated_generation != original_generation

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

            # Exercise the real source-table triggers, not just their helper.
            from sqlalchemy.orm import Session
            from database.models.company import LoanCompany
            from database.models.branch import CompanyBranch
            from database.models.enums import CompanyStatus
            branch_id = uuid4()
            disabled_branch_id = uuid4()
            with Session(engine) as db:
                db.add_all([
                    LoanCompany(id=company, name="DC Test " + uuid4().hex,
                                phone="000000000", status=CompanyStatus.APPROVED,
                                is_active=True),
                    LoanCompany(id=another_company, name="DC Disabled " + uuid4().hex,
                                phone="000000001", status=CompanyStatus.APPROVED,
                                is_active=True),
                ])
                db.flush()
                db.add_all([
                    CompanyBranch(id=branch_id, company_id=company,
                                  name="Pilot", district="Maseru"),
                    CompanyBranch(id=disabled_branch_id, company_id=another_company,
                                  name="Not Captured", district="Maseru"),
                ])
                db.commit()
            with engine.connect() as con:
                assert con.execute(text("""
                    SELECT cursor, resource, entity_id, branch_id, action
                    FROM loanhub_dc_event
                    WHERE company_id = :company ORDER BY cursor DESC LIMIT 1
                """), {"company": company}).one() == (
                    4, "branches", branch_id, branch_id, "created"
                )
                assert con.execute(text("""
                    SELECT count(*) FROM loanhub_dc_event
                    WHERE company_id = :company
                """), {"company": another_company}).scalar_one() == 0
            with Session(engine) as db:
                branch = db.get(CompanyBranch, branch_id)
                branch.is_active = False
                db.commit()
            with engine.connect() as con:
                assert con.execute(text("""
                    SELECT cursor, action FROM loanhub_dc_event
                    WHERE company_id = :company ORDER BY cursor DESC LIMIT 1
                """), {"company": company}).one() == (5, "updated")
            with Session(engine) as db:
                branch = db.get(CompanyBranch, branch_id)
                branch.name = "Rolled back"
                db.flush()
                db.rollback()
            with engine.connect() as con:
                assert con.execute(text("""
                    SELECT cursor FROM loanhub_dc_clock
                    WHERE company_id = :company
                """), {"company": company}).scalar_one() == 5

            # Full integration: commit a staff membership, build the actual
            # six-resource repeatable-read snapshot, then replay a later
            # committed branch change from that exact cursor.
            from core.access_control import TenantContext
            from database.models.user import User
            from database.models.company_staff import CompanyStaff
            from database.models.enums import UserRole
            from services.data_center_snapshot import preview_snapshot
            from services.data_center_replay import replay_metadata
            from database.tenant_context import bind_database_tenant_context

            with Session(engine, expire_on_commit=False) as db:
                member_user = User(
                    phone="590" + uuid4().hex[:9],
                    password_hash="not-a-login",
                    role=UserRole.COMPANY_OWNER,
                    is_active=True,
                )
                db.add(member_user)
                db.flush()
                member = CompanyStaff(
                    user_id=member_user.id,
                    company_id=company,
                    role=UserRole.COMPANY_OWNER,
                    is_active=True,
                )
                db.add(member)
                db.commit()
                owner_company = db.get(LoanCompany, company)
                context = TenantContext(
                    user=member_user,
                    staff=member,
                    company=owner_company,
                    company_id=company,
                    branch_id=None,
                    is_platform_admin=False,
                )
                preview = preview_snapshot(context, db)
                assert preview["ready"] is True
                assert preview["complete_data_center_snapshot"] is True
                assert preview["replay_supported"] is True
                assert set(preview["buckets"]) == {
                    "branches", "loanProducts", "staff", "clients", "loans", "payments",
                }
                assert str(branch_id) in preview["buckets"]["branches"]["byId"]
                assert str(member.id) in preview["buckets"]["staff"]["byId"]
                baseline_cursor = preview["cursor"]
                generation = preview["generation"]

                # A subsequent committed change must appear as the next
                # journal cursor, with no row payload or loan amount.
                tracked_branch = db.get(CompanyBranch, branch_id)
                tracked_branch.name = "Updated after snapshot"
                db.commit()
                bind_database_tenant_context(
                    db,
                    user_id=member_user.id,
                    company_id=company,
                    role=UserRole.COMPANY_OWNER.value,
                    actor_scope="tenant",
                )
                from uuid import UUID
                replay = replay_metadata(
                    db, context,
                    after_cursor=baseline_cursor,
                    generation=UUID(generation),
                )
                assert replay["next_cursor"] == baseline_cursor + 1
                assert replay["has_more"] is False
                assert replay["events"] == [{
                    "cursor": baseline_cursor + 1,
                    "resource": "branches",
                    "entity_id": str(branch_id),
                    "branch_id": str(branch_id),
                    "action": "updated",
                }]
                assert replay["payloads_included"] is False

                # Actual branch manager membership must be denied both
                # full-company snapshot and metadata replay, even while
                # capture is enabled for the owner's company.
                manager_user = User(
                    phone="590" + uuid4().hex[:9],
                    password_hash="not-a-login",
                    role=UserRole.BRANCH_MANAGER,
                    is_active=True,
                )
                db.add(manager_user)
                db.flush()
                branch_manager = CompanyStaff(
                    user_id=manager_user.id,
                    company_id=company,
                    branch_id=branch_id,
                    role=UserRole.BRANCH_MANAGER,
                    is_active=True,
                )
                db.add(branch_manager)
                db.commit()
                branch_context = TenantContext(
                    user=manager_user,
                    staff=branch_manager,
                    company=owner_company,
                    company_id=company,
                    branch_id=branch_id,
                    is_platform_admin=False,
                )
                with pytest.raises(PermissionError, match="management"):
                    preview_snapshot(branch_context, db)
                bind_database_tenant_context(
                    db, user_id=manager_user.id, company_id=company,
                    branch_id=branch_id, role=UserRole.BRANCH_MANAGER.value,
                    actor_scope="tenant",
                )
                with pytest.raises(PermissionError, match="management"):
                    replay_metadata(
                        db, branch_context, after_cursor=baseline_cursor,
                        generation=UUID(generation),
                    )

                # Exercise the actual HTTP routes, dependency authorization
                # and response headers against this throwaway PostgreSQL DB.
                # No real credentials, customer records or production traffic.
                from fastapi import FastAPI
                from fastapi.testclient import TestClient
                from core.access_control import get_tenant_context
                from database.session import get_db
                from routers.data_center_snapshot import router as snapshot_router
                from routers.data_center_replay import router as replay_router

                test_app = FastAPI()
                test_app.include_router(snapshot_router)
                test_app.include_router(replay_router)
                current_context = [context]

                def resolve_test_context():
                    return current_context[0]

                def disposable_test_session():
                    with Session(engine) as test_db:
                        actor = current_context[0]
                        bind_database_tenant_context(
                            test_db, user_id=actor.user.id,
                            company_id=actor.company_id,
                            branch_id=actor.branch_id,
                            role=actor.role.value, actor_scope="tenant",
                        )
                        yield test_db

                test_app.dependency_overrides[get_tenant_context] = resolve_test_context
                test_app.dependency_overrides[get_db] = disposable_test_session
                replay_params = {
                    "generation": generation,
                    "after_cursor": baseline_cursor,
                }
                with TestClient(test_app) as http:
                    owner_snapshot = http.get("/realtime/data-center/snapshot-preview")
                    assert owner_snapshot.status_code == 200, owner_snapshot.text
                    assert owner_snapshot.headers["cache-control"] == "private, no-store"
                    assert owner_snapshot.json()["ready"] is True
                    assert owner_snapshot.json()["cursor"] == baseline_cursor + 1
                    owner_replay = http.get(
                        "/realtime/data-center/replay", params=replay_params,
                    )
                    assert owner_replay.status_code == 200, owner_replay.text
                    assert owner_replay.headers["cache-control"] == "private, no-store"
                    assert owner_replay.json()["next_cursor"] == baseline_cursor + 1
                    assert owner_replay.json()["payloads_included"] is False

                    current_context[0] = branch_context
                    assert http.get(
                        "/realtime/data-center/snapshot-preview"
                    ).status_code == 403
                    assert http.get(
                        "/realtime/data-center/replay",
                        params=replay_params,
                    ).status_code == 403
                    current_context[0] = context

                    # FastAPI's query validation must reject malformed cursors,
                    # generation and oversized pages before service execution.
                    for invalid in (
                        {"generation": generation, "after_cursor": -1},
                        {"generation": generation, "limit": 201},
                        {"generation": "not-a-uuid"},
                    ):
                        assert http.get(
                            "/realtime/data-center/replay", params=invalid,
                        ).status_code == 422

            # Exercise the actual privileged operator CLI on this throwaway
            # PostgreSQL database, never a production database.
            from argparse import Namespace
            from scripts.data_center_pilot_control import run as pilot_control
            original_operator_url = os.environ.get("LOANHUB_DC_OPERATOR_DATABASE_URL")
            os.environ["LOANHUB_DC_OPERATOR_DATABASE_URL"] = database_url.render_as_string(
                hide_password=False
            )
            try:
                def command(action, *, apply=False, confirm=None):
                    return Namespace(
                        action=action,
                        company_id=company,
                        confirm_company=confirm,
                        operator="ci-pilot-operator",
                        approval_ref="CI-DISPOSABLE-ONLY",
                        apply=apply,
                    )
                assert pilot_control(command("disable")) == 0
                with engine.connect() as con:
                    assert con.execute(text("""
                        SELECT enabled FROM loanhub_dc_capture WHERE company_id = :id
                    """), {"id": company}).scalar_one() is True
                    assert con.execute(text("""
                        SELECT count(*) FROM loanhub_dc_pilot_audit
                        WHERE company_id = :id
                    """), {"id": company}).scalar_one() == 0

                assert pilot_control(command("disable", apply=True, confirm=company)) == 0
                with engine.connect() as con:
                    inactive_generation = con.execute(text("""
                        SELECT generation FROM loanhub_dc_capture WHERE company_id = :id
                    """), {"id": company}).scalar_one()
                    assert con.execute(text("""
                        SELECT enabled FROM loanhub_dc_capture WHERE company_id = :id
                    """), {"id": company}).scalar_one() is False

                # The HTTP endpoint must also return not-ready after an
                # audited disable; an old generation cannot yield events.
                with TestClient(test_app) as http:
                    current_context[0] = context
                    stopped = http.get("/realtime/data-center/snapshot-preview")
                    assert stopped.status_code == 200
                    assert stopped.json()["ready"] is False
                    assert stopped.json()["replay_supported"] is False
                    assert http.get(
                        "/realtime/data-center/replay", params=replay_params,
                    ).status_code == 409

                # Revoking capture must instantly revoke both server
                # readiness and the replay contract for existing clients.
                from services.data_center_replay import ReplayNotReady
                with Session(engine) as db:
                    disabled_snapshot = preview_snapshot(context, db)
                    assert disabled_snapshot["ready"] is False
                    assert disabled_snapshot["replay_supported"] is False
                    assert disabled_snapshot["buckets"] == {}
                    bind_database_tenant_context(
                        db, user_id=member_user.id, company_id=company,
                        role=UserRole.COMPANY_OWNER.value, actor_scope="tenant",
                    )
                    with pytest.raises(ReplayNotReady, match="Capture disabled"):
                        replay_metadata(
                            db, context, after_cursor=baseline_cursor,
                            generation=UUID(generation),
                        )
                    db.rollback()

                assert pilot_control(command("activate")) == 0
                assert pilot_control(command("activate", apply=True, confirm=company)) == 0
                with engine.connect() as con:
                    active = con.execute(text("""
                        SELECT enabled, generation FROM loanhub_dc_capture
                        WHERE company_id = :id
                    """), {"id": company}).one()
                    assert active.enabled is True
                    assert active.generation != inactive_generation
                    assert active.generation != UUID(generation)
                    assert con.execute(text("""
                        SELECT array_agg(action ORDER BY id)
                        FROM loanhub_dc_pilot_audit WHERE company_id = :id
                    """), {"id": company}).scalar_one() == ["disable", "activate"]

                # Actual HTTP replay must reject clients still using their
                # old generation after the audited reactivation.
                with TestClient(test_app) as http:
                    assert http.get(
                        "/realtime/data-center/replay", params=replay_params,
                    ).status_code == 409
                    refreshed = http.get("/realtime/data-center/snapshot-preview")
                    assert refreshed.status_code == 200
                    assert refreshed.json()["ready"] is True
                    assert refreshed.json()["generation"] == str(active.generation)

                # Old-generation clients must not replay after an authorized
                # stop/restart; a new consistent snapshot is mandatory.
                with Session(engine) as db:
                    bind_database_tenant_context(
                        db, user_id=member_user.id, company_id=company,
                        role=UserRole.COMPANY_OWNER.value, actor_scope="tenant",
                    )
                    with pytest.raises(ReplayNotReady, match="generation changed"):
                        replay_metadata(
                            db, context, after_cursor=baseline_cursor,
                            generation=UUID(generation),
                        )
                    db.rollback()
                    resumed = preview_snapshot(context, db)
                    assert resumed["ready"] is True
                    assert resumed["generation"] == str(active.generation)
                    assert resumed["cursor"] >= baseline_cursor

                # Revoke owner membership after the authenticated context
                # was constructed. No replay may use that stale context.
                with engine.begin() as con:
                    con.execute(text("""
                        UPDATE company_staff SET is_active = false
                        WHERE id = :staff_id
                    """), {"staff_id": member.id})
                with Session(engine) as db:
                    bind_database_tenant_context(
                        db, user_id=member_user.id, company_id=company,
                        role=UserRole.COMPANY_OWNER.value, actor_scope="tenant",
                    )
                    with pytest.raises(PermissionError):
                        replay_metadata(
                            db, context, after_cursor=baseline_cursor,
                            generation=active.generation,
                        )
                with engine.begin() as con:
                    con.execute(text("""
                        UPDATE company_staff SET is_active = true
                        WHERE id = :staff_id
                    """), {"staff_id": member.id})

                # A revoked user and an inactive company must also fail
                # even if a stale HTTP context still contains valid staff.
                for table, identifier in (("users", member_user.id), ("loan_companies", company)):
                    with engine.begin() as con:
                        con.execute(text(f"""
                            UPDATE {table} SET is_active = false WHERE id = :id
                        """), {"id": identifier})
                    try:
                        with Session(engine) as db:
                            bind_database_tenant_context(
                                db, user_id=member_user.id, company_id=company,
                                role=UserRole.COMPANY_OWNER.value, actor_scope="tenant",
                            )
                            with pytest.raises(PermissionError, match="inactive"):
                                replay_metadata(
                                    db, context, after_cursor=baseline_cursor,
                                    generation=active.generation,
                                )
                    finally:
                        with engine.begin() as con:
                            con.execute(text(f"""
                                UPDATE {table} SET is_active = true WHERE id = :id
                            """), {"id": identifier})
            finally:
                if original_operator_url is None:
                    os.environ.pop("LOANHUB_DC_OPERATOR_DATABASE_URL", None)
                else:
                    os.environ["LOANHUB_DC_OPERATOR_DATABASE_URL"] = original_operator_url
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
