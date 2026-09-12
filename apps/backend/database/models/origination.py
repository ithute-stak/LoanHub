from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
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


class OriginationPolicy(Base):
    """Versioned tenant rules used by KYC, duplicate checks and affordability."""

    __tablename__ = "origination_policies"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_origination_policy_company"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    currency = Column(String(3), nullable=False, default="LSL")
    is_active = Column(Boolean, nullable=False, default=True)

    allow_concurrent_active_loans = Column(Boolean, nullable=False, default=False)
    max_active_loans = Column(Integer, nullable=False, default=1)
    max_open_applications = Column(Integer, nullable=False, default=1)
    allow_top_up = Column(Boolean, nullable=False, default=True)
    top_up_min_paid_percent = Column(Numeric(8, 3), nullable=False, default=75)
    top_up_min_paid_installments = Column(Integer, nullable=False, default=0)
    top_up_owner_exception_enabled = Column(Boolean, nullable=False, default=True)
    top_up_require_positive_history = Column(Boolean, nullable=False, default=True)
    top_up_settle_existing_balance = Column(Boolean, nullable=False, default=True)
    cooling_off_days = Column(Integer, nullable=False, default=0)

    min_age = Column(Integer, nullable=False, default=18)
    max_age = Column(Integer, nullable=False, default=70)
    min_verified_net_income = Column(Numeric(15, 2), nullable=False, default=0)
    max_dti_percent = Column(Numeric(8, 3), nullable=False, default=40)
    max_installment_income_percent = Column(Numeric(8, 3), nullable=False, default=35)
    disposable_income_usage_percent = Column(Numeric(8, 3), nullable=False, default=70)
    min_disposable_after_installment = Column(Numeric(15, 2), nullable=False, default=0)
    living_expense_buffer = Column(Numeric(15, 2), nullable=False, default=0)
    dependant_allowance = Column(Numeric(15, 2), nullable=False, default=0)
    min_employment_months = Column(Integer, nullable=False, default=0)
    required_payslips = Column(Integer, nullable=False, default=1)
    required_bank_statement_months = Column(Integer, nullable=False, default=1)

    require_kyc_verified = Column(Boolean, nullable=False, default=True)
    require_signed_contract = Column(Boolean, nullable=False, default=True)
    allow_blacklisted = Column(Boolean, nullable=False, default=False)
    manager_override_enabled = Column(Boolean, nullable=False, default=True)
    configured_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    company = relationship("LoanCompany")
    configured_by = relationship("User", foreign_keys=[configured_by_user_id])


class BorrowerKYCProfile(Base):
    __tablename__ = "borrower_kyc_profiles"
    __table_args__ = (
        UniqueConstraint("borrower_id", name="uq_kyc_borrower"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(40), nullable=False, default="not_started", index=True)
    identity_verified = Column(Boolean, nullable=False, default=False)
    address_verified = Column(Boolean, nullable=False, default=False)
    phone_verified = Column(Boolean, nullable=False, default=False)
    sanctions_hit = Column(Boolean, nullable=False, default=False)
    politically_exposed = Column(Boolean, nullable=False, default=False)
    adverse_media_hit = Column(Boolean, nullable=False, default=False)
    fraud_flag = Column(Boolean, nullable=False, default=False)
    source_of_funds = Column(String(200), nullable=True)
    residence_status = Column(String(60), nullable=True)
    years_at_address = Column(Numeric(6, 2), nullable=True)
    dependants = Column(Integer, nullable=False, default=0)
    next_of_kin = Column(JSONB, nullable=False, default=dict)
    emergency_contact = Column(JSONB, nullable=False, default=dict)
    document_file_ids = Column(JSONB, nullable=False, default=list)
    verification_notes = Column(Text, nullable=True)
    reviewed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    borrower = relationship("Borrower")
    company = relationship("LoanCompany")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])


class BorrowerEmploymentProfile(Base):
    __tablename__ = "borrower_employment_profiles"
    __table_args__ = (
        UniqueConstraint("borrower_id", name="uq_employment_borrower"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    employment_status = Column(String(40), nullable=False, default="employed")
    employer_name = Column(String(200), nullable=True)
    employer_registration = Column(String(100), nullable=True)
    employer_phone = Column(String(40), nullable=True)
    employer_address = Column(Text, nullable=True)
    employee_number = Column(String(100), nullable=True)
    job_title = Column(String(150), nullable=True)
    employment_start_date = Column(Date, nullable=True)
    contract_type = Column(String(60), nullable=True)
    contract_expiry_date = Column(Date, nullable=True)
    salary_frequency = Column(String(30), nullable=False, default="monthly")
    gross_salary = Column(Numeric(15, 2), nullable=False, default=0)
    net_salary = Column(Numeric(15, 2), nullable=False, default=0)
    verified_net_income = Column(Numeric(15, 2), nullable=False, default=0)
    salary_day = Column(Integer, nullable=True)
    verification_method = Column(String(100), nullable=True)
    verification_status = Column(String(40), nullable=False, default="unverified")
    payslip_count = Column(Integer, nullable=False, default=0)
    bank_statement_months = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)

    borrower = relationship("Borrower")
    company = relationship("LoanCompany")


class BorrowerIncomeSource(Base):
    __tablename__ = "borrower_income_sources"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(60), nullable=False)
    description = Column(String(240), nullable=True)
    declared_amount = Column(Numeric(15, 2), nullable=False, default=0)
    verified_amount = Column(Numeric(15, 2), nullable=False, default=0)
    frequency = Column(String(30), nullable=False, default="monthly")
    verification_method = Column(String(100), nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)

    borrower = relationship("Borrower")
    company = relationship("LoanCompany")


class BorrowerExpense(Base):
    __tablename__ = "borrower_expenses"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(80), nullable=False)
    description = Column(String(240), nullable=True)
    monthly_amount = Column(Numeric(15, 2), nullable=False, default=0)
    is_verified = Column(Boolean, nullable=False, default=False)
    verification_notes = Column(Text, nullable=True)

    borrower = relationship("Borrower")
    company = relationship("LoanCompany")


class BorrowerDebtObligation(Base):
    __tablename__ = "borrower_debt_obligations"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    creditor = Column(String(200), nullable=False)
    account_reference = Column(String(140), nullable=True)
    debt_type = Column(String(80), nullable=False, default="other")
    started_on = Column(Date, nullable=True)
    original_amount = Column(Numeric(15, 2), nullable=False, default=0)
    current_balance = Column(Numeric(15, 2), nullable=False, default=0)
    installment_amount = Column(Numeric(15, 2), nullable=False, default=0)
    installment_frequency = Column(String(30), nullable=False, default="monthly")
    monthly_installment = Column(Numeric(15, 2), nullable=False, default=0)
    total_installments = Column(Integer, nullable=True)
    installments_paid = Column(Integer, nullable=False, default=0)
    remaining_installments = Column(Integer, nullable=True)
    next_due_date = Column(Date, nullable=True)
    settlement_amount = Column(Numeric(15, 2), nullable=True)
    remaining_term_months = Column(Integer, nullable=True)
    status = Column(String(30), nullable=False, default="active", index=True)
    source = Column(String(60), nullable=False, default="declared")
    is_verified = Column(Boolean, nullable=False, default=False)
    last_reviewed_at = Column(DateTime, nullable=True)
    last_reviewed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes = Column(Text, nullable=True)

    borrower = relationship("Borrower")
    company = relationship("LoanCompany")
    last_reviewed_by = relationship("User", foreign_keys=[last_reviewed_by_user_id])
    events = relationship(
        "BorrowerDebtObligationEvent",
        back_populates="obligation",
        cascade="all, delete-orphan",
        order_by="BorrowerDebtObligationEvent.event_at",
    )


class BorrowerDebtObligationEvent(Base):
    __tablename__ = "borrower_debt_obligation_events"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    obligation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrower_debt_obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type = Column(String(40), nullable=False, default="reviewed", index=True)
    event_at = Column(DateTime, nullable=False)
    amount = Column(Numeric(15, 2), nullable=True)
    balance_after = Column(Numeric(15, 2), nullable=True)
    remaining_installments_after = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    company = relationship("LoanCompany")
    borrower = relationship("Borrower")
    obligation = relationship("BorrowerDebtObligation", back_populates="events")
    recorded_by = relationship("User", foreign_keys=[recorded_by_user_id])


class BorrowerBankAccount(Base):
    """Bank and tokenized card information.

    Full card numbers, CVV/CVC and PIN values are intentionally not represented.
    """

    __tablename__ = "borrower_bank_accounts"
    __table_args__ = ()

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    account_holder = Column(String(200), nullable=False)
    bank_name = Column(String(160), nullable=False)
    branch_name = Column(String(160), nullable=True)
    branch_code = Column(String(40), nullable=True)
    account_type = Column(String(40), nullable=False, default="savings")
    currency = Column(String(3), nullable=False, default="LSL")
    account_number_encrypted = Column(Text, nullable=False)
    account_number_last4 = Column(String(4), nullable=False)
    salary_account = Column(Boolean, nullable=False, default=False)
    verification_status = Column(String(40), nullable=False, default="unverified")
    verification_reference = Column(String(180), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    tokenized_card_provider = Column(String(80), nullable=True)
    tokenized_card_reference_encrypted = Column(Text, nullable=True)
    masked_card_number = Column(String(30), nullable=True)
    card_brand = Column(String(30), nullable=True)
    card_expiry_month = Column(Integer, nullable=True)
    card_expiry_year = Column(Integer, nullable=True)

    borrower = relationship("Borrower")
    company = relationship("LoanCompany")


class AffordabilityAssessment(Base):
    __tablename__ = "affordability_assessments"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("origination_policies.id", ondelete="SET NULL"), nullable=True)
    policy_version = Column(Integer, nullable=False, default=1)
    assessment_number = Column(Integer, nullable=False, default=1)
    decision = Column(String(50), nullable=False, index=True)
    verified_income = Column(Numeric(15, 2), nullable=False, default=0)
    household_expenses = Column(Numeric(15, 2), nullable=False, default=0)
    existing_debt_installments = Column(Numeric(15, 2), nullable=False, default=0)
    configured_buffer = Column(Numeric(15, 2), nullable=False, default=0)
    dependant_allowance_total = Column(Numeric(15, 2), nullable=False, default=0)
    disposable_income = Column(Numeric(15, 2), nullable=False, default=0)
    dti_percent = Column(Numeric(8, 3), nullable=False, default=0)
    disposable_income_limit = Column(Numeric(15, 2), nullable=False, default=0)
    dti_limit = Column(Numeric(15, 2), nullable=False, default=0)
    installment_income_limit = Column(Numeric(15, 2), nullable=False, default=0)
    maximum_affordable_installment = Column(Numeric(15, 2), nullable=False, default=0)
    proposed_installment = Column(Numeric(15, 2), nullable=False, default=0)
    affordability_headroom = Column(Numeric(15, 2), nullable=False, default=0)
    input_snapshot = Column(JSONB, nullable=False, default=dict)
    result_reasons = Column(JSONB, nullable=False, default=list)
    calculated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    overridden = Column(Boolean, nullable=False, default=False)
    override_decision = Column(String(50), nullable=True)
    override_reason = Column(Text, nullable=True)
    overridden_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    overridden_at = Column(DateTime, nullable=True)

    application = relationship("DirectLoanApplication", foreign_keys=[application_id])
    borrower = relationship("Borrower")
    company = relationship("LoanCompany")
    policy = relationship("OriginationPolicy")


class LoanContract(Base):
    __tablename__ = "loan_contracts"
    __table_args__ = (
        UniqueConstraint("loan_id", name="uq_loan_contract_loan"),
        UniqueConstraint("contract_number", name="uq_loan_contract_number"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_number = Column(String(80), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(40), nullable=False, default="draft", index=True)
    terms_snapshot = Column(JSONB, nullable=False, default=dict)
    contract_hash = Column(String(64), nullable=False)
    pdf_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="SET NULL"), nullable=True)
    borrower_signature_name = Column(String(200), nullable=True)
    borrower_signed_at = Column(DateTime, nullable=True)
    borrower_signature_method = Column(String(40), nullable=True)
    company_signer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    company_signed_at = Column(DateTime, nullable=True)
    company_signature_method = Column(String(40), nullable=True)
    witness_name = Column(String(200), nullable=True)
    locked_at = Column(DateTime, nullable=True)

    company = relationship("LoanCompany")
    borrower = relationship("Borrower")
    application = relationship("DirectLoanApplication", foreign_keys=[application_id])
    loan = relationship("ClientCompanyLoan", foreign_keys=[loan_id])
    pdf_file = relationship("ManagedFile", foreign_keys=[pdf_file_id])
    company_signer = relationship("User", foreign_keys=[company_signer_user_id])


class LoanTopUpSettlement(Base):
    __tablename__ = "loan_top_up_settlements"
    __table_args__ = (UniqueConstraint("new_loan_id", name="uq_top_up_settlement_new_loan"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    parent_loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False, index=True)
    new_loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    settlement_amount = Column(Numeric(15, 2), nullable=False)
    cash_to_borrower = Column(Numeric(15, 2), nullable=False)
    parent_balance_before = Column(Numeric(15, 2), nullable=False)
    parent_amount_paid_before = Column(Numeric(15, 2), nullable=False)
    parent_status_before = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="settled", index=True)
    settled_at = Column(DateTime, nullable=False)
    settled_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reversed_at = Column(DateTime, nullable=True)
    reversed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    parent_loan = relationship("ClientCompanyLoan", foreign_keys=[parent_loan_id])
    new_loan = relationship("ClientCompanyLoan", foreign_keys=[new_loan_id])



class OriginationIntegrationConfiguration(Base):
    __tablename__ = "origination_integration_configurations"
    __table_args__ = (
        UniqueConstraint("company_id", "provider", name="uq_origination_integration_company_provider"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(40), nullable=False, index=True)
    environment = Column(String(30), nullable=False, default="sandbox")
    is_enabled = Column(Boolean, nullable=False, default=False)
    configuration = Column(JSONB, nullable=False, default=dict)
    encrypted_credentials = Column(Text, nullable=True)
    last_test_status = Column(String(40), nullable=True)
    last_tested_at = Column(DateTime, nullable=True)
    configured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("LoanCompany")
    configured_by = relationship("User", foreign_keys=[configured_by_user_id])
