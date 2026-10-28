"""Append-only compensating records for a previously posted loan rollover."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database.base import Base


class LoanRolloverCompensation(Base):
    __tablename__ = "loan_rollover_compensations"
    __table_args__ = (
        UniqueConstraint("transfer_id", name="uq_rollover_compensation_once"),
        UniqueConstraint("company_id", "reference", name="uq_rollover_compensation_reference"),
        CheckConstraint("amount > 0", name="ck_rollover_compensation_positive"),
        CheckConstraint("principal_component >= 0 AND interest_component >= 0 AND fee_component >= 0", name="ck_rollover_compensation_components_nonnegative"),
        CheckConstraint("amount = principal_component + interest_component + fee_component", name="ck_rollover_compensation_balances"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("loan_rollover_transfers.id", ondelete="RESTRICT"), nullable=False)
    reference = Column(String(160), nullable=False)
    approval_reference = Column(String(180), nullable=False)
    reason = Column(String(500), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    principal_component = Column(Numeric(15, 2), nullable=False)
    interest_component = Column(Numeric(15, 2), nullable=False)
    fee_component = Column(Numeric(15, 2), nullable=False)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    evidence = Column(JSONB, nullable=False, default=dict)
