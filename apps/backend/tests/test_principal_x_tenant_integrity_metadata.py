"""Verify the composite foreign key prevents cross-company assignments.

The actual constraint requires an Alembic migration before enforcement.
"""
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from database.models import ClientCompanyLoan, LoanPaymentModelAssignmentRecord


def test_loan_parent_has_composite_unique_key():
    constraints = ClientCompanyLoan.__table__.constraints
    assert any(
        isinstance(c, UniqueConstraint)
        and {column.name for column in c.columns} == {"id", "company_id"}
        for c in constraints
    )


def test_assignment_has_composite_owner_foreign_key():
    constraints = LoanPaymentModelAssignmentRecord.__table__.constraints
    assert any(
        isinstance(c, ForeignKeyConstraint)
        and {element.parent.name for element in c.elements} == {"loan_id", "company_id"}
        and {element.column.name for element in c.elements} == {"id", "company_id"}
        and {element.column.table.name for element in c.elements} == {"client_company_loan"}
        for c in constraints
    )
