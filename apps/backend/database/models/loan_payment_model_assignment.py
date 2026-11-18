"""Persisted immutable payment-model choice per loan.

The separate table keeps existing calculator and historical loan columns
untouched. A unique loan_id ensures one assigned model per loan.
"""
from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class LoanPaymentModelAssignmentRecord(Base):
    __tablename__ = "loan_payment_model_assignments"
    __table_args__ = (
        UniqueConstraint("loan_id", name="uq_loan_payment_model_assignment_loan"),
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
