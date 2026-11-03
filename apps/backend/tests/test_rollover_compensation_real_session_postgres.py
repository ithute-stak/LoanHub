"""Execute the actual compensation service body against real PostgreSQL rows.

Test-only AST extraction removes the first unconditional 503 statement in an
isolated function object; the production function and HTTP routes remain gated.
The transfer, compensation and repayment schedule use real application mapped
ORM classes. The minimal loan/payment models isolate unrelated schema setup.
The mapped maker request, checker decision and active company-role identity
are exercised with PostgreSQL. The loan/payment fixtures remain simplified;
this is not complete production activation certification.
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
from sqlalchemy import Boolean, Column, Enum, Numeric, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Session, declarative_base

from database.models.enums import InstallmentStatus, LoanStatus, UserRole
from database.models.repayment import RepaymentInstallment
from database.models.user import User
from database.models.company_staff import CompanyStaff
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_compensation import LoanRolloverCompensation
from database.models.loan_rollover_reversal_request import LoanRolloverReversalRequest
from database.models.loan_rollover_reversal_approval import LoanRolloverReversalApproval
from services.rollover_reversal_approval import require_rollover_reversal_approval
from services import rollover_reversal_approval as approval_service
from services import rollover_compensation_posting as posting


TestBase = declarative_base()


class TestLoan(TestBase):
    __tablename__ = "client_company_loan"
    id = Column(UUID(as_uuid=True), primary_key=True)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    parent_loan_id = Column(UUID(as_uuid=True), nullable=True)
    balance = Column(Numeric(15, 2), nullable=False)
    amount_paid = Column(Numeric(15, 2), nullable=False)
    status = Column(Enum(LoanStatus), nullable=False)
    is_overdue = Column(Boolean, nullable=False)
    calculation_breakdown = Column(JSONB, nullable=False)


class TestPayment(TestBase):
    __tablename__ = "payment_transactions"
    id = Column(UUID(as_uuid=True), primary_key=True)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    loan_id = Column(UUID(as_uuid=True), nullable=False)


class TestAllocation(TestBase):
    __tablename__ = "payment_allocations"
    payment_id = Column(UUID(as_uuid=True), primary_key=True)
    installment_id = Column(UUID(as_uuid=True), primary_key=True)


def isolated_compensation(*, reconciliation=None):
    tree = ast.parse(textwrap.dedent(inspect.getsource(posting.post_rollover_compensation)))
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
        "PaymentTransaction": TestPayment,
        "PaymentAllocation": TestAllocation,
        "require_rollover_reversal_approval": require_rollover_reversal_approval,
    })
    if reconciliation is not None:
        namespace["reconcile_rollover_accounting"] = reconciliation
    exec(compile(tree, inspect.getfile(posting.post_rollover_compensation), "exec"), namespace)
    return namespace["post_rollover_compensation"]


@pytest.mark.parametrize("reject_accounting", [False, True])
def test_real_session_compensation_restores_persisted_parent_child_and_history(reject_accounting):
    url = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL integration URL not configured")
    engine = create_engine(url)
    schema = "rollover_service_comp_" + uuid4().hex[:12]
    company, maker, checker, parent_id, child_id = [uuid4() for _ in range(5)]
    original = {
        "balance": "60", "installment_total_due": "100",
        "installment_paid_amount": "40", "installment_principal_due": "100",
        "installment_interest_due": "0", "installment_fee_due": "0",
        "installment_status": "overdue", "loan_status": "active",
        "loan_is_overdue": True,
    }
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                conn.execute(text('CREATE TABLE loan_companies (id uuid PRIMARY KEY)'))
                conn.execute(text('CREATE TABLE company_branches (id uuid PRIMARY KEY)'))
                User.__table__.create(bind=conn)
                CompanyStaff.__table__.create(bind=conn)
                conn.execute(text('CREATE TABLE loan_renewal_cycles (id uuid PRIMARY KEY)'))
                TestLoan.__table__.create(bind=conn)
                TestPayment.__table__.create(bind=conn)
                TestAllocation.__table__.create(bind=conn)
                RepaymentInstallment.__table__.create(bind=conn)
                LoanRolloverTransfer.__table__.create(bind=conn)
                LoanRolloverCompensation.__table__.create(bind=conn)
                LoanRolloverReversalRequest.__table__.create(bind=conn)
                LoanRolloverReversalApproval.__table__.create(bind=conn)
                conn.execute(text('INSERT INTO loan_companies VALUES (:id)'), {"id": company})
                with Session(bind=conn) as identities:
                    identities.add_all([
                        User(id=maker, phone="maker-" + maker.hex[:12],
                             password_hash="test-not-an-account",
                             role=UserRole.COMPANY_OWNER,
                             is_active=True, is_verified=True),
                        User(id=checker, phone="checker-" + checker.hex[:12],
                             password_hash="test-not-an-account",
                             role=UserRole.FINANCE_OFFICER,
                             is_active=True, is_verified=True),
                    ])
                    identities.flush()
                    identities.add(CompanyStaff(
                        user_id=checker, company_id=company,
                        role=UserRole.FINANCE_OFFICER, is_active=True,
                        is_primary=True,
                    ))
                    identities.flush()
                    # Bound connection remains in the isolated outer transaction.


                with Session(bind=conn, expire_on_commit=False) as db:
                    parent = TestLoan(
                        id=parent_id, company_id=company, parent_loan_id=None,
                        balance=Decimal("0"), amount_paid=Decimal("40"),
                        status=LoanStatus.COMPLETED, is_overdue=False,
                        calculation_breakdown={"linked_rollover_out": {
                            "child_loan_id": str(child_id), "amount": "60",
                            "original": original,
                        }},
                    )
                    child = TestLoan(
                        id=child_id, company_id=company, parent_loan_id=parent_id,
                        balance=Decimal("60"), amount_paid=Decimal("0"),
                        status=LoanStatus.ACTIVE, is_overdue=False,
                        calculation_breakdown={},
                    )
                    db.add_all((parent, child))
                    db.flush()
                    source = RepaymentInstallment(
                        loan_id=parent_id, installment_number=1,
                        due_date=date(2026, 11, 1),
                        principal_due=Decimal("100"), interest_due=Decimal("0"),
                        fee_due=Decimal("0"), total_due=Decimal("100"),
                        paid_amount=Decimal("40"), status=InstallmentStatus.OVERDUE,
                        is_superseded=True,
                    )
                    child_row = RepaymentInstallment(
                        loan_id=child_id, installment_number=1,
                        due_date=date(2026, 12, 1),
                        principal_due=Decimal("60"), interest_due=Decimal("0"),
                        fee_due=Decimal("0"), total_due=Decimal("60"),
                        paid_amount=Decimal("0"), status=InstallmentStatus.PENDING,
                        is_superseded=False,
                    )
                    db.add_all((source, child_row))
                    db.flush()
                    transfer = LoanRolloverTransfer(
                        company_id=company, parent_loan_id=parent_id,
                        child_loan_id=child_id, source_installment_id=source.id,
                        transfer_reference="SESSION-TRANSFER",
                        agreement_reference="SIGNED-TEST",
                        approval_reference="ORIGINAL-APPROVAL",
                        principal_component=Decimal("60"),
                        interest_component=Decimal("0"), fee_component=Decimal("0"),
                        transfer_amount=Decimal("60"), posted_by_user_id=maker,
                        status="posted", evidence={"original": original},
                    )
                    db.add(transfer)
                    db.flush()
                    transfer_id, source_id, child_row_id = transfer.id, source.id, child_row.id
                    # Use the real service authorization query against actual
                    # immutable maker-request and checker-decision ORM rows.
                    request = LoanRolloverReversalRequest(
                        company_id=company, transfer_id=transfer.id,
                        maker_user_id=maker, request_reference="SESSION-REQUEST",
                        reason="Request the restoration of mistaken rollover",
                    )
                    db.add(request)
                    db.flush()
                    decision = LoanRolloverReversalApproval(
                        company_id=company, transfer_id=transfer.id,
                        maker_user_id=maker, checker_user_id=checker,
                        approval_reference="CHECKER-APPROVED",
                        decision="approved",
                        reason="Independent financial review is completed",
                        evidence={"maker_request_id": str(request.id)},
                    )
                    db.add(decision)
                    db.flush()

                    # Verify real active/verified company staff eligibility.
                    from services.rollover_checker_identity import verify_rollover_checker_identity
                    assert verify_rollover_checker_identity(
                        db, company_id=company,
                        maker_user_id=maker, checker_user_id=checker,
                    ) == checker
                    membership = db.query(CompanyStaff).filter(
                        CompanyStaff.user_id == checker,
                        CompanyStaff.company_id == company,
                    ).one()
                    membership.is_active = False
                    db.flush()
                    with pytest.raises(HTTPException) as inactive_checker:
                        require_rollover_reversal_approval(
                            db, company_id=company, transfer_id=transfer.id,
                            maker_user_id=maker, checker_user_id=checker,
                            approval_reference="CHECKER-APPROVED",
                        )
                    assert inactive_checker.value.status_code == 409
                    membership.is_active = True
                    db.flush()
                    # All of these use the real mapped User and CompanyStaff
                    # records and the real independent checker verifier. Every
                    # denial must occur before a compensation journal exists.
                    checker_user = db.get(User, checker)
                    unrelated_company = uuid4()
                    db.execute(text("INSERT INTO loan_companies (id) VALUES (:id)"), {"id": unrelated_company})
                    denial_cases = (
                        ("unverified", lambda: setattr(checker_user, "is_verified", False),
                         lambda: setattr(checker_user, "is_verified", True)),
                        ("disabled_user", lambda: setattr(checker_user, "is_active", False),
                         lambda: setattr(checker_user, "is_active", True)),
                        ("unauthorized_role", lambda: setattr(membership, "role", UserRole.COLLECTIONS_OFFICER),
                         lambda: setattr(membership, "role", UserRole.FINANCE_OFFICER)),
                        ("wrong_company", lambda: setattr(membership, "company_id", unrelated_company),
                         lambda: setattr(membership, "company_id", company)),
                    )
                    for case_name, deny, restore in denial_cases:
                        deny()
                        db.flush()
                        with pytest.raises(HTTPException) as denied:
                            require_rollover_reversal_approval(
                                db, company_id=company, transfer_id=transfer.id,
                                maker_user_id=maker, checker_user_id=checker,
                                approval_reference="CHECKER-APPROVED",
                            )
                        assert denied.value.status_code == 409, case_name
                        assert db.query(LoanRolloverCompensation).count() == 0
                        assert db.get(TestLoan, parent_id).balance == Decimal("0")
                        assert db.get(TestLoan, child_id).balance == Decimal("60")
                        restore()
                        db.flush()
                    with pytest.raises(HTTPException) as same_user:
                        require_rollover_reversal_approval(
                            db, company_id=company, transfer_id=transfer.id,
                            maker_user_id=maker, checker_user_id=maker,
                            approval_reference="CHECKER-APPROVED",
                        )
                    assert same_user.value.status_code == 409
                    assert require_rollover_reversal_approval(
                        db, company_id=company, transfer_id=transfer.id,
                        maker_user_id=maker, checker_user_id=checker,
                        approval_reference="CHECKER-APPROVED",
                    ) is decision
                    with pytest.raises(HTTPException) as wrong_checker_approval:
                        require_rollover_reversal_approval(
                            db, company_id=company, transfer_id=transfer.id,
                            maker_user_id=maker, checker_user_id=checker,
                            approval_reference="WRONG-CHECKER-REFERENCE",
                        )
                    assert wrong_checker_approval.value.status_code == 409

                    # Calls actual service SQLAlchemy query/locking/mutation/flush/
                    # accounting/commit logic, not a mocked query/result iterator.
                    if reject_accounting:
                        # Force a failure after the actual compensation service
                        # has mutated the parent/child/schedules and flushed
                        # a mapped compensation row, but before db.commit().
                        def reject_after_flush(**kwargs):
                            assert db.query(LoanRolloverCompensation).count() == 1
                            assert db.get(TestLoan, parent_id).balance == Decimal("60")
                            assert db.get(TestLoan, child_id).balance == Decimal("0")
                            raise HTTPException(
                                status_code=409,
                                detail="Simulated compensation accounting failure",
                            )

                        with pytest.raises(HTTPException, match="Simulated compensation"):
                            with db.begin_nested():
                                isolated_compensation(reconciliation=reject_after_flush)(
                                    db, company_id=company, transfer_id=transfer_id,
                                    actor_user_id=maker, independent_approver_id=checker,
                                    reference="SESSION-UNDO-FAILED",
                                    approval_reference="CHECKER-APPROVED",
                                    reason="Rollback regression after compensation flush",
                                )
                        db.expire_all()
                        parent_after = db.get(TestLoan, parent_id)
                        child_after = db.get(TestLoan, child_id)
                        source_after = db.get(RepaymentInstallment, source_id)
                        child_row_after = db.get(RepaymentInstallment, child_row_id)
                        assert parent_after.balance == Decimal("0")
                        assert parent_after.status == LoanStatus.COMPLETED
                        assert parent_after.is_overdue is False
                        assert "linked_rollover_compensated" not in parent_after.calculation_breakdown
                        assert child_after.balance == Decimal("60")
                        assert child_after.status == LoanStatus.ACTIVE
                        assert source_after.is_superseded is True
                        assert source_after.paid_amount == Decimal("40")
                        assert source_after.status == InstallmentStatus.OVERDUE
                        assert child_row_after.is_superseded is False
                        assert db.query(LoanRolloverCompensation).count() == 0
                        assert db.query(LoanRolloverTransfer).count() == 1
                        assert parent_after.balance + child_after.balance == Decimal("60")
                        return
                    result = isolated_compensation()(
                        db, company_id=company, transfer_id=transfer_id,
                        actor_user_id=maker, independent_approver_id=checker,
                        reference="SESSION-UNDO",
                        approval_reference="CHECKER-APPROVED",
                        reason="Real PostgreSQL transaction certification regression",
                    )
                    assert result["parent_balance"] == "60"
                    assert result["child_balance"] == "0"
                    db.expire_all()
                    restored_parent = db.get(TestLoan, parent_id)
                    restored_child = db.get(TestLoan, child_id)
                    restored_source = db.get(RepaymentInstallment, source_id)
                    cancelled_row = db.get(RepaymentInstallment, child_row_id)
                    assert restored_parent.balance == Decimal("60")
                    assert restored_parent.status == LoanStatus.ACTIVE
                    assert restored_parent.is_overdue is True
                    assert restored_child.balance == Decimal("0")
                    assert restored_child.status == LoanStatus.CANCELLED
                    assert restored_source.paid_amount == Decimal("40")
                    assert restored_source.status == InstallmentStatus.OVERDUE
                    assert restored_source.is_superseded is False
                    assert cancelled_row.is_superseded is True
                    assert db.query(LoanRolloverTransfer).count() == 1
                    assert db.query(LoanRolloverCompensation).count() == 1
                    assert (restored_parent.balance + restored_child.balance
                            == Decimal("60"))
                    with pytest.raises(HTTPException) as replay:
                        isolated_compensation()(
                            db, company_id=company, transfer_id=transfer_id,
                            actor_user_id=maker, independent_approver_id=checker,
                            reference="SESSION-UNDO-AGAIN",
                            approval_reference="CHECKER-APPROVED-AGAIN",
                            reason="Replay must be rejected",
                        )
                    assert replay.value.status_code == 409
                    assert db.query(LoanRolloverCompensation).count() == 1
                    # The unmodified production service always rejects callers.
                    with pytest.raises(HTTPException) as live:
                        posting.post_rollover_compensation(
                            db, company_id=company, transfer_id=transfer_id,
                            actor_user_id=maker, independent_approver_id=checker,
                            reference="LIVE", approval_reference="LIVE",
                            reason="Live gate check",
                        )
                    assert live.value.status_code == 503
            finally:
                outer.rollback()
    finally:
        engine.dispose()
