"""Immutable maker-initiated request for a rollover compensation review."""
from sqlalchemy import Column, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class LoanRolloverReversalRequest(Base):
    __tablename__ = "loan_rollover_reversal_requests"
    __table_args__ = (
        UniqueConstraint("transfer_id", name="uq_rollover_reversal_request_transfer"),
        UniqueConstraint("company_id", "request_reference", name="uq_rollover_reversal_request_reference"),
        CheckConstraint("length(trim(reason)) >= 12", name="ck_rollover_reversal_request_reason"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("loan_rollover_transfers.id", ondelete="RESTRICT"), nullable=False)
    maker_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    request_reference = Column(String(180), nullable=False)
    reason = Column(String(500), nullable=False)
    requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
