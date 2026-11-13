"""Regression: same borrower may have independently settled and active loans.

Runs against disposable in-memory SQLite data, never production. This invokes
LoanHub's actual portfolio handler using a minimal SQLAlchemy projection.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import Column, DateTime, Numeric, String, Uuid, create_engine
from sqlalchemy.orm import Session, declarative_base

from database.models.enums import UserRole
from routers import loans as loans_router


def test_same_borrower_legacy_and_current_loan_keep_independent_state(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    base = declarative_base()

    class LoanRow(base):
        __tablename__ = "isolated_loan_state"
        id = Column(Uuid(as_uuid=True), primary_key=True)
        borrower_id = Column(Uuid(as_uuid=True), nullable=False)
        company_id = Column(Uuid(as_uuid=True), nullable=False)
        branch_id = Column(Uuid(as_uuid=True), nullable=True)
        created_at = Column(DateTime, nullable=False)
        loan_reference = Column(String, nullable=False)
        status = Column(String, nullable=False)
        amount_paid = Column(Numeric(14, 2), nullable=False)
        balance = Column(Numeric(14, 2), nullable=False)
        total_repayable = Column(Numeric(14, 2), nullable=False)

    base.metadata.create_all(engine)
    borrower, other_borrower = uuid4(), uuid4()
    company_a, company_b, branch = uuid4(), uuid4(), uuid4()
    old_id, new_id, foreign_id, other_id = (uuid4() for _ in range(4))
    now = datetime(2026, 11, 13)
    rows = [
        dict(id=old_id, company_id=company_a, branch_id=branch,
             borrower_id=borrower, created_at=now - timedelta(days=200),
             loan_reference="LEGACY-SYNTH-001", status="completed",
             amount_paid=Decimal("1500.00"), balance=Decimal("0.00"),
             total_repayable=Decimal("1500.00")),
        dict(id=new_id, company_id=company_a, branch_id=branch,
             borrower_id=borrower, created_at=now,
             loan_reference="CURRENT-SYNTH-002", status="active",
             amount_paid=Decimal("100.00"), balance=Decimal("900.00"),
             total_repayable=Decimal("1000.00")),
        dict(id=foreign_id, company_id=company_b, branch_id=branch,
             borrower_id=borrower, created_at=now + timedelta(days=1),
             loan_reference="OTHER-TENANT-SYNTH", status="completed",
             amount_paid=Decimal("2000.00"), balance=Decimal("0.00"),
             total_repayable=Decimal("2000.00")),
        dict(id=other_id, company_id=company_a, branch_id=branch,
             borrower_id=other_borrower, created_at=now + timedelta(days=2),
             loan_reference="OTHER-BORROWER-SYNTH", status="completed",
             amount_paid=Decimal("800.00"), balance=Decimal("0.00"),
             total_repayable=Decimal("800.00")),
    ]
    role = UserRole.COMPANY_OWNER
    monkeypatch.setattr(loans_router, "ClientCompanyLoan", LoanRow)
    monkeypatch.setattr(loans_router, "loan_query", lambda db: db.query(LoanRow))
    monkeypatch.setattr(
        loans_router, "resolve_tenant_context",
        lambda *_args: SimpleNamespace(company_id=company_a, branch_id=branch, role=role)
    )
    try:
        with Session(engine) as db:
            db.add_all(LoanRow(**row) for row in rows)
            db.commit()

            def read_history(borrower_id):
                return loans_router.list_loans(
                    skip=0, limit=500, borrower_id=borrower_id,
                    x_company_id=None, x_active_role=None, db=db,
                    current_user=SimpleNamespace(role=role),
                )

            history = read_history(borrower)
            assert len(history) == 2
            by_id = {loan.id: loan for loan in history}
            assert set(by_id) == {old_id, new_id}
            assert (by_id[old_id].status, by_id[old_id].balance) == (
                "completed", Decimal("0.00")
            )
            assert (by_id[new_id].status, by_id[new_id].balance) == (
                "active", Decimal("900.00")
            )
            assert by_id[old_id].amount_paid == Decimal("1500.00")
            assert by_id[new_id].amount_paid == Decimal("100.00")
            assert [loan.id for loan in read_history(other_borrower)] == [other_id]
            assert read_history(uuid4()) == []
    finally:
        engine.dispose()


def test_loan_detail_and_repayment_frontend_bind_to_exact_loan_id():
    """Static API contract complements the executable portfolio isolation test."""
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[2] / "frontend"
    loan_api = (frontend / "api" / "loans.ts").read_text(encoding="utf-8")
    portfolio = (
        frontend / "app" / "(dashboard)" / "company" / "loans" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "get<Loan>(`/loans/${loanId}`)" in loan_api
    assert "/loans/${loanId}/installments/${installmentId}/payments" in loan_api
    assert "getLoan(selectedLoan.id)" in portfolio
    assert "setSelectedLoan(loan);" in portfolio
