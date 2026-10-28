"""Durable accounting evidence for a parent-to-child receivable transfer.

Not a cash transaction. No endpoint writes this record until migrations,
accounting controls and PostgreSQL integration tests have been approved.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database.base import Base


class LoanRolloverTransfer(Base):
    __tablename__ = "loan_rollover_transfers"
    __table_args__ = (
        UniqueConstraint("company_id", "transfer_reference", name="uq_rollover_company_transfer_ref"),
        UniqueConstraint("parent_loan_id", name="uq_rollover_once_per_parent"),
        UniqueConstraint("child_loan_id", name="uq_rollover_once_per_child"),
        CheckConstraint("transfer_amount > 0", name="ck_rollover_positive_amount"),
        CheckConstraint("principal_component >= 0 AND interest_component >= 0 AND fee_component >= 0", name="ck_rollover_nonnegative_components"),
        CheckConstraint("transfer_amount = principal_component + interest_component + fee_component", name="ck_rollover_component_sum"),
        CheckConstraint("parent_loan_id <> child_loan_id", name="ck_rollover_distinct_loans"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    parent_loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False)
    child_loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False)
    source_installment_id = Column(UUID(as_uuid=True), ForeignKey("repayment_installments.id", ondelete="RESTRICT"), nullable=False)
    transfer_reference = Column(String(160), nullable=False)
    agreement_reference = Column(String(180), nullable=False)
    approval_reference = Column(String(180), nullable=False)
    principal_component = Column(Numeric(15, 2), nullable=False)
    interest_component = Column(Numeric(15, 2), nullable=False)
    fee_component = Column(Numeric(15, 2), nullable=False)
    transfer_amount = Column(Numeric(15, 2), nullable=False)
    status = Column(String(24), nullable=False, default="posted")
    posted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    evidence = Column(JSONB, nullable=False, default=dict)
