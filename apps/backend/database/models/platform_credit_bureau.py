from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class PlatformCreditBureauConfiguration(Base):
    """Platform-owner controlled provider configuration for shared credit bureaus."""

    __tablename__ = "platform_credit_bureau_configurations"
    __table_args__ = (
        UniqueConstraint("provider", name="uq_platform_credit_bureau_provider"),
    )

    provider = Column(String(40), nullable=False, index=True)
    environment = Column(String(30), nullable=False, default="sandbox")
    is_enabled = Column(Boolean, nullable=False, default=False)
    configuration = Column(JSONB, nullable=False, default=dict)
    encrypted_credentials = Column(Text, nullable=True)
    last_test_status = Column(String(100), nullable=True)
    last_tested_at = Column(DateTime, nullable=True)
    configured_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    configured_by = relationship("User", foreign_keys=[configured_by_user_id])


class PlatformCreditBureauSubscription(Base):
    """A lending company's platform-approved right to consume bureau transactions."""

    __tablename__ = "platform_credit_bureau_subscriptions"
    __table_args__ = (
        UniqueConstraint("provider", "company_id", name="uq_credit_bureau_subscription_provider_company"),
    )

    provider = Column(String(40), nullable=False, default="experian", index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(30), nullable=False, default="pending", index=True)
    price_per_transaction = Column(Numeric(15, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="LSL")
    credit_limit = Column(Numeric(15, 2), nullable=True)
    warning_threshold = Column(Numeric(15, 2), nullable=True)
    auto_suspend_on_limit = Column(Boolean, nullable=False, default=True)
    billing_due_days = Column(Integer, nullable=False, default=14)
    requested_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_at = Column(DateTime, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    suspended_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    company = relationship("LoanCompany")


class PlatformCreditBureauTransaction(Base):
    """Immutable-style PAYG accrual created once for each successful fresh provider enquiry."""

    __tablename__ = "platform_credit_bureau_transactions"
    __table_args__ = (
        UniqueConstraint("enquiry_id", name="uq_credit_bureau_payg_enquiry"),
    )

    provider = Column(String(40), nullable=False, default="experian", index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("platform_credit_bureau_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    enquiry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credit_bureau_enquiries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_reference = Column(String(100), nullable=False, unique=True, index=True)
    unit_price = Column(Numeric(15, 2), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    status = Column(String(30), nullable=False, default="accrued", index=True)
    accrued_at = Column(DateTime, nullable=False)
    settled_at = Column(DateTime, nullable=True)
    waived_at = Column(DateTime, nullable=True)
    waiver_reason = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    subscription = relationship("PlatformCreditBureauSubscription")


class PlatformCreditBureauInvoice(Base):
    """Monthly PAYG statement/invoice snapshot for one lending company."""

    __tablename__ = "platform_credit_bureau_invoices"
    __table_args__ = (
        UniqueConstraint("company_id", "provider", "period_start", "period_end", name="uq_credit_bureau_invoice_period"),
    )

    provider = Column(String(40), nullable=False, default="experian", index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("platform_credit_bureau_subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True)
    invoice_number = Column(String(100), nullable=False, unique=True, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    transaction_count = Column(Integer, nullable=False, default=0)
    subtotal = Column(Numeric(18, 2), nullable=False, default=0)
    waived_amount = Column(Numeric(18, 2), nullable=False, default=0)
    amount_due = Column(Numeric(18, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="LSL")
    status = Column(String(30), nullable=False, default="issued", index=True)
    issued_at = Column(DateTime, nullable=False)
    due_at = Column(DateTime, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    snapshot = Column(JSONB, nullable=False, default=dict)

    subscription = relationship("PlatformCreditBureauSubscription")
