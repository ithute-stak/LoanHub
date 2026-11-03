"""Run the real rollover posting body through PostgreSQL ORM transactions.

The production 503 remains intact. A test-only compiled copy removes just
that initial guard, and uses real ORM loan/repayment/transfer/audit persistence.
The loan model is deliberately schema-minimal, while only the child-reference generator is substituted; the real preview,
rollover plan, receivable reconciliation and posting body all execute. Therefore this is
service-body transaction evidence, not complete production certification.
"""
import ast
import inspect
import os
import textwrap
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Boolean, Column, Date, Enum, Integer, Numeric, String, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Session, declarative_base, object_session

from database.models.audit_log import AuditLog
from database.models.enums import InstallmentStatus, LoanStatus, RepaymentType, RiskLevel
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.repayment import RepaymentInstallment
from services import final_installment_rollover_posting as posting


TestBase = declarative_base()


class TestLoan(TestBase):
    __tablename__ = "client_company_loan"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    branch_id = Column(UUID(as_uuid=True))
    borrower_id = Column(UUID(as_uuid=True))
    parent_loan_id = Column(UUID(as_uuid=True))
    loan_reference = Column(String, nullable=False)
    folio_number = Column(String, nullable=False, default="TEST-FOLIO")
    origination_channel = Column(String)
    is_top_up = Column(Boolean, default=False)
    principal_amount = Column(Numeric(15, 2), nullable=False)
    interest_rate = Column(Numeric(6, 3), nullable=False)
    processing_fee = Column(Numeric(15, 2), nullable=False)
    total_repayable = Column(Numeric(15, 2), nullable=False)
    repayment_type = Column(Enum(RepaymentType), nullable=False)
    repayment_period = Column(Integer, nullable=False)
    installment_amount = Column(Numeric(15, 2), nullable=False)
    calculation_method = Column(String, nullable=False)
    calculation_breakdown = Column(JSONB, nullable=False)
    cdas_collection_enabled = Column(Boolean, nullable=False)
    cdas_collection_plan = Column(JSONB, nullable=False)
    approved_at = Column(Date)
    approved_by_user_id = Column(UUID(as_uuid=True))
    first_payment_due = Column(Date)
    preferred_payment_day = Column(Integer)
    maturity_date = Column(Date)
    amount_paid = Column(Numeric(15, 2), nullable=False)
    balance = Column(Numeric(15, 2), nullable=False)
    status = Column(Enum(LoanStatus), nullable=False)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    is_overdue = Column(Boolean, nullable=False)
    automatic_renewal_enabled = Column(Boolean)

    @property
    def installments(self):
        return (object_session(self).query(RepaymentInstallment)
                .filter(RepaymentInstallment.loan_id == self.id)
                .order_by(RepaymentInstallment.installment_number).all())

    @property
    def company(self):
        return None


def isolated_posting(*, reconciliation=None):
    tree = ast.parse(textwrap.dedent(inspect.getsource(posting.post_final_rollover)))
    fn = tree.body[0]
    gate = fn.body[0]
    assert isinstance(gate, ast.Raise)
    assert any(k.arg == "status_code" and isinstance(k.value, ast.Constant)
               and k.value.value == 503 for k in gate.exc.keywords)
    fn.body.pop(0)
    ast.fix_missing_locations(tree)
    namespace = vars(posting).copy()
    namespace.update({
        "ClientCompanyLoan": TestLoan,
        "generate_loan_reference": lambda *args: "SESSION-CHILD",
    })
    if reconciliation is not None:
        namespace["reconcile_rollover_accounting"] = reconciliation
    exec(compile(tree, inspect.getfile(posting.post_final_rollover), "exec"), namespace)
    return namespace["post_final_rollover"]


@pytest.mark.parametrize("reject_accounting", [False, True])
def test_posting_service_body_commits_actual_postgres_loan_schedule_and_ledgers(reject_accounting):
    url = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL integration URL not configured")
    engine = create_engine(url)
    schema = "rollover_service_post_" + uuid4().hex[:12]
    company, maker, parent_id, borrower = [uuid4() for _ in range(4)]
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                for table in ("loan_companies", "users", "company_branches", "loan_renewal_cycles"):
                    conn.execute(text(f'CREATE TABLE "{table}" (id uuid PRIMARY KEY)'))
                conn.execute(text('INSERT INTO loan_companies VALUES (:id)'), {"id": company})
                conn.execute(text('INSERT INTO users VALUES (:id)'), {"id": maker})
                TestLoan.__table__.create(bind=conn)
                RepaymentInstallment.__table__.create(bind=conn)
                LoanRolloverTransfer.__table__.create(bind=conn)
                AuditLog.__table__.create(bind=conn)
                with Session(bind=conn, expire_on_commit=False) as db:
                    parent = TestLoan(
                        id=parent_id, company_id=company, branch_id=None,
                        borrower_id=borrower, parent_loan_id=None,
                        loan_reference="SESSION-PARENT", folio_number="PARENT-FOLIO",
                        principal_amount=Decimal("100"), interest_rate=Decimal("0"),
                        processing_fee=Decimal("0"), total_repayable=Decimal("100"),
                        repayment_type=RepaymentType.MONTHLY, repayment_period=1,
                        installment_amount=Decimal("100"), calculation_method="flat",
                        calculation_breakdown={}, cdas_collection_enabled=False,
                        cdas_collection_plan={}, preferred_payment_day=1,
                        amount_paid=Decimal("40"), balance=Decimal("60"),
                        status=LoanStatus.ACTIVE, risk_level=RiskLevel.LOW,
                        is_overdue=True, automatic_renewal_enabled=False,
                    )
                    db.add(parent)
                    db.flush()
                    source = RepaymentInstallment(
                        loan_id=parent_id, installment_number=1,
                        due_date=date(2026, 11, 1),
                        principal_due=Decimal("100"), interest_due=Decimal("0"),
                        fee_due=Decimal("0"), total_due=Decimal("100"),
                        paid_amount=Decimal("40"), status=InstallmentStatus.OVERDUE,
                        is_superseded=False,
                    )
                    db.add(source)
                    db.flush()
                    source_id = source.id
                    # Real preview/plan/reconciliation must reject an
                    # improperly approved transfer before adding any child
                    # or ledger records, even in the isolated service body.
                    with pytest.raises(HTTPException) as wrong_amount:
                        isolated_posting()(
                            db, company_id=company, parent_id=parent_id,
                            installment_id=source_id,
                            approved_amount=Decimal("61"),
                            due_date=date(2026, 12, 1),
                            agreement_reference="SIGNED-AGREEMENT",
                            approval_reference="APPROVED-TRANSFER",
                            actor_user_id=maker, actor_role="owner",
                            as_of=date(2026, 11, 3),
                        )
                    assert wrong_amount.value.status_code == 409
                    db.expire_all()
                    assert db.query(TestLoan).count() == 1
                    assert db.query(LoanRolloverTransfer).count() == 0
                    assert db.get(RepaymentInstallment, source_id).paid_amount == Decimal("40")
                    if reject_accounting:
                        # The test-only failure is thrown after the real
                        # service has inserted the child, schedule, transfer
                        # and audit and called its final db.flush(), but
                        # before the production db.commit() line.
                        def reject_after_flush(**kwargs):
                            assert db.query(LoanRolloverTransfer).count() == 1
                            assert db.query(AuditLog).count() == 1
                            assert db.query(TestLoan).count() == 2
                            raise HTTPException(
                                status_code=409,
                                detail="Simulated accounting reconciliation failure",
                            )

                        with pytest.raises(HTTPException, match="Simulated accounting"):
                            with db.begin_nested():
                                isolated_posting(reconciliation=reject_after_flush)(
                                    db, company_id=company, parent_id=parent_id,
                                    installment_id=source_id,
                                    approved_amount=Decimal("60"),
                                    due_date=date(2026, 12, 1),
                                    agreement_reference="SIGNED-AGREEMENT",
                                    approval_reference="APPROVED-TRANSFER",
                                    actor_user_id=maker, actor_role="owner",
                                    as_of=date(2026, 11, 3),
                                )
                        db.expire_all()
                        persisted_parent = db.get(TestLoan, parent_id)
                        persisted_source = db.get(RepaymentInstallment, source_id)
                        assert persisted_parent.balance == Decimal("60")
                        assert persisted_parent.status == LoanStatus.ACTIVE
                        assert persisted_parent.is_overdue is True
                        assert "linked_rollover_out" not in persisted_parent.calculation_breakdown
                        assert persisted_source.paid_amount == Decimal("40")
                        assert persisted_source.is_superseded is False
                        assert db.query(TestLoan).count() == 1
                        assert db.query(RepaymentInstallment).count() == 1
                        assert db.query(LoanRolloverTransfer).count() == 0
                        assert db.query(AuditLog).count() == 0
                        return
                    result = isolated_posting()(
                        db, company_id=company, parent_id=parent_id,
                        installment_id=source_id, approved_amount=Decimal("60"),
                        due_date=date(2026, 12, 1),
                        agreement_reference="SIGNED-AGREEMENT",
                        approval_reference="APPROVED-TRANSFER",
                        actor_user_id=maker, actor_role="owner",
                        as_of=date(2026, 11, 3),
                    )
                    assert result["cash_disbursement"] == "0.00"
                    assert result["transferred_amount"] == "60"
                    child_id = __import__("uuid").UUID(result["child_loan_id"])
                    db.expire_all()
                    saved_parent = db.get(TestLoan, parent_id)
                    child = db.get(TestLoan, child_id)
                    saved_source = db.get(RepaymentInstallment, source_id)
                    assert saved_parent.balance == Decimal("0")
                    assert saved_parent.status == LoanStatus.COMPLETED
                    assert saved_parent.is_overdue is False
                    assert child.balance == Decimal("60")
                    assert child.parent_loan_id == parent_id
                    assert child.principal_amount == Decimal("60")
                    assert child.status == LoanStatus.ACTIVE
                    assert saved_source.paid_amount == Decimal("40")
                    assert saved_source.status == InstallmentStatus.OVERDUE
                    assert saved_source.is_superseded is True
                    child_rows = db.query(RepaymentInstallment).filter(
                        RepaymentInstallment.loan_id == child_id).all()
                    assert len(child_rows) == 1
                    assert child_rows[0].principal_due == Decimal("60")
                    assert child_rows[0].paid_amount == Decimal("0")
                    transfer = db.query(LoanRolloverTransfer).one()
                    assert transfer.parent_loan_id == parent_id
                    assert transfer.child_loan_id == child_id
                    assert transfer.transfer_amount == Decimal("60")
                    assert db.query(AuditLog).count() == 1
                    assert db.query(TestLoan).count() == 2
                    assert saved_parent.balance + child.balance == Decimal("60")
                    assert saved_parent.calculation_breakdown[
                        "linked_rollover_out"]["original"]["loan_is_overdue"] is True
                    with pytest.raises(HTTPException) as blocked:
                        posting.post_final_rollover(
                            db, company_id=company, parent_id=parent_id,
                            installment_id=source_id, approved_amount=Decimal("60"),
                            due_date=date(2026, 12, 1),
                            agreement_reference="SIGNED-AGREEMENT",
                            approval_reference="APPROVED-TRANSFER",
                            actor_user_id=maker, actor_role="owner",
                            as_of=date(2026, 11, 3),
                        )
                    assert blocked.value.status_code == 503
            finally:
                outer.rollback()
    finally:
        engine.dispose()
