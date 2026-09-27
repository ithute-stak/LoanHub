from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class CreditLossProvisionPolicy(Base):
    __tablename__ = "credit_loss_provision_policies"
    __table_args__ = (
        UniqueConstraint("company_id", "name", "version", name="uq_credit_loss_policy_version"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(30), nullable=False, default="active", index=True)
    rates = Column(JSONB, nullable=False, default=dict)
    description = Column(Text, nullable=True)
    configured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)


class CreditLossProvisionRun(Base):
    __tablename__ = "credit_loss_provision_runs"
    __table_args__ = (
        UniqueConstraint("company_id", "as_of_date", "branch_scope_key", name="uq_credit_loss_run_scope_date"),
        UniqueConstraint("run_reference", name="uq_credit_loss_run_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_scope_key = Column(String(40), nullable=False, default="ALL", index=True)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("credit_loss_provision_policies.id", ondelete="RESTRICT"), nullable=False, index=True)
    run_reference = Column(String(100), nullable=False, index=True)
    as_of_date = Column(Date, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="draft", index=True)
    loan_count = Column(Integer, nullable=False, default=0)
    gross_exposure = Column(Numeric(18, 2), nullable=False, default=0)
    required_allowance = Column(Numeric(18, 2), nullable=False, default=0)
    prior_allowance = Column(Numeric(18, 2), nullable=False, default=0)
    allowance_movement = Column(Numeric(18, 2), nullable=False, default=0)
    stage_1_allowance = Column(Numeric(18, 2), nullable=False, default=0)
    stage_2_allowance = Column(Numeric(18, 2), nullable=False, default=0)
    stage_3_allowance = Column(Numeric(18, 2), nullable=False, default=0)
    management_overlay = Column(Numeric(18, 2), nullable=False, default=0)
    overlay_reason = Column(Text, nullable=True)
    summary = Column(JSONB, nullable=False, default=dict)
    generated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    locked_at = Column(DateTime, nullable=True)


class CreditLossProvisionLine(Base):
    __tablename__ = "credit_loss_provision_lines"
    __table_args__ = (
        UniqueConstraint("run_id", "loan_id", name="uq_credit_loss_line_run_loan"),
    )

    run_id = Column(UUID(as_uuid=True), ForeignKey("credit_loss_provision_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    folio_number = Column(String(40), nullable=False, index=True)
    stage = Column(Integer, nullable=False, index=True)
    days_past_due = Column(Integer, nullable=False, default=0)
    exposure = Column(Numeric(18, 2), nullable=False, default=0)
    provision_rate = Column(Numeric(8, 4), nullable=False, default=0)
    base_allowance = Column(Numeric(18, 2), nullable=False, default=0)
    overlay_amount = Column(Numeric(18, 2), nullable=False, default=0)
    required_allowance = Column(Numeric(18, 2), nullable=False, default=0)
    rationale = Column(JSONB, nullable=False, default=list)
    evidence = Column(JSONB, nullable=False, default=dict)
    write_off_candidate = Column(Boolean, nullable=False, default=False, index=True)
