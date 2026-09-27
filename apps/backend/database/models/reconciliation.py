from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class ReconciliationBatch(Base):
    """One auditable reconciliation source/period for a lending company."""

    __tablename__ = "reconciliation_batches"
    __table_args__ = (
        UniqueConstraint("company_id", "batch_reference", name="uq_reconciliation_batch_company_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_reference = Column(String(90), nullable=False, index=True)
    source_type = Column(String(40), nullable=False, index=True)
    source_reference = Column(String(180), nullable=True, index=True)
    account_reference = Column(String(180), nullable=True, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    currency = Column(String(3), nullable=False, default="LSL")
    status = Column(String(30), nullable=False, default="draft", index=True)

    imported_line_count = Column(Integer, nullable=False, default=0)
    matched_line_count = Column(Integer, nullable=False, default=0)
    exception_line_count = Column(Integer, nullable=False, default=0)
    duplicate_line_count = Column(Integer, nullable=False, default=0)
    missing_source_count = Column(Integer, nullable=False, default=0)

    imported_amount = Column(Numeric(15, 2), nullable=False, default=0)
    matched_amount = Column(Numeric(15, 2), nullable=False, default=0)
    shortage_amount = Column(Numeric(15, 2), nullable=False, default=0)
    excess_amount = Column(Numeric(15, 2), nullable=False, default=0)
    unmatched_amount = Column(Numeric(15, 2), nullable=False, default=0)

    imported_at = Column(DateTime, nullable=True)
    reconciled_at = Column(DateTime, nullable=True)
    reconciled_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    close_note = Column(Text, nullable=True)
    methodology_snapshot = Column(JSONB, nullable=False, default=dict)

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    lines = relationship("ReconciliationLine", back_populates="batch", cascade="all, delete-orphan")
    events = relationship("ReconciliationEvent", back_populates="batch", cascade="all, delete-orphan")
    reconciled_by = relationship("User", foreign_keys=[reconciled_by_user_id])
    closed_by = relationship("User", foreign_keys=[closed_by_user_id])


class ReconciliationLine(Base):
    """Source or system-side reconciliation row. Matching never mutates a payment."""

    __tablename__ = "reconciliation_lines"
    __table_args__ = (
        UniqueConstraint("batch_id", "source_line_key", name="uq_reconciliation_line_batch_source_key"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("reconciliation_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    source_kind = Column(String(30), nullable=False, default="external", index=True)
    source_line_key = Column(String(180), nullable=False)
    transaction_date = Column(Date, nullable=False, index=True)
    reference = Column(String(220), nullable=True, index=True)
    description = Column(String(700), nullable=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    direction = Column(String(12), nullable=False, default="credit", index=True)
    source_fingerprint = Column(String(64), nullable=False, index=True)

    status = Column(String(30), nullable=False, default="unmatched", index=True)
    match_method = Column(String(60), nullable=True, index=True)
    match_confidence = Column(Numeric(6, 3), nullable=True)
    matched_payment_id = Column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    folio_number = Column(String(40), nullable=True, index=True)
    expected_amount = Column(Numeric(15, 2), nullable=True)
    variance_amount = Column(Numeric(15, 2), nullable=False, default=0)

    exception_code = Column(String(80), nullable=True, index=True)
    exception_reason = Column(Text, nullable=True)
    candidate_snapshot = Column(JSONB, nullable=False, default=list)
    source_payload = Column(JSONB, nullable=False, default=dict)
    is_manual_match = Column(Boolean, nullable=False, default=False)
    matched_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    matched_at = Column(DateTime, nullable=True)
    resolved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)
    payment_adjustment_id = Column(UUID(as_uuid=True), ForeignKey("payment_adjustments.id", ondelete="SET NULL"), nullable=True, index=True)

    batch = relationship("ReconciliationBatch", back_populates="lines")
    payment = relationship("PaymentTransaction", foreign_keys=[matched_payment_id])
    loan = relationship("ClientCompanyLoan", foreign_keys=[matched_loan_id])
    borrower = relationship("Borrower", foreign_keys=[matched_borrower_id])
    matched_by = relationship("User", foreign_keys=[matched_by_user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])
    payment_adjustment = relationship("PaymentAdjustment", foreign_keys=[payment_adjustment_id])


class ReconciliationEvent(Base):
    """Append-only evidence trail for every reconciliation decision."""

    __tablename__ = "reconciliation_events"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("reconciliation_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    line_id = Column(UUID(as_uuid=True), ForeignKey("reconciliation_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)

    batch = relationship("ReconciliationBatch", back_populates="events")
    line = relationship("ReconciliationLine")
    actor = relationship("User", foreign_keys=[actor_user_id])
