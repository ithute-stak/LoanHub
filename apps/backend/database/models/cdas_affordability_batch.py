"""Persistent CDAS bulk job definitions (execution intentionally disabled)."""
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class CdasAffordabilityBatch(Base):
    __tablename__ = "cdas_affordability_batches"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_cdas_affordability_batch_idempotency"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(120), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="draft", index=True)
    total_count = Column(Integer, nullable=False)
    finished_count = Column(Integer, nullable=False, default=0)
    execution_enabled = Column(Boolean, nullable=False, default=False)


class CdasAffordabilityBatchItem(Base):
    __tablename__ = "cdas_affordability_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "borrower_id", name="uq_cdas_affordability_batch_borrower"),
        UniqueConstraint("batch_id", "employee_number", name="uq_cdas_affordability_batch_employee"),
    )
    batch_id = Column(UUID(as_uuid=True), ForeignKey("cdas_affordability_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False)
    employee_number = Column(String(100), nullable=False)
    proposed_monthly_installment = Column(Numeric(15, 2), nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    error_code = Column(String(80), nullable=True)
    assessment_record_id = Column(UUID(as_uuid=True), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
