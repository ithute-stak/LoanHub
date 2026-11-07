"""Disposable PostgreSQL contract tests for the Phase 36 reservation core.

Only runs with LOANHUB_BATLOKOA_TEST_POSTGRES_URL, explicitly provided by
isolated CI. Creates and drops a unique schema; no production tables touched.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from services.batlokoa_reservation_store import (
    ReservationDecision, ReservationRequest, reserve_in_existing_transaction,
    reservation_metadata,
)

URL = os.getenv("LOANHUB_BATLOKOA_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not URL or not URL.startswith("postgresql+psycopg2://"),
    reason="Requires explicitly configured disposable PostgreSQL CI database",
)

COMPANY = UUID("4236a21f-5164-48aa-90f3-a35eccd23ae2")
OTHER = UUID("00000000-0000-4000-8000-000000000002")
LOAN = UUID("00000000-0000-4000-8000-000000000003")
BORROWER = UUID("00000000-0000-4000-8000-000000000004")


def request(*, company=COMPANY, fingerprint="a" * 64, key="collect_request_TEST123456"):
    return ReservationRequest(
        company_id=company,
        loan_id=LOAN, borrower_id=BORROWER,
        idempotency_key=key, request_fingerprint=fingerprint,
        amount=Decimal("100.00"),
    )


@pytest.fixture
def isolated_database():
    schema = "batlokoa_ci_" + uuid4().hex
    admin = create_engine(URL, poolclass=NullPool)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    # Per-connection search path is isolated to this disposable schema.
    engine = create_engine(
        URL, poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        reservation_metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def reserve(engine, req):
    with Session(engine) as session:
        with session.begin():
            return reserve_in_existing_transaction(
                session, request=req,
                verified_company_id=req.company_id, enabled=True,
            )


def test_new_duplicate_conflict_and_cross_tenant(isolated_database):
    engine = isolated_database
    created = reserve(engine, request())
    assert created.decision is ReservationDecision.CREATED
    repeated = reserve(engine, request())
    assert repeated.decision is ReservationDecision.REPLAY
    assert repeated.reservation_id == created.reservation_id
    changed = reserve(engine, request(fingerprint="b" * 64))
    assert changed.decision is ReservationDecision.CONFLICT
    second_tenant = reserve(engine, request(company=OTHER))
    assert second_tenant.decision is ReservationDecision.CREATED
    assert second_tenant.reservation_id != created.reservation_id
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM batlokoa_collection_intent_reservations"
        )) == 2


def test_rollback_allows_safe_retry(isolated_database):
    engine = isolated_database
    with Session(engine) as session:
        with session.begin():
            first = reserve_in_existing_transaction(
                session, request=request(),
                verified_company_id=COMPANY, enabled=True,
            )
            assert first.decision is ReservationDecision.CREATED
            session.rollback()
    retry = reserve(engine, request())
    assert retry.decision is ReservationDecision.CREATED
    assert retry.reservation_id != first.reservation_id


def test_concurrent_same_key_has_one_creation(isolated_database):
    engine = isolated_database
    barrier = Barrier(2)
    def attempt():
        barrier.wait(timeout=20)
        return reserve(engine, request())
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        decisions = [f.result(timeout=35).decision for f in futures]
    assert sorted(decisions) == sorted([
        ReservationDecision.CREATED, ReservationDecision.REPLAY,
    ])


def test_concurrent_conflicting_payload_cannot_reserve_twice(isolated_database):
    engine = isolated_database
    barrier = Barrier(2)
    def attempt(fp):
        barrier.wait(timeout=20)
        return reserve(engine, request(fingerprint=fp))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, fp) for fp in ("a" * 64, "b" * 64)]
        decisions = [f.result(timeout=35).decision for f in futures]
    assert sorted(decisions) == sorted([
        ReservationDecision.CREATED, ReservationDecision.CONFLICT,
    ])
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM batlokoa_collection_intent_reservations"
        )) == 1
