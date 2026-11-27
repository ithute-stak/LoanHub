"""Persistent evidence review model; no posting authority or public write route."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database.base import Base


class PrincipalXLedgerReview(Base):
    __tablename__ = "principal_x_ledger_reviews"
    __table_args__ = (
        UniqueConstraint("company_id", "review_reference", name="uq_px_review_reference"),
        CheckConstraint("maker_user_id <> checker_user_id", name="ck_px_review_independent"),
        CheckConstraint("net_collected >= 0", name="ck_px_review_nonnegative"),
        CheckConstraint("source_revision ~ '^[0-9a-f]{64}$'", name="ck_px_review_revision"),
        CheckConstraint("evidence_digest ~ '^[0-9a-f]{64}$'", name="ck_px_review_digest"),
        CheckConstraint("jsonb_typeof(attestations) = 'array' AND jsonb_array_length(attestations) = 8", name="ck_px_review_sources"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False, index=True)
    maker_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    checker_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    review_reference = Column(String(180), nullable=False)
    source_revision = Column(String(64), nullable=False)
    evidence_digest = Column(String(64), nullable=False)
    net_collected = Column(Numeric(15, 2), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=False)
    attestations = Column(JSONB, nullable=False)
