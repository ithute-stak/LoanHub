from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class CompanyOperatingRecord(Base):
    """Tenant-scoped operational record used by cross-functional company modules.

    Loan, payment, accounting, treasury, HR, collection, compliance and reporting
    ledgers remain authoritative in their existing tables. This record stores only
    workflow metadata for operating areas that do not already have a specialised
    LoanHub model (CRM, collateral, complaints, legal, campaigns, procurement,
    audits, budgets, targets, integrations and similar work queues).
    """

    __tablename__ = "company_operating_records"
    __table_args__ = (
        UniqueConstraint("company_id", "reference", name="uq_company_operating_record_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(60), nullable=False, index=True)
    record_type = Column(String(80), nullable=False, index=True)
    reference = Column(String(100), nullable=False, index=True)
    title = Column(String(240), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(40), nullable=False, default="open", index=True)
    priority = Column(String(30), nullable=False, default="normal", index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    counterparty_name = Column(String(240), nullable=True, index=True)
    amount = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="LSL")
    due_at = Column(DateTime, nullable=True, index=True)
    data = Column(JSONB, nullable=False, default=dict)
    tags = Column(JSONB, nullable=False, default=list)
    is_archived = Column(Boolean, nullable=False, default=False, index=True)


class CompanyAPIKey(Base):
    __tablename__ = "company_api_keys"
    __table_args__ = (
        UniqueConstraint("key_prefix", name="uq_company_api_key_prefix"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    key_prefix = Column(String(32), nullable=False, index=True)
    key_hash = Column(String(64), nullable=False)
    scopes = Column(JSONB, nullable=False, default=list)
    allowed_ips = Column(JSONB, nullable=False, default=list)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True, index=True)


class CompanyWebhookEndpoint(Base):
    __tablename__ = "company_webhook_endpoints"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    endpoint_url = Column(String(500), nullable=False)
    secret_hash = Column(String(64), nullable=False)
    secret_prefix = Column(String(24), nullable=False)
    encrypted_secret = Column(Text, nullable=True)
    encryption_nonce = Column(String(80), nullable=True)
    encryption_version = Column(String(30), nullable=True)
    event_types = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    failure_count = Column(Integer, nullable=False, default=0)
    last_delivery_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
