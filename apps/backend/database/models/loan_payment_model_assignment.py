"""Persisted immutable payment-model choice per loan.

The separate table keeps existing calculator and historical loan columns
untouched. A unique loan_id ensures one assigned model per loan.
"""
from sqlalchemy import CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class LoanPaymentModelAssignmentRecord(Base):
    __tablename__ = "loan_payment_model_assignments"
    __table_args__ = (
        UniqueConstraint("loan_id", name="uq_loan_payment_model_assignment_loan"),
        ForeignKeyConstraint(
            ["loan_id", "company_id"],
            ["client_company_loan.id", "client_company_loan.company_id"],
            name="fk_loan_payment_model_assignment_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint("payment_model IN ('existing', 'principal_x')", name="ck_loan_payment_model_allowed"),
    )

    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_company_loan.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_model = Column(String(30), nullable=False)
