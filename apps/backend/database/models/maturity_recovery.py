from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class MaturityRenewalPolicy(Base):
    """Company-level rules for automatic balance renewal at contractual maturity.

    The policy is disabled by default. A company must opt in explicitly because
    capitalising an unpaid balance can change the cost of credit and must match
    the lender's signed agreement and applicable lending rules.
    """

    __tablename__ = "maturity_renewal_policies"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_maturity_renewal_policy_company"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=False, index=True)
    rollover_basis = Column(String(40), nullable=False, default="outstanding_balance")
    reuse_original_rate = Column(Boolean, nullable=False, default=True)
    renewal_rate_percent = Column(Numeric(8, 3), nullable=True)
    reuse_original_term = Column(Boolean, nullable=False, default=True)
    renewal_term_months = Column(Integer, nullable=True)
    include_processing_fee = Column(Boolean, nullable=False, default=False)
    grace_days = Column(Integer, nullable=False, default=0)
    max_cycles = Column(Integer, nullable=True)
    notify_borrower = Column(Boolean, nullable=False, default=True)
    configured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class LoanRenewalCycle(Base):
    """Immutable snapshot of one maturity renewal of an existing loan facility."""

    __tablename__ = "loan_renewal_cycles"
    __table_args__ = (
        UniqueConstraint("loan_id", "cycle_number", name="uq_loan_renewal_cycle_number"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    cycle_number = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="active", index=True)
    automatic = Column(Boolean, nullable=False, default=True)

    opening_balance = Column(Numeric(15, 2), nullable=False)
    rollover_basis = Column(String(40), nullable=False, default="outstanding_balance")
    rate_percent = Column(Numeric(8, 3), nullable=False, default=0)
    processing_fee = Column(Numeric(15, 2), nullable=False, default=0)
    term_months = Column(Integer, nullable=False)
    calculation_method = Column(String(40), nullable=False)
    installment_amount = Column(Numeric(15, 2), nullable=False)
    total_repayable = Column(Numeric(15, 2), nullable=False)
    started_on = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False)
    rolled_at = Column(DateTime, nullable=False)

    previous_terms_snapshot = Column(JSONB, nullable=False, default=dict)
    previous_schedule_snapshot = Column(JSONB, nullable=False, default=list)
    calculation_breakdown = Column(JSONB, nullable=False, default=dict)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    loan = relationship("ClientCompanyLoan", back_populates="renewal_cycles")
