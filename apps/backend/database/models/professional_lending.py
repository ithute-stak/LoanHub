from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from database.base import Base

class DirectLoanApplication(Base):
    __tablename__ = "direct_loan_applications"
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("loan_products.id", ondelete="SET NULL"), nullable=True)
    application_reference = Column(String(60), nullable=False, unique=True, index=True)
    channel = Column(String(30), nullable=False, default="branch_walk_in")
    requested_amount = Column(Numeric(15,2), nullable=False)
    approved_amount = Column(Numeric(15,2), nullable=True)
    interest_rate = Column(Numeric(8,3), nullable=True)
    term_count = Column(Integer, nullable=False)
    repayment_type = Column(String(30), nullable=False, default="monthly")
    purpose = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft", index=True)
    affordability_snapshot = Column(JSONB, nullable=False, default=dict)
    credit_warning = Column(JSONB, nullable=False, default=dict)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    captured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    decision_notes = Column(Text, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejected_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, unique=True)
    preferred_payment_day = Column(Integer, nullable=True)
    first_payment_date = Column(Date, nullable=True)
    installment_due_dates = Column(JSONB, nullable=False, default=list)
    application_step = Column(Integer, nullable=False, default=1)
    kyc_profile_id = Column(UUID(as_uuid=True), ForeignKey("borrower_kyc_profiles.id", ondelete="SET NULL"), nullable=True)
    affordability_assessment_id = Column(UUID(as_uuid=True), ForeignKey("affordability_assessments.id", ondelete="SET NULL", use_alter=True), nullable=True)
    application_type = Column(String(30), nullable=False, default="new_loan", index=True)
    parent_loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    top_up_cash_requested = Column(Numeric(15, 2), nullable=True)
    top_up_settlement_amount = Column(Numeric(15, 2), nullable=True)
    top_up_cash_to_borrower = Column(Numeric(15, 2), nullable=True)
    top_up_eligibility_snapshot = Column(JSONB, nullable=False, default=dict)
    top_up_exception_requested = Column(Boolean, nullable=False, default=False)
    top_up_exception_reason = Column(Text, nullable=True)
    top_up_exception_approved = Column(Boolean, nullable=False, default=False)
    top_up_exception_approved_at = Column(DateTime, nullable=True)
    top_up_exception_approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

class CreditBlacklist(Base):
    __tablename__ = "credit_blacklist"
    __table_args__ = (UniqueConstraint("borrower_id", name="uq_credit_blacklist_borrower"),)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    source = Column(String(50), nullable=False, default="automatic_365_day_default")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    blacklisted_at = Column(DateTime, nullable=False)
    review_due_at = Column(DateTime, nullable=True)
    cleared_at = Column(DateTime, nullable=True)
    cleared_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

class Suggestion(Base):
    __tablename__ = "platform_suggestions"
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True)
    submitted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reference = Column(String(60), nullable=False, unique=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(80), nullable=False, default="feature_request")
    description = Column(Text, nullable=False)
    priority = Column(String(30), nullable=False, default="normal")
    status = Column(String(30), nullable=False, default="submitted", index=True)
    platform_response = Column(Text, nullable=True)

class OfferWallPost(Base):
    __tablename__ = "offer_wall_posts"
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("loan_products.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    summary = Column(Text, nullable=False)
    terms = Column(JSONB, nullable=False, default=dict)
    image_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), nullable=False, default="draft", index=True)
    published_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

class OfferWallInterest(Base):
    __tablename__ = "offer_wall_interests"
    __table_args__ = (UniqueConstraint("post_id","borrower_id", name="uq_offer_interest_borrower"),)
    post_id = Column(UUID(as_uuid=True), ForeignKey("offer_wall_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="interested")

class PaymentReceipt(Base):
    __tablename__ = "payment_receipts"
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True)
    receipt_number = Column(String(60), nullable=False, unique=True, index=True)
    balance_before = Column(Numeric(15,2), nullable=False, default=0)
    amount_received = Column(Numeric(15,2), nullable=False)
    principal_amount = Column(Numeric(15,2), nullable=False, default=0)
    interest_amount = Column(Numeric(15,2), nullable=False, default=0)
    fee_amount = Column(Numeric(15,2), nullable=False, default=0)
    penalty_amount = Column(Numeric(15,2), nullable=False, default=0)
    balance_after = Column(Numeric(15,2), nullable=False, default=0)
    payment_method = Column(String(30), nullable=False)
    provider_reference = Column(String(180), nullable=True)
    pdf_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="SET NULL"), nullable=True)
    verification_code = Column(String(80), nullable=False, unique=True)

class PrintAgent(Base):
    __tablename__ = "print_agents"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    secret_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_seen_at = Column(DateTime, nullable=True)

class PrintJob(Base):
    __tablename__ = "print_jobs"
    agent_id = Column(UUID(as_uuid=True), ForeignKey("print_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="RESTRICT"), nullable=False)
    printer_name = Column(String(200), nullable=True)
    copies = Column(Integer, nullable=False, default=1)
    status = Column(String(30), nullable=False, default="queued", index=True)
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
