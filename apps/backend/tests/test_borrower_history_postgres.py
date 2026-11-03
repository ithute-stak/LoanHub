"""Real PostgreSQL query regression for borrower loan history and tenant boundaries.

This tests the production list_loans handler with a disposable PostgreSQL
projection of the four authorization / pagination keys. The production ORM
has many financial columns not needed for this query contract; no actual
financial records or schema migrations are modified.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import Column, DateTime, create_engine, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, declarative_base

from database.models.enums import UserRole
from routers import loans as loans_router


def test_borrower_history_paginates_and_enforces_company_branch_scope(monkeypatch):
    url = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL integration URL not configured")

    engine = create_engine(url)
    schema = "borrower_history_" + uuid4().hex[:12]
    base = declarative_base()
    company_a, company_b = uuid4(), uuid4()
    branch_a, branch_b = uuid4(), uuid4()
    borrower, other_borrower = uuid4(), uuid4()

    class LoanRow(base):
        __tablename__ = "loan_rows"
        __table_args__ = {"schema": schema}
        id = Column(UUID(as_uuid=True), primary_key=True)
        company_id = Column(UUID(as_uuid=True), nullable=False)
        branch_id = Column(UUID(as_uuid=True), nullable=True)
        borrower_id = Column(UUID(as_uuid=True), nullable=False)
        created_at = Column(DateTime, nullable=False)

    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                base.metadata.create_all(conn)
                now = datetime(2026, 11, 3)
                rows = [
                    {"id": uuid4(), "company_id": company_a, "branch_id": branch_a,
                     "borrower_id": borrower, "created_at": now - timedelta(minutes=i)}
                    for i in range(525)
                ]
                rows += [
                    {"id": uuid4(), "company_id": company_a, "branch_id": branch_b,
                     "borrower_id": borrower, "created_at": now + timedelta(minutes=1)},
                    {"id": uuid4(), "company_id": company_b, "branch_id": branch_a,
                     "borrower_id": borrower, "created_at": now + timedelta(minutes=2)},
                    {"id": uuid4(), "company_id": company_a, "branch_id": branch_a,
                     "borrower_id": other_borrower, "created_at": now + timedelta(minutes=3)},
                ]
                conn.execute(LoanRow.__table__.insert(), rows)
                monkeypatch.setattr(loans_router, "ClientCompanyLoan", LoanRow)
                monkeypatch.setattr(loans_router, "loan_query", lambda db: db.query(LoanRow))
                role = UserRole.COMPANY_OWNER
                monkeypatch.setattr(
                    loans_router, "resolve_tenant_context",
                    lambda *_args: SimpleNamespace(
                        company_id=company_a, branch_id=branch_a, role=role
                    ),
                )
                current_user = SimpleNamespace(role=role)
                with Session(bind=conn) as db:
                    def fetch(skip, limit, for_borrower=borrower):
                        return loans_router.list_loans(
                            skip=skip, limit=limit, borrower_id=for_borrower,
                            x_company_id=None, x_active_role=None, db=db,
                            current_user=current_user,
                        )

                    first = fetch(0, 500)
                    second = fetch(500, 500)
                    assert len(first) == 500
                    assert len(second) == 26  # owner can see both branches
                    assert {loan.id for loan in first}.isdisjoint({loan.id for loan in second})
                    assert all(loan.company_id == company_a and loan.borrower_id == borrower
                               for loan in first + second)
                    assert fetch(0, 500, other_borrower)[0].borrower_id == other_borrower

                    role = UserRole.LOAN_OFFICER
                    scoped = fetch(0, 500) + fetch(500, 500)
                    assert len(scoped) == 525
                    assert all(loan.branch_id == branch_a for loan in scoped)
                    assert not fetch(0, 500, uuid4())
            finally:
                outer.rollback()
    finally:
        engine.dispose()
