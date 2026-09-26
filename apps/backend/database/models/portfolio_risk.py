from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class PortfolioRiskSnapshot(Base):
    """Daily loan-level risk state used for transparent portfolio trend analysis."""

    __tablename__ = "portfolio_risk_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "snapshot_date",
            "loan_id",
            name="uq_portfolio_risk_snapshot_company_date_loan",
        ),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    employer_group_id = Column(UUID(as_uuid=True), ForeignKey("employer_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("loan_products.id", ondelete="SET NULL"), nullable=True, index=True)

    snapshot_date = Column(Date, nullable=False, index=True)
    origination_month = Column(Date, nullable=True, index=True)
    days_past_due = Column(Integer, nullable=False, default=0, index=True)
    delinquency_bucket = Column(String(30), nullable=False, default="current", index=True)
    outstanding_balance = Column(Numeric(15, 2), nullable=False, default=0)
    overdue_amount = Column(Numeric(15, 2), nullable=False, default=0)
    principal_amount = Column(Numeric(15, 2), nullable=False, default=0)
    installment_amount = Column(Numeric(15, 2), nullable=False, default=0)

    loan_status = Column(String(30), nullable=False, index=True)
    origination_channel = Column(String(30), nullable=False, default="unknown", index=True)
    collection_channel = Column(String(40), nullable=False, default="direct", index=True)
    product_label = Column(String(180), nullable=False, default="Unmapped product")
    employer_label = Column(String(220), nullable=False, default="No employer group")
    branch_label = Column(String(180), nullable=False, default="Unassigned branch")

    is_top_up = Column(Boolean, nullable=False, default=False, index=True)
    first_payment_default = Column(Boolean, nullable=False, default=False, index=True)
    is_written_off = Column(Boolean, nullable=False, default=False, index=True)
    cdas_collection_enabled = Column(Boolean, nullable=False, default=False, index=True)
    generated_at = Column(DateTime, nullable=False)
    evidence_snapshot = Column(JSONB, nullable=False, default=dict)

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    loan = relationship("ClientCompanyLoan")
    borrower = relationship("Borrower")
    employer_group = relationship("EmployerGroup")
    product = relationship("LoanProduct")


class PortfolioRiskRun(Base):
    """Audit record for each portfolio risk snapshot generation run."""

    __tablename__ = "portfolio_risk_runs"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "snapshot_date",
            "branch_scope_key",
            name="uq_portfolio_risk_run_company_date_scope",
        ),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_scope_key = Column(String(40), nullable=False, default="ALL")
    snapshot_date = Column(Date, nullable=False, index=True)
    run_reference = Column(String(100), nullable=False, unique=True, index=True)
    loan_count = Column(Integer, nullable=False, default=0)
    active_exposure = Column(Numeric(15, 2), nullable=False, default=0)
    par_30_amount = Column(Numeric(15, 2), nullable=False, default=0)
    summary = Column(JSONB, nullable=False, default=dict)
    generated_at = Column(DateTime, nullable=False)
    triggered_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    triggered_by = relationship("User", foreign_keys=[triggered_by_user_id])
