"""Alembic-to-head smoke test on a disposable PostgreSQL database.

This is a schema certification gate only, not authorization to activate rollover.
No production or persistent database may be supplied here.
"""
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = (
    "client_company_loan",
    "repayment_installments",
    "loan_rollover_transfers",
    "audit_logs",
)


def test_full_migrations_provide_rollover_financial_schema():
    source = os.getenv("LOANHUB_MIGRATION_CERTIFICATION_POSTGRES_URL")
    if not source:
        pytest.skip("Dedicated disposable-database certification URL not configured")
    if os.getenv("CI") != "true":
        pytest.skip("Migration certification is restricted to isolated CI")

    url = make_url(source)
    assert url.get_backend_name() == "postgresql", "PostgreSQL is required"
    assert url.database == "loan_db", "Only the dedicated CI seed database is permitted"
    assert url.host in ("127.0.0.1", "localhost"), "Never run against remote databases"

    name = "loanhub_rollover_cert_" + uuid4().hex[:16]
    admin_url = url.set(database="postgres")
    test_url = url.set(database=name)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    created = False
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True

        env = os.environ.copy()
        env["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
        env["DB_NAME"] = name
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND, env=env, check=True, timeout=600,
        )
        cfg = Config(str(BACKEND / "alembic.ini"))
        expected_heads = set(ScriptDirectory.from_config(cfg).get_heads())
        assert len(expected_heads) == 1, "Migration history must have exactly one head"

        engine = create_engine(test_url)
        try:
            with engine.connect() as conn:
                actual_heads = set(conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalars())
                assert actual_heads == expected_heads
                inspector = inspect(conn)
                for table in EXPECTED_TABLES:
                    assert inspector.has_table(table), f"Missing migrated table: {table}"
                for table in ("client_company_loan", "repayment_installments", "loan_rollover_transfers"):
                    assert inspector.get_foreign_keys(table), f"Missing migrated foreign keys: {table}"
                child_columns = {c["name"] for c in inspector.get_columns("client_company_loan")}
                assert {"id", "company_id", "parent_loan_id", "folio_number", "balance"} <= child_columns
                transfer_columns = {c["name"] for c in inspector.get_columns("loan_rollover_transfers")}
                assert {"parent_loan_id", "child_loan_id", "transfer_amount",
                        "principal_component", "interest_component"} <= transfer_columns
            _certify_migrated_posting(engine)
        finally:
            engine.dispose()
    finally:
        if created:
            with admin.connect() as conn:
                conn.execute(text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database AND pid <> pg_backend_pid()"
                ), {"database": name})
                conn.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()

def _certify_migrated_posting(engine):
    """Exercise guarded posting body only inside the throwaway migrated database."""
    import ast
    import inspect as pyinspect
    import textwrap
    from datetime import date
    from decimal import Decimal
    from uuid import UUID
    from fastapi import HTTPException
    from sqlalchemy.orm import Session
    import database.models  # noqa: F401
    from database.models.user import User
    from database.models.borrower import Borrower
    from database.models.company import LoanCompany
    from database.models.client_loan_company import ClientCompanyLoan
    from database.models.repayment import RepaymentInstallment
    from database.models.loan_rollover_transfer import LoanRolloverTransfer
    from database.models.audit_log import AuditLog
    from database.models.enums import (
        CompanyStatus, EmploymentStatus, UserRole, LoanStatus,
        RepaymentType, RiskLevel, InstallmentStatus,
    )
    from services import final_installment_rollover_posting as posting

    source = textwrap.dedent(pyinspect.getsource(posting.post_final_rollover))
    tree = ast.parse(source)
    guard = tree.body[0].body[0]
    assert isinstance(guard, ast.Raise)
    assert any(
        keyword.arg == "status_code"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value == 503
        for keyword in guard.exc.keywords
    ), "The live 503 safety guard must remain in place"
    tree.body[0].body.pop(0)
    ast.fix_missing_locations(tree)
    namespace = vars(posting).copy()
    namespace["generate_loan_reference"] = lambda _db, _company: "MIGRATED-CHILD-" + uuid4().hex
    exec(compile(tree, pyinspect.getfile(posting.post_final_rollover), "exec"), namespace)
    test_only_post = namespace["post_final_rollover"]

    def seed(db, suffix):
        maker = User(
            phone="590" + uuid4().hex[:9], password_hash="not-a-login",
            role=UserRole.COMPANY_OWNER, is_active=True,
        )
        borrower_user = User(
            phone="580" + uuid4().hex[:9], password_hash="not-a-login",
            role=UserRole.BORROWER, is_active=True,
        )
        db.add_all([maker, borrower_user])
        db.flush()
        borrower = Borrower(
            user_id=borrower_user.id, employment_status=EmploymentStatus.EMPLOYED,
        )
        company = LoanCompany(
            name="Migration certification " + suffix,
            phone="000000000", status=CompanyStatus.APPROVED, is_active=True,
        )
        db.add_all([borrower, company])
        db.flush()
        parent = ClientCompanyLoan(
            company_id=company.id, borrower_id=borrower.id,
            loan_reference="MIGRATED-PARENT-" + suffix,
            origination_channel="direct", is_top_up=False,
            principal_amount=Decimal("100"), interest_rate=Decimal("0"),
            processing_fee=Decimal("0"), total_repayable=Decimal("100"),
            repayment_type=RepaymentType.MONTHLY, repayment_period=1,
            installment_amount=Decimal("100"), calculation_method="micro_loan",
            calculation_breakdown={}, cdas_collection_enabled=False,
            cdas_collection_plan={}, preferred_payment_day=20,
            amount_paid=Decimal("40"), balance=Decimal("60"),
            status=LoanStatus.ACTIVE, risk_level=RiskLevel.LOW,
            is_overdue=True, automatic_renewal_enabled=False,
        )
        db.add(parent)
        db.flush()
        installment = RepaymentInstallment(
            loan_id=parent.id, installment_number=1,
            due_date=date(2026, 11, 1), principal_due=Decimal("70"),
            interest_due=Decimal("30"), fee_due=Decimal("0"),
            total_due=Decimal("100"), paid_amount=Decimal("40"),
            status=InstallmentStatus.OVERDUE, is_superseded=False,
        )
        db.add(installment)
        db.commit()
        return company.id, parent.id, installment.id, maker.id

    def arguments(ids):
        company, parent, installment, maker = ids
        return dict(
            company_id=company, parent_id=parent, installment_id=installment,
            approved_amount=Decimal("60"), due_date=date(2026, 12, 20),
            agreement_reference="MIGRATED-SIGNED-AGREEMENT",
            approval_reference="MIGRATED-APPROVAL-" + uuid4().hex,
            actor_user_id=maker, actor_role="company_owner",
            as_of=date(2026, 11, 3),
            component_evidence=dict(
                source_reference="MIGRATED-ALLOCATION",
                verified_by="FINANCE-REVIEWER",
                principal_paid="30", interest_paid="10", fee_paid="0",
            ),
        )

    with Session(engine, expire_on_commit=False) as db:
        good = seed(db, "success")
        with pytest.raises(HTTPException) as disabled:
            posting.post_final_rollover(db, **arguments(good))
        assert disabled.value.status_code == 503
        result = test_only_post(db, **arguments(good))
        child_id = UUID(result["child_loan_id"])
        assert Decimal(result["transferred_amount"]) == Decimal("60")
        assert Decimal(result["cash_disbursement"]) == 0
    # Verify persisted state using a *new* independent database connection.
    with Session(engine) as verify:
        company_id, parent_id, installment_id, maker_id = good
        parent = verify.get(ClientCompanyLoan, parent_id)
        child = verify.get(ClientCompanyLoan, child_id)
        row = verify.get(RepaymentInstallment, installment_id)
        transfer = verify.query(LoanRolloverTransfer).filter_by(
            parent_loan_id=parent_id
        ).one()
        assert parent.balance == Decimal("0")
        assert parent.status == LoanStatus.COMPLETED
        assert child.company_id == company_id
        assert child.parent_loan_id == parent_id
        assert child.principal_amount == Decimal("40")
        assert child.balance == Decimal("60")
        assert row.paid_amount == Decimal("40") and row.is_superseded
        assert transfer.principal_component == Decimal("40")
        assert transfer.interest_component == Decimal("20")
        assert transfer.transfer_amount == Decimal("60")
        assert verify.query(RepaymentInstallment).filter_by(
            loan_id=child.id
        ).one().interest_due == Decimal("20")
        assert verify.query(AuditLog).filter_by(
            record_id=parent_id,
            action="loan.final_installment_receivable_transferred",
        ).count() == 1

    with Session(engine, expire_on_commit=False) as db:
        failed = seed(db, "rollback")
        def fail_after_financial_flush(**_kwargs):
            db.flush()
            assert db.query(LoanRolloverTransfer).filter_by(
                parent_loan_id=failed[1]
            ).count() == 1
            raise HTTPException(status_code=409, detail="Injected reconciliation failure")
        test_only_post.__globals__["reconcile_rollover_accounting"] = fail_after_financial_flush
        with pytest.raises(HTTPException, match="Injected reconciliation failure"):
            with db.begin_nested():
                test_only_post(db, **arguments(failed))
        db.rollback()
    with Session(engine) as verify:
        company_id, parent_id, installment_id, maker_id = failed
        parent = verify.get(ClientCompanyLoan, parent_id)
        row = verify.get(RepaymentInstallment, installment_id)
        assert parent.balance == Decimal("60")
        assert parent.status == LoanStatus.ACTIVE
        assert not row.is_superseded and row.paid_amount == Decimal("40")
        assert verify.query(ClientCompanyLoan).filter_by(
            parent_loan_id=parent_id
        ).count() == 0
        assert verify.query(LoanRolloverTransfer).filter_by(
            parent_loan_id=parent_id
        ).count() == 0
        assert verify.query(AuditLog).filter_by(
            record_id=parent_id,
            action="loan.final_installment_receivable_transferred",
        ).count() == 0
