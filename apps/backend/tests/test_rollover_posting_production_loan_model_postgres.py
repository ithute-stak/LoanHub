"""Production-loan-mapped posting body with real PostgreSQL persistence.

The live 503 protection is deliberately untouched. This test-only compilation
removes only that first guard. All financial planning, accounting, transfer,
audit, loan, and repayment mappings run as written in the application; only
loan-reference generation is substituted. The disposable schema retains real
foreign-key constraints with abbreviated external reference tables; this is
still not full migration-backed, end-to-end production certification.
"""
import ast
import inspect
import os
import textwrap
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Enum as SAEnum, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

import database.models  # noqa: F401 - complete SQLAlchemy mapper registration
from database.models.audit_log import AuditLog
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.enums import CompanyStatus, InstallmentStatus, LoanStatus, RepaymentType, RiskLevel
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.repayment import RepaymentInstallment
from services import final_installment_rollover_posting as posting


def isolated_real_model_posting():
    tree = ast.parse(textwrap.dedent(inspect.getsource(posting.post_final_rollover)))
    fn = tree.body[0]
    guard = fn.body[0]
    assert isinstance(guard, ast.Raise)
    assert any(k.arg == "status_code" and isinstance(k.value, ast.Constant)
               and k.value.value == 503 for k in guard.exc.keywords)
    fn.body.pop(0)
    ast.fix_missing_locations(tree)
    namespace = vars(posting).copy()
    # This test specifically exercises the real ClientCompanyLoan mapping.
    # No payment classification, planning or accounting checks are stubbed.
    namespace["generate_loan_reference"] = lambda _db, _company: "REAL-POSTED-CHILD"
    exec(compile(tree, inspect.getfile(posting.post_final_rollover), "exec"), namespace)
    return namespace["post_final_rollover"]


@pytest.mark.parametrize("case", [
    "success", "accounting_failure", "wrong_company", "wrong_amount",
    "cdas_enabled", "already_transferred", "not_partially_paid",
    "expired_due_date", "invalid_agreement",
    "mixed_missing_evidence", "mixed_invalid_evidence", "mixed_valid_evidence",
])
def test_posting_body_real_client_company_loan_mapping(case):
    url = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL integration URL not configured")
    engine = create_engine(url)
    schema = "rollover_full_loan_" + uuid4().hex[:12]
    company_id, borrower_id, maker_id = uuid4(), uuid4(), uuid4()
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                conn.execute(text("CREATE TABLE employer_groups (id uuid PRIMARY KEY, code text, name text)"))
                conn.execute(text(
                    "CREATE TABLE borrowers (id uuid PRIMARY KEY, "
                    "employer_group_id uuid, employer_name text)"
                ))
                conn.execute(text("CREATE TABLE users (id uuid PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE company_branches (id uuid PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE loan_renewal_cycles (id uuid PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE loan_requests (id uuid PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE loan_offers (id uuid PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE direct_loan_applications (id uuid PRIMARY KEY)"))
                # The actual production columns/constraints and typed enums
                # are used for every model participating in the posting body.
                models = (
                    LoanCompany, ClientCompanyLoan,
                    RepaymentInstallment, LoanRolloverTransfer, AuditLog,
                )
                for model in models:
                    for column in model.__table__.columns:
                        if isinstance(column.type, SAEnum):
                            column.type.create(bind=conn, checkfirst=True)
                    # Keep the real production FK constraints active;
                    # minimal reference tables above satisfy external edges.
                    conn.execute(CreateTable(model.__table__))

                with Session(bind=conn, expire_on_commit=False) as db:
                    company = LoanCompany(
                        id=company_id, name="Batlokoa Financial Services",
                        phone="000000000", status=CompanyStatus.APPROVED,
                        is_active=True,
                    )
                    db.add(company)
                    db.flush()
                    db.execute(text(
                        "INSERT INTO borrowers (id, employer_group_id, employer_name) "
                        "VALUES (:id, NULL, :name)"
                    ), {"id": borrower_id, "name": "Sample employer"})
                    db.execute(text("INSERT INTO users (id) VALUES (:id)"), {"id": maker_id})
                    parent = ClientCompanyLoan(
                        company_id=company_id, borrower_id=borrower_id,
                        loan_reference="REAL-POSTED-PARENT",
                        origination_channel="direct", is_top_up=False,
                        principal_amount=Decimal("100"),
                        interest_rate=Decimal("0"),
                        processing_fee=Decimal("0"),
                        total_repayable=Decimal("100"),
                        repayment_type=RepaymentType.MONTHLY,
                        repayment_period=1,
                        installment_amount=Decimal("100"),
                        calculation_method="micro_loan",
                        calculation_breakdown={},
                        cdas_collection_enabled=False, cdas_collection_plan={},
                        preferred_payment_day=20,
                        amount_paid=Decimal("40"),
                        balance=Decimal("60"),
                        status=LoanStatus.ACTIVE,
                        risk_level=RiskLevel.LOW,
                        is_overdue=True,
                        automatic_renewal_enabled=False,
                    )
                    db.add(parent)
                    db.flush()
                    assert parent.folio_number == "BFS-Force-00001"
                    original_parent_id = parent.id
                    original_folio = parent.folio_number
                    source = RepaymentInstallment(
                        loan_id=original_parent_id,
                        installment_number=1,
                        due_date=date(2026, 11, 1),
                        principal_due=Decimal("100"),
                        interest_due=Decimal("0"),
                        fee_due=Decimal("0"),
                        total_due=Decimal("100"),
                        paid_amount=Decimal("40"),
                        status=InstallmentStatus.OVERDUE,
                        is_superseded=False,
                    )
                    db.add(source)
                    db.flush()
                    source_id = source.id

                    fn = isolated_real_model_posting()
                    if case == "mixed_valid_evidence":
                        source.principal_due = Decimal("70")
                        source.interest_due = Decimal("30")
                        db.flush()
                    if case not in ("success", "accounting_failure", "mixed_valid_evidence"):
                        # All denial scenarios use production ClientCompanyLoan,
                        # RepaymentInstallment, real preview and real plan checks.
                        arguments = dict(
                            company_id=company_id,
                            parent_id=original_parent_id,
                            installment_id=source_id,
                            approved_amount=Decimal("60"),
                            due_date=date(2026, 12, 20),
                            agreement_reference="REAL-SIGNED-AGREEMENT",
                            approval_reference="REAL-CREDIT-APPROVAL",
                            actor_user_id=maker_id,
                            actor_role="company_owner",
                            as_of=date(2026, 11, 3),
                        )
                        if case == "wrong_company":
                            arguments["company_id"] = uuid4()
                        elif case == "wrong_amount":
                            arguments["approved_amount"] = Decimal("61")
                        elif case == "cdas_enabled":
                            parent.cdas_collection_enabled = True
                        elif case == "already_transferred":
                            parent.calculation_breakdown = {
                                "linked_rollover_out": {"child_loan_id": str(uuid4())}
                            }
                        elif case == "not_partially_paid":
                            source.paid_amount = Decimal("0")
                        elif case == "expired_due_date":
                            arguments["due_date"] = date(2026, 11, 3)
                        elif case == "invalid_agreement":
                            arguments["agreement_reference"] = "bad"
                        elif case in ("mixed_missing_evidence", "mixed_invalid_evidence"):
                            source.principal_due = Decimal("70")
                            source.interest_due = Decimal("30")
                            if case == "mixed_invalid_evidence":
                                arguments["component_evidence"] = {
                                    "source_reference": "PAYMENT-LEDGER-VALIDATION",
                                    "verified_by": "INDEPENDENT-REVIEWER",
                                    "principal_paid": "40",
                                    "interest_paid": "40",
                                    "fee_paid": "0",
                                }
                        db.flush()
                        db.expire_all()
                        initial_parent = db.get(ClientCompanyLoan, original_parent_id)
                        initial_row = db.get(RepaymentInstallment, source_id)
                        initial_balance = initial_parent.balance
                        initial_breakdown = initial_parent.calculation_breakdown
                        initial_paid = initial_row.paid_amount
                        initial_cdas = initial_parent.cdas_collection_enabled
                        with pytest.raises(HTTPException) as denied:
                            fn(db, **arguments)
                        assert denied.value.status_code in (404, 409, 422)
                        db.expire_all()
                        checked_parent = db.get(ClientCompanyLoan, original_parent_id)
                        checked_row = db.get(RepaymentInstallment, source_id)
                        assert checked_parent.balance == initial_balance
                        assert checked_parent.calculation_breakdown == initial_breakdown
                        assert checked_parent.cdas_collection_enabled == initial_cdas
                        assert checked_parent.status == LoanStatus.ACTIVE
                        assert checked_row.paid_amount == initial_paid
                        assert checked_row.is_superseded is False
                        assert db.query(ClientCompanyLoan).count() == 1
                        assert db.query(RepaymentInstallment).count() == 1
                        assert db.query(LoanRolloverTransfer).count() == 0
                        assert db.query(AuditLog).count() == 0
                        assert not db.new and not db.dirty and not db.deleted
                        return
                    if case == "accounting_failure":
                        def reject_after_flush(**kwargs):
                            assert db.query(ClientCompanyLoan).count() == 2
                            assert db.query(LoanRolloverTransfer).count() == 1
                            assert db.query(AuditLog).count() == 1
                            raise HTTPException(
                                status_code=409,
                                detail="Simulated production-mapped accounting failure",
                            )
                        fn.__globals__["reconcile_rollover_accounting"] = reject_after_flush
                        with pytest.raises(HTTPException, match="Simulated production-mapped"):
                            with db.begin_nested():
                                fn(
                                    db, company_id=company_id,
                                    parent_id=original_parent_id,
                                    installment_id=source_id,
                                    approved_amount=Decimal("60"),
                                    due_date=date(2026, 12, 20),
                                    agreement_reference="REAL-SIGNED-AGREEMENT",
                                    approval_reference="REAL-CREDIT-APPROVAL",
                                    actor_user_id=maker_id,
                                    actor_role="company_owner",
                                    as_of=date(2026, 11, 3),
                                )
                        db.expire_all()
                        p = db.get(ClientCompanyLoan, original_parent_id)
                        row = db.get(RepaymentInstallment, source_id)
                        assert p.balance == Decimal("60")
                        assert p.status == LoanStatus.ACTIVE
                        assert p.is_overdue is True
                        assert p.folio_number == original_folio
                        assert "linked_rollover_out" not in p.calculation_breakdown
                        assert row.paid_amount == Decimal("40")
                        assert row.is_superseded is False
                        assert db.query(ClientCompanyLoan).count() == 1
                        assert db.query(RepaymentInstallment).count() == 1
                        assert db.query(LoanRolloverTransfer).count() == 0
                        assert db.query(AuditLog).count() == 0
                        return

                    component_evidence = (
                        {
                            "source_reference": "INDEPENDENT-ALLOCATION-REF",
                            "verified_by": "FINANCE-REVIEWER",
                            "principal_paid": "30",
                            "interest_paid": "10",
                            "fee_paid": "0",
                        }
                        if case == "mixed_valid_evidence" else None
                    )
                    result = fn(
                        db, company_id=company_id, parent_id=original_parent_id,
                        installment_id=source_id,
                        approved_amount=Decimal("60"),
                        due_date=date(2026, 12, 20),
                        agreement_reference="REAL-SIGNED-AGREEMENT",
                        approval_reference="REAL-CREDIT-APPROVAL",
                        actor_user_id=maker_id,
                        actor_role="company_owner",
                        as_of=date(2026, 11, 3),
                        component_evidence=component_evidence,
                    )
                    assert Decimal(result["transferred_amount"]) == Decimal("60")
                    assert Decimal(result["cash_disbursement"]) == Decimal("0")
                    child_id = UUID(result["child_loan_id"])
                    db.expire_all()
                    saved_parent = db.get(ClientCompanyLoan, original_parent_id)
                    child = db.get(ClientCompanyLoan, child_id)
                    source = db.get(RepaymentInstallment, source_id)
                    assert saved_parent.balance == Decimal("0")
                    assert saved_parent.status == LoanStatus.COMPLETED
                    assert saved_parent.is_overdue is False
                    assert source.is_superseded is True
                    assert source.paid_amount == Decimal("40")
                    assert child.parent_loan_id == original_parent_id
                    assert child.balance == Decimal("60")
                    assert child.principal_amount == (
                        Decimal("40") if case == "mixed_valid_evidence"
                        else Decimal("60")
                    )
                    assert child.status == LoanStatus.ACTIVE
                    assert child.folio_number == "BFS-Force-00002"
                    assert child.folio_number != saved_parent.folio_number
                    child_schedule = db.query(RepaymentInstallment).filter(
                        RepaymentInstallment.loan_id == child_id,
                    ).one()
                    assert child_schedule.principal_due == (
                        Decimal("40") if case == "mixed_valid_evidence"
                        else Decimal("60")
                    )
                    assert child_schedule.interest_due == (
                        Decimal("20") if case == "mixed_valid_evidence"
                        else Decimal("0")
                    )
                    assert child_schedule.paid_amount == Decimal("0")
                    transfer = db.query(LoanRolloverTransfer).one()
                    assert transfer.parent_loan_id == original_parent_id
                    assert transfer.child_loan_id == child_id
                    assert transfer.transfer_amount == Decimal("60")
                    assert transfer.principal_component == child_schedule.principal_due
                    assert transfer.interest_component == child_schedule.interest_due
                    if case == "mixed_valid_evidence":
                        assert transfer.evidence["allocation_evidence"] == component_evidence
                    assert db.query(AuditLog).count() == 1
                    assert saved_parent.balance + child.balance == Decimal("60")

                    # A linked child must never reference a nonexistent
                    # parent even after the service successfully commits.
                    with pytest.raises(IntegrityError):
                        with db.begin_nested():
                            db.execute(text(
                                "UPDATE client_company_loan SET parent_loan_id = :missing "
                                "WHERE id = :child"
                            ), {"missing": uuid4(), "child": child_id})
                    db.expire_all()
                    assert db.get(ClientCompanyLoan, child_id).parent_loan_id == original_parent_id
                    fk_count = db.execute(text(
                        "SELECT COUNT(*) FROM pg_constraint c "
                        "JOIN pg_class t ON t.oid = c.conrelid "
                        "JOIN pg_namespace n ON n.oid = t.relnamespace "
                        "WHERE n.nspname = :schema AND c.contype = 'f' "
                        "AND t.relname IN "
                        "('client_company_loan', 'repayment_installments', "
                        "'loan_rollover_transfers', 'audit_logs')"
                    ), {"schema": schema}).scalar_one()
                    assert fk_count >= 10
                    with pytest.raises(HTTPException) as disabled:
                        posting.post_final_rollover(
                            db, company_id=company_id, parent_id=original_parent_id,
                            installment_id=source_id,
                            approved_amount=Decimal("60"),
                            due_date=date(2026, 12, 20),
                            agreement_reference="REAL-SIGNED-AGREEMENT",
                            approval_reference="REAL-CREDIT-APPROVAL",
                            actor_user_id=maker_id, actor_role="company_owner",
                            as_of=date(2026, 11, 3),
                        )
                    assert disabled.value.status_code == 503
            finally:
                outer.rollback()
    finally:
        engine.dispose()
