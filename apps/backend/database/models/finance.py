from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import PaymentDirection, PaymentProvider

class BorrowerFeeConfiguration(Base):
    """Platform-controlled fee payable before a borrower request is submitted.

    ``company_id`` is optional so the platform owner can configure a global
    default and, when required by a commercial agreement, a company-specific
    override. Loan marketplace requests normally use the global configuration.
    """

    __tablename__ = "borrower_fee_configurations"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(160), nullable=False, default="Borrow request service fee")
    fee_type = Column(String(20), nullable=False, default="flat")
    flat_amount = Column(Numeric(15, 2), nullable=False, default=0)
    percentage = Column(Numeric(10, 6), nullable=False, default=0)
    minimum_amount = Column(Numeric(15, 2), nullable=True)
    maximum_amount = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="LSL")
    required_before_submission = Column(Boolean, nullable=False, default=True)
    refundable = Column(Boolean, nullable=False, default=False)
    allowed_providers = Column(JSONB, nullable=False, default=list)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    company = relationship("LoanCompany")

class TransactionChargeAgreement(Base):
    __tablename__ = "transaction_charge_agreements"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agreement_number = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(180), nullable=False, default="Platform transaction charge agreement")
    inbound_percentage = Column(Numeric(10, 6), nullable=False, default=0)
    outbound_percentage = Column(Numeric(10, 6), nullable=False, default=0)
    inbound_flat_fee = Column(Numeric(15, 2), nullable=False, default=0)
    outbound_flat_fee = Column(Numeric(15, 2), nullable=False, default=0)
    minimum_charge = Column(Numeric(15, 2), nullable=True)
    maximum_charge = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="LSL")
    settlement_frequency = Column(String(30), nullable=False, default="monthly")
    settlement_day = Column(Integer, nullable=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    status = Column(String(30), nullable=False, default="draft", index=True)
    terms = Column(Text, nullable=True)
    owner_accepted_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    company_accepted_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    owner_accepted_at = Column(DateTime, nullable=True)
    company_accepted_at = Column(DateTime, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    suspended_at = Column(DateTime, nullable=True)

    company = relationship("LoanCompany")

class PlatformChargeClaim(Base):
    __tablename__ = "platform_charge_claims"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agreement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transaction_charge_agreements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    claim_number = Column(String(80), nullable=False, unique=True, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    transaction_count = Column(Integer, nullable=False, default=0)
    gross_transaction_value = Column(Numeric(18, 2), nullable=False, default=0)
    amount = Column(Numeric(18, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="LSL")
    status = Column(String(30), nullable=False, default="draft", index=True)
    issued_at = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    disputed_at = Column(DateTime, nullable=True)
    issued_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payment_id = Column(
        UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True
    )
    notes = Column(Text, nullable=True)
    dispute_reason = Column(Text, nullable=True)

    agreement = relationship("TransactionChargeAgreement")
    payment = relationship("PaymentTransaction")

class TransactionChargeLedgerEntry(Base):
    __tablename__ = "transaction_charge_ledger_entries"
    __table_args__ = (UniqueConstraint("payment_id", name="uq_transaction_charge_payment"),)

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agreement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transaction_charge_agreements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    claim_id = Column(
        UUID(as_uuid=True),
        ForeignKey("platform_charge_claims.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction = Column(Enum(PaymentDirection), nullable=False, index=True)
    provider = Column(Enum(PaymentProvider), nullable=False, index=True)
    payment_purpose = Column(String(80), nullable=False, index=True)
    gross_amount = Column(Numeric(18, 2), nullable=False)
    percentage_rate = Column(Numeric(10, 6), nullable=False, default=0)
    flat_fee = Column(Numeric(15, 2), nullable=False, default=0)
    charge_amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    status = Column(String(30), nullable=False, default="accrued", index=True)
    accrued_at = Column(DateTime, nullable=False)
    claimed_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    waived_at = Column(DateTime, nullable=True)
    waiver_reason = Column(Text, nullable=True)

    agreement = relationship("TransactionChargeAgreement")
    payment = relationship("PaymentTransaction")
    claim = relationship("PlatformChargeClaim")

class PlatformStaffProfile(Base):
    __tablename__ = "platform_staff_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_platform_staff_user"),)

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_title = Column(String(160), nullable=False)
    department = Column(String(120), nullable=True)
    permissions = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_reviewed_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])

class CompanyAccountOpeningFeeConfiguration(Base):
    """Platform fee charged to a tenant when staff open a borrower account."""

    __tablename__ = "company_account_opening_fee_configurations"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(160), nullable=False, default="Assisted borrower account opening fee")
    fee_type = Column(String(20), nullable=False, default="flat")
    flat_amount = Column(Numeric(15, 2), nullable=False, default=0)
    percentage = Column(Numeric(10, 6), nullable=False, default=0)
    minimum_amount = Column(Numeric(15, 2), nullable=True)
    maximum_amount = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="LSL")
    required_before_activation = Column(Boolean, nullable=False, default=True)
    allowed_providers = Column(JSONB, nullable=False, default=list)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    company = relationship("LoanCompany")
