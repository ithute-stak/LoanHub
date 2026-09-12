from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class UserMFAEnrollment(Base):
    __tablename__ = "user_mfa_enrollments"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_mfa_user"),)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_secret = Column(Text, nullable=False)
    encryption_nonce = Column(String(80), nullable=False)
    encryption_version = Column(String(30), nullable=False)
    recovery_code_hashes = Column(JSONB, nullable=False, default=list)
    is_enabled = Column(Boolean, nullable=False, default=False, index=True)
    confirmed_at = Column(DateTime, nullable=True)
    disabled_at = Column(DateTime, nullable=True)
    last_accepted_counter = Column(Integer, nullable=True)


class UserSecurityState(Base):
    __tablename__ = "user_security_states"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_security_state_user"),)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True, index=True)
    last_failed_login_at = Column(DateTime, nullable=True)
    last_successful_login_at = Column(DateTime, nullable=True)
    session_version = Column(Integer, nullable=False, default=1)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_approval_company_idempotency"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    action_type = Column(String(80), nullable=False, index=True)
    resource_type = Column(String(80), nullable=False, index=True)
    resource_id = Column(String(120), nullable=True, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="pending", index=True)
    idempotency_key = Column(String(180), nullable=False)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_reason = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)


class PaymentAdjustment(Base):
    __tablename__ = "payment_adjustments"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_payment_adjustment_company_idempotency"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="RESTRICT"), nullable=False, index=True)
    approval_request_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    adjustment_type = Column(String(30), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    reason = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="pending_approval", index=True)
    idempotency_key = Column(String(180), nullable=False)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    provider_reference = Column(String(180), nullable=True, index=True)
    failure_reason = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class WebhookOutboxEvent(Base):
    __tablename__ = "webhook_outbox_events"
    __table_args__ = (
        UniqueConstraint("endpoint_id", "idempotency_key", name="uq_webhook_outbox_endpoint_idempotency"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("company_webhook_endpoints.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    aggregate_type = Column(String(80), nullable=True)
    aggregate_id = Column(String(120), nullable=True, index=True)
    idempotency_key = Column(String(180), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=False, index=True)
    last_attempt_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    response_status = Column(Integer, nullable=True)


class WebhookDeliveryAttempt(Base):
    __tablename__ = "webhook_delivery_attempts"

    outbox_event_id = Column(UUID(as_uuid=True), ForeignKey("webhook_outbox_events.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    request_timestamp = Column(DateTime, nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body_hash = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (
        UniqueConstraint("scope_key", "period_start", "period_end", name="uq_accounting_scope_period"),
    )

    scope_key = Column(String(80), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    locked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    locked_at = Column(DateTime, nullable=True)
    closed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    close_note = Column(Text, nullable=True)


class BankStatementLine(Base):
    __tablename__ = "bank_statement_lines"
    __table_args__ = (
        UniqueConstraint("company_id", "source_fingerprint", name="uq_bank_line_company_fingerprint"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    account_reference = Column(String(180), nullable=True, index=True)
    transaction_date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    reference = Column(String(180), nullable=True, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    source_fingerprint = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False, default="unmatched", index=True)
    matched_payment_id = Column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    matched_at = Column(DateTime, nullable=True)


class LoanGuarantor(Base):
    __tablename__ = "loan_guarantors"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    guarantor_borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(240), nullable=False)
    national_id = Column(String(80), nullable=False, index=True)
    phone = Column(String(30), nullable=False)
    relationship_to_borrower = Column(String(100), nullable=False)
    guaranteed_amount = Column(Numeric(15, 2), nullable=False)
    consent_obtained = Column(Boolean, nullable=False, default=False)
    verification_status = Column(String(30), nullable=False, default="pending", index=True)
    verified_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime, nullable=True)


class LoanCollateral(Base):
    __tablename__ = "loan_collateral"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    collateral_type = Column(String(80), nullable=False, index=True)
    description = Column(Text, nullable=False)
    ownership_reference = Column(String(180), nullable=True, index=True)
    estimated_value = Column(Numeric(15, 2), nullable=False)
    forced_sale_value = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="LSL")
    valuation_date = Column(Date, nullable=True)
    status = Column(String(30), nullable=False, default="proposed", index=True)
    released_at = Column(DateTime, nullable=True)


class ComplaintCase(Base):
    __tablename__ = "complaint_cases"
    __table_args__ = (UniqueConstraint("reference", name="uq_complaint_reference"),)

    reference = Column(String(80), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String(80), nullable=False, index=True)
    subject = Column(String(240), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), nullable=False, default="normal", index=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    resolution = Column(Text, nullable=True)
    due_at = Column(DateTime, nullable=True, index=True)
    submitted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class DataRightsRequest(Base):
    __tablename__ = "data_rights_requests"
    __table_args__ = (UniqueConstraint("reference", name="uq_data_rights_reference"),)

    reference = Column(String(80), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    request_type = Column(String(40), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="received", index=True)
    identity_verified_at = Column(DateTime, nullable=True)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    due_at = Column(DateTime, nullable=False, index=True)
    decision = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
