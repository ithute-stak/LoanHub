from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class PredictiveIntelligenceRun(Base):
    """Auditable daily/on-demand forecast run for an existing loan portfolio."""

    __tablename__ = "predictive_intelligence_runs"
    __table_args__ = (
        UniqueConstraint("company_id", "as_of_date", "branch_scope_key", name="uq_predictive_run_company_date_scope"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_scope_key = Column(String(40), nullable=False, default="ALL")
    as_of_date = Column(Date, nullable=False, index=True)
    source_snapshot_date = Column(Date, nullable=False, index=True)
    previous_snapshot_date = Column(Date, nullable=True, index=True)
    run_reference = Column(String(100), nullable=False, unique=True, index=True)
    run_type = Column(String(40), nullable=False, default="on_demand", index=True)
    status = Column(String(30), nullable=False, default="completed", index=True)
    model_version = Column(String(80), nullable=False, default="transparent-rules-v1")
    lookback_days = Column(Integer, nullable=False, default=90)
    loan_count = Column(Integer, nullable=False, default=0)
    stable_count = Column(Integer, nullable=False, default=0)
    watch_count = Column(Integer, nullable=False, default=0)
    elevated_count = Column(Integer, nullable=False, default=0)
    high_count = Column(Integer, nullable=False, default=0)
    critical_count = Column(Integer, nullable=False, default=0)
    projected_par30_entry_count = Column(Integer, nullable=False, default=0)
    observed_collection_rate = Column(Numeric(8, 4), nullable=False, default=0)
    summary = Column(JSONB, nullable=False, default=dict)
    triggered_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime, nullable=False)


class PredictiveLoanSignal(Base):
    """Transparent early-warning signal for an already-originated loan."""

    __tablename__ = "predictive_loan_signals"
    __table_args__ = (
        UniqueConstraint("run_id", "loan_id", name="uq_predictive_signal_run_loan"),
    )

    run_id = Column(UUID(as_uuid=True), ForeignKey("predictive_intelligence_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    folio_number = Column(String(40), nullable=False, index=True)
    loan_reference = Column(String(80), nullable=True, index=True)
    risk_score = Column(Numeric(6, 2), nullable=False, default=0, index=True)
    risk_band = Column(String(30), nullable=False, default="stable", index=True)
    current_dpd = Column(Integer, nullable=False, default=0)
    previous_dpd = Column(Integer, nullable=True)
    dpd_change = Column(Integer, nullable=True)
    current_bucket = Column(String(30), nullable=False)
    previous_bucket = Column(String(30), nullable=True)
    first_payment_default = Column(Boolean, nullable=False, default=False)
    projected_par30_entry = Column(Boolean, nullable=False, default=False, index=True)
    stress_bucket_30d = Column(String(30), nullable=False)
    outstanding_balance = Column(Numeric(15, 2), nullable=False, default=0)
    rationale = Column(JSONB, nullable=False, default=list)
    recommended_action = Column(Text, nullable=False)
    evidence = Column(JSONB, nullable=False, default=dict)


class PredictiveCashflowForecast(Base):
    """Contractual and evidence-adjusted collection outlook for a forecast horizon."""

    __tablename__ = "predictive_cashflow_forecasts"
    __table_args__ = (
        UniqueConstraint("run_id", "horizon_days", name="uq_predictive_cashflow_run_horizon"),
    )

    run_id = Column(UUID(as_uuid=True), ForeignKey("predictive_intelligence_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    horizon_days = Column(Integer, nullable=False, index=True)
    period_end = Column(Date, nullable=False)
    contractual_due = Column(Numeric(15, 2), nullable=False, default=0)
    expected_collection = Column(Numeric(15, 2), nullable=False, default=0)
    observed_collection_rate = Column(Numeric(8, 4), nullable=False, default=0)
    due_installment_count = Column(Integer, nullable=False, default=0)
    history_installment_count = Column(Integer, nullable=False, default=0)
    confidence_band = Column(String(20), nullable=False, default="low")
    method = Column(String(60), nullable=False, default="contractual_no_history")
    evidence = Column(JSONB, nullable=False, default=dict)
