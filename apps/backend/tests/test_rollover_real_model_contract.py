"""Real LoanHub ORM mapping checks for the disabled linked rollover operation.

Unlike the temporary probe tables, these assertions interrogate production
SQLAlchemy models and compile their actual lock statements for PostgreSQL.
This is not an end-to-end financial transaction integration test.
"""
from sqlalchemy import inspect, select
from sqlalchemy.dialects import postgresql

from database.models.client_loan_company import ClientCompanyLoan
from database.models.repayment import RepaymentInstallment, PaymentAllocation


def test_rollover_parent_lock_compiles_to_postgresql_for_update():
    stmt = select(ClientCompanyLoan).where(
        ClientCompanyLoan.id == "00000000-0000-0000-0000-000000000001"
    ).with_for_update()
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    assert "client_company_loan" in sql


def test_real_models_preserve_original_allocations_and_linkage():
    loans = inspect(ClientCompanyLoan).columns
    installments = inspect(RepaymentInstallment).columns
    allocations = inspect(PaymentAllocation).columns
    assert loans["parent_loan_id"].nullable
    assert loans["balance"].type.scale == 2
    assert loans["total_repayable"].type.scale == 2
    assert installments["paid_amount"].type.scale == 2
    assert "is_superseded" in installments
    assert "payment_id" in allocations and "installment_id" in allocations
    assert "principal_paid" not in allocations
    assert "interest_paid" not in allocations
    assert "fee_paid" not in allocations


def test_actual_loan_parent_link_not_uniquely_constrained():
    # The current production loan schema permits multiple child loans
    # (e.g. top-ups); rollover idempotency therefore needs a dedicated
    # durable transfer uniqueness constraint, not just an application query.
    parent = ClientCompanyLoan.__table__.c.parent_loan_id
    assert not parent.unique
    assert not any(
        set(column.name for column in constraint.columns) == {"parent_loan_id"}
        for constraint in ClientCompanyLoan.__table__.constraints
        if hasattr(constraint, "columns")
    )
