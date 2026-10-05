from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class PlatformCdasSubscription(Base):
    """Platform-approved commercial access to CDAS for one lending company."""

    __tablename__ = "platform_cdas_subscriptions"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_platform_cdas_subscription_company"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="pending", index=True)
    currency = Column(String(3), nullable=False, default="LSL")
    pricing = Column(JSONB, nullable=False, default=dict)
    credit_limit = Column(Numeric(15, 2), nullable=True)
    warning_threshold = Column(Numeric(15, 2), nullable=True)
    auto_suspend_on_limit = Column(Boolean, nullable=False, default=True)
    billing_due_days = Column(Integer, nullable=False, default=14)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    suspended_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    company = relationship("LoanCompany")


class PlatformCdasCredentialProfile(Base):
    """Company-specific CDAS credentials held only at platform scope."""

    __tablename__ = "platform_cdas_credential_profiles"
    __table_args__ = (
        UniqueConstraint("company_id", "environment", name="uq_platform_cdas_profile_company_environment"),
        UniqueConstraint("environment", "username", name="uq_platform_cdas_profile_environment_username"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    environment = Column(String(20), nullable=False, index=True)
    base_url = Column(String(500), nullable=False)
    username = Column(String(200), nullable=False)
    item_code = Column(String(100), nullable=True)
    encrypted_password = Column(Text, nullable=False)
    timeout_seconds = Column(Numeric(8, 2), nullable=False, default=20)
    last_test_status = Column(String(60), nullable=True)
    last_tested_at = Column(DateTime, nullable=True)
    configured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("LoanCompany")
    configured_by = relationship("User", foreign_keys=[configured_by_user_id])


class PlatformCdasTransaction(Base):
    """One metered CDAS business operation; provider session/login traffic is never billed."""

    __tablename__ = "platform_cdas_transactions"
    __table_args__ = (
        UniqueConstraint("billing_key", name="uq_platform_cdas_transaction_billing_key"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("platform_cdas_subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True)
    environment = Column(String(20), nullable=False, index=True)
    operation_type = Column(String(80), nullable=False, index=True)
    billing_key = Column(String(180), nullable=False, unique=True, index=True)
    transaction_reference = Column(String(100), nullable=False, unique=True, index=True)
    unit_price = Column(Numeric(15, 2), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    status = Column(String(30), nullable=False, default="accrued", index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source_reference = Column(String(180), nullable=True, index=True)
    accrued_at = Column(DateTime, nullable=False)
    settled_at = Column(DateTime, nullable=True)
    waived_at = Column(DateTime, nullable=True)
    waiver_reason = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    subscription = relationship("PlatformCdasSubscription")
    actor = relationship("User", foreign_keys=[actor_user_id])



class PlatformCdasInvoice(Base):
    """Monthly PAYG invoice snapshot for one lending company's CDAS usage."""

    __tablename__ = "platform_cdas_invoices"
    __table_args__ = (
        UniqueConstraint("company_id", "period_start", "period_end", name="uq_platform_cdas_invoice_period"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("platform_cdas_subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True)
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

    subscription = relationship("PlatformCdasSubscription")
