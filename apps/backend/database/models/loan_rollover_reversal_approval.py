"""Durable, transfer-specific maker/checker decision evidence.

No public mutation endpoint yet. A decision is immutable and cannot authorize
posting without separately validating identity, status and journal readiness.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database.base import Base


class LoanRolloverReversalApproval(Base):
    __tablename__ = "loan_rollover_reversal_approvals"
    __table_args__ = (
        UniqueConstraint("transfer_id", name="uq_rollover_reversal_approval_transfer"),
        UniqueConstraint("company_id", "approval_reference", name="uq_rollover_reversal_approval_ref"),
        CheckConstraint("maker_user_id <> checker_user_id", name="ck_rollover_reversal_independent"),
        CheckConstraint("decision IN ('approved', 'rejected')", name="ck_rollover_reversal_decision"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("loan_rollover_transfers.id", ondelete="RESTRICT"), nullable=False)
    maker_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    checker_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approval_reference = Column(String(180), nullable=False)
    decision = Column(String(16), nullable=False)
    reason = Column(String(500), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    evidence = Column(JSONB, nullable=False, default=dict)
