"""Real PostgreSQL transaction tests for the signature lookup privacy budget.

Only executes in CI against a disposable local PostgreSQL service. Uses an
isolated test-only audit table with the same fields touched by the service;
never queries or mutates the application audit_logs table.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, DateTime, String, UUID, create_engine, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base

from services import signature_lookup_security as security


@pytest.fixture
def postgres(monkeypatch):
    url_value = os.getenv("LOANHUB_SIGNATURE_LOOKUP_TEST_POSTGRES_URL")
    if not url_value:
        pytest.skip("Disposable signature lookup PostgreSQL URL unavailable")
    if os.getenv("CI") != "true":
        pytest.skip("Unsafe to run signature lookup PostgreSQL tests outside CI")
    url = make_url(url_value)
    assert url.get_backend_name() == "postgresql"
    assert url.host in ("127.0.0.1", "localhost")
    assert url.database == "loan_db"

    Base = declarative_base()
    table_name = "signature_lookup_ci_" + uuid4().hex[:16]

    class AuditProbe(Base):
        __tablename__ = table_name
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
        user_id = Column(UUID(as_uuid=True), nullable=False)
        company_id = Column(UUID(as_uuid=True), nullable=False)
        action = Column(String(150), nullable=False)
        table_name = Column(String(150))
        entity_type = Column(String(150))
        description = Column(String(500))
        status = Column(String(30))
        severity = Column(String(30))
        event_data = Column(JSONB, default=dict)
        created_at = Column(DateTime, server_default=func.now(), nullable=False)

    engine = create_engine(url_value, pool_size=12, max_overflow=0)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(security, "AuditLog", AuditProbe)
    try:
        yield engine, AuditProbe
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _reserve(engine, company, user):
    with Session(engine) as db:
        try:
            security.reserve_lookup_attempt(db, company_id=company, operator_id=user)
            return 200
        except HTTPException as exc:
            return exc.status_code


def test_lookup_budget_is_enforced_after_eight_real_commits(postgres):
    engine, Model = postgres
    company, user = uuid4(), uuid4()
    assert [_reserve(engine, company, user) for _ in range(9)] == [200] * 8 + [429]
    with Session(engine) as db:
        rows = db.query(Model).all()
        assert len(rows) == 8
        assert all(row.company_id == company and row.user_id == user for row in rows)
        assert all(row.event_data.get("contains_personal_data") is False for row in rows)


def test_lookup_budgets_are_isolated_by_tenant_and_operator(postgres):
    engine, Model = postgres
    company, other_company, operator, other_operator = uuid4(), uuid4(), uuid4(), uuid4()
    for _ in range(8):
        assert _reserve(engine, company, operator) == 200
    assert _reserve(engine, company, operator) == 429
    assert _reserve(engine, other_company, operator) == 200
    assert _reserve(engine, company, other_operator) == 200


def test_concurrent_lookups_cannot_bypass_postgres_budget(postgres):
    engine, Model = postgres
    company, operator = uuid4(), uuid4()
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: _reserve(engine, company, operator), range(12)))
    assert sorted(results) == [200] * 8 + [429] * 4
    with Session(engine) as db:
        assert db.query(Model).count() == 8
