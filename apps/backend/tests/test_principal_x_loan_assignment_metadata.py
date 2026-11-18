"""Loan-level payment model assignment metadata safety tests."""
from database.base import Base
from database.models import LoanPaymentModelAssignmentRecord


def test_loan_assignment_registered_in_metadata():
    table = Base.metadata.tables["loan_payment_model_assignments"]
    assert table is LoanPaymentModelAssignmentRecord.__table__
    assert not table.c.loan_id.nullable
    assert not table.c.company_id.nullable
    assert not table.c.payment_model.nullable


def test_assignment_has_unique_loan_identity_and_tenant_foreign_keys():
    table = LoanPaymentModelAssignmentRecord.__table__
    unique_columns = [
        {column.name for column in constraint.columns}
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]
    assert {"loan_id"} in unique_columns
    assert {fk.column.table.name for fk in table.c.loan_id.foreign_keys} == {
        "client_company_loan"
    }
    assert {fk.column.table.name for fk in table.c.company_id.foreign_keys} == {
        "loan_companies"
    }
