from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class OnlineRepaymentMandate(Base):
    __tablename__ = "online_repayment_mandates"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    gateway_mandate_id = Column(String(80), nullable=True, unique=True, index=True)
    provider = Column(String(30), nullable=False, default="mpesa", index=True)
    status = Column(String(30), nullable=False, default="processing", index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    frequency = Column(String(30), nullable=False, default="monthly")
    next_debit_date = Column(Date, nullable=True, index=True)
    expiry_date = Column(Date, nullable=True)
    max_debits = Column(Integer, nullable=True)
    debits_completed = Column(Integer, nullable=False, default=0)
    consent_reference = Column(String(160), nullable=False)
    consented_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)


class BorrowerReminderPreference(Base):
    __tablename__ = "borrower_reminder_preferences"
    __table_args__ = (UniqueConstraint("company_id", "borrower_id", name="uq_borrower_reminder_company"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    in_app_enabled = Column(Boolean, nullable=False, default=True)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    email_enabled = Column(Boolean, nullable=False, default=False)
    whatsapp_enabled = Column(Boolean, nullable=False, default=False)
    days_before_due = Column(Integer, nullable=False, default=3)
    remind_on_due_date = Column(Boolean, nullable=False, default=True)
    overdue_interval_days = Column(Integer, nullable=False, default=3)
    payment_link_enabled = Column(Boolean, nullable=False, default=True)
    timezone = Column(String(80), nullable=False, default="Africa/Maseru")


class RepaymentReminder(Base):
    __tablename__ = "repayment_reminders"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    installment_id = Column(UUID(as_uuid=True), ForeignKey("repayment_installments.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(30), nullable=False, index=True)
    reminder_type = Column(String(40), nullable=False, index=True)
    scheduled_for = Column(DateTime, nullable=False, index=True)
    status = Column(String(40), nullable=False, default="pending", index=True)
    deduplication_key = Column(String(255), nullable=False, unique=True, index=True)
    destination_masked = Column(String(120), nullable=True)
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)


class LoanRestructureRequest(Base):
    __tablename__ = "loan_restructure_requests"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="requested", index=True)
    requested_term_months = Column(Integer, nullable=False)
    approved_rate_percent = Column(Numeric(8, 3), nullable=True)
    payment_holiday_days = Column(Integer, nullable=False, default=0)
    reason = Column(Text, nullable=False)
    borrower_accepted = Column(Boolean, nullable=False, default=True)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    agreement_reference = Column(String(160), nullable=True, unique=True)
    original_snapshot = Column(JSONB, nullable=False, default=dict)
    preview = Column(JSONB, nullable=False, default=dict)
    rejection_reason = Column(Text, nullable=True)


class AccountingExport(Base):
    __tablename__ = "accounting_exports"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    format = Column(String(20), nullable=False, default="json")
    destination = Column(String(60), nullable=False, default="manual")
    status = Column(String(30), nullable=False, default="ready", index=True)
    entry_count = Column(Integer, nullable=False, default=0)
    total_debit = Column(Numeric(18, 2), nullable=False, default=0)
    total_credit = Column(Numeric(18, 2), nullable=False, default=0)
    payload = Column(JSONB, nullable=False, default=dict)
    generated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime, nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)


__all__ = [
    "OnlineRepaymentMandate", "BorrowerReminderPreference", "RepaymentReminder",
    "LoanRestructureRequest", "AccountingExport",
]
