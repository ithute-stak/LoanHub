"""Durable, fail-closed tracking for individually requested CDAS affordability checks.

Not a payroll deduction operation and never a bulk worker queue.
"""
from sqlalchemy import Column, ForeignKey, String, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class CdasAffordabilityAttempt(Base):
    __tablename__ = "cdas_affordability_attempts"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_cdas_aff_attempt_company_key"),
        CheckConstraint(
            "state IN ('reserved','unknown','identity_review','completed')",
            name="ck_cdas_aff_attempt_state",
        ),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key = Column(String(120), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    state = Column(String(24), nullable=False, default="reserved")
    assessment_record_id = Column(UUID(as_uuid=True), nullable=True)
