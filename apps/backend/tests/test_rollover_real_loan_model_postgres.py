"""Exercise the production loan ORM and folio hooks on real PostgreSQL.

This uses the actual ClientCompanyLoan mapped table, column types and insertion
hooks. An isolated rollback-only schema provides small FK reference fixtures;
this is model-level certification, not yet full service-body activation testing.
"""
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

# Import model registry before configuring the real mapped loan class.
import database.models  # noqa: F401
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, RepaymentType, RiskLevel


def test_production_loan_mapping_allocates_real_postgres_folios_and_clears_completed_overdue():
    url = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL integration URL not configured")
    engine = create_engine(url)
    schema = "rollover_real_loan_" + uuid4().hex[:12]
    company, borrower = uuid4(), uuid4()

    def loan(ref, pay_day, *, parent_id=None, balance="60", status=LoanStatus.ACTIVE):
        return ClientCompanyLoan(
            company_id=company,
            borrower_id=borrower,
            parent_loan_id=parent_id,
            loan_reference=ref,
            origination_channel="balance_rollover" if parent_id else "direct",
            is_top_up=False,
            principal_amount=Decimal("60"),
            interest_rate=Decimal("0"),
            processing_fee=Decimal("0"),
            total_repayable=Decimal("60"),
            repayment_type=RepaymentType.MONTHLY,
            repayment_period=1,
            installment_amount=Decimal("60"),
            calculation_method="micro_loan",
            calculation_breakdown={},
            cdas_collection_enabled=False,
            cdas_collection_plan={},
            preferred_payment_day=pay_day,
            first_payment_due=date(2026, 12, pay_day),
            amount_paid=Decimal("0"),
            balance=Decimal(balance),
            status=status,
            risk_level=RiskLevel.LOW,
            is_overdue=True,
        )

    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                conn.execute(text("CREATE TABLE loan_companies (id uuid PRIMARY KEY, name text NOT NULL)"))
                conn.execute(text("CREATE TABLE employer_groups (id uuid PRIMARY KEY, code text, name text)"))
                conn.execute(text(
                    "CREATE TABLE borrowers (id uuid PRIMARY KEY, employer_group_id uuid, employer_name text)"
                ))
                conn.execute(text(
                    "INSERT INTO loan_companies (id, name) VALUES (:id, :name)"
                ), {"id": company, "name": "Batlokoa Financial Services"})
                conn.execute(text(
                    "INSERT INTO borrowers (id, employer_group_id, employer_name) "
                    "VALUES (:id, NULL, :name)"
                ), {"id": borrower, "name": "Sample employer"})
                # Preserve the production table's real SQLAlchemy columns,
                # defaults, constraints, enums and before_insert hooks.
                # Referenced application tables are excluded only because
                # this tests loan lifecycle and folios, not the entire schema.
                for col in ClientCompanyLoan.__table__.columns:
                    if getattr(col.type, "enum_class", None) is not None:
                        col.type.create(bind=conn, checkfirst=True)
                conn.execute(CreateTable(
                    ClientCompanyLoan.__table__,
                    include_foreign_key_constraints=[],
                ))
                with Session(bind=conn, expire_on_commit=False) as db:
                    parent = loan("REAL-PARENT", 20)
                    db.add(parent)
                    db.flush()
                    assert parent.folio_company_code == "BFS"
                    assert parent.folio_group_code == "Force"
                    assert parent.folio_sequence == 1
                    assert parent.folio_number == "BFS-Force-00001"
                    assert parent.is_overdue is True

                    # A rollover child is a separate facility with its own
                    # immutable folio; it must not reuse the parent's folio.
                    child = loan("REAL-CHILD", 20, parent_id=parent.id)
                    db.add(child)
                    db.flush()
                    assert child.folio_number == "BFS-Force-00002"
                    assert child.parent_loan_id == parent.id
                    assert child.is_overdue is True

                    other_group = loan("REAL-CIVIL", 25)
                    db.add(other_group)
                    db.flush()
                    assert other_group.folio_number == "BFS-CIVIL-00001"

                    # Production before_update hook must prevent completed
                    # zero-balance parents from remaining overdue.
                    parent.balance = Decimal("0")
                    parent.status = LoanStatus.COMPLETED
                    parent.is_overdue = True
                    db.flush()
                    db.expire_all()
                    reloaded_parent = db.get(ClientCompanyLoan, parent.id)
                    reloaded_child = db.get(ClientCompanyLoan, child.id)
                    assert reloaded_parent.status == LoanStatus.COMPLETED
                    assert reloaded_parent.balance == Decimal("0")
                    assert reloaded_parent.is_overdue is False
                    assert reloaded_child.balance == Decimal("60")
                    assert reloaded_child.parent_loan_id == reloaded_parent.id
                    assert reloaded_child.folio_number != reloaded_parent.folio_number
                    assert db.query(ClientCompanyLoan).count() == 3
            finally:
                outer.rollback()
    finally:
        engine.dispose()
