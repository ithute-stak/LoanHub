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
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import (
    BranchTransferStatus,
    OpeningSourceType,
    PaymentMethod,
    TreasuryDayStatus,
    TreasuryDirection,
    TreasuryEntryApprovalStatus,
    TreasuryEntryType,
)


class TreasurySettings(Base):
    __tablename__ = "treasury_settings"
    __table_args__ = (UniqueConstraint("company_id", name="uq_treasury_settings_company"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    headquarters_branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    currency = Column(String(3), nullable=False, default="LSL")
    timezone = Column(String(80), nullable=False, default="Africa/Maseru")
    auto_open_enabled = Column(Boolean, nullable=False, default=True)
    auto_open_time = Column(Time, nullable=False)
    auto_submit_enabled = Column(Boolean, nullable=False, default=True)
    auto_submit_time = Column(Time, nullable=False)
    require_proof_for_non_cash = Column(Boolean, nullable=False, default=True)
    allow_branch_reopen = Column(Boolean, nullable=False, default=False)
    expense_approval_threshold = Column(Numeric(15, 2), nullable=False, default=0)
    dual_control_expenses = Column(Boolean, nullable=False, default=True)

    headquarters_branch = relationship("CompanyBranch", foreign_keys=[headquarters_branch_id])


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_expense_category_company_name"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class BranchDailyLedger(Base):
    __tablename__ = "branch_daily_ledgers"
    __table_args__ = (UniqueConstraint("company_id", "branch_id", "business_date", name="uq_branch_daily_ledger_company_branch_date"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    business_date = Column(Date, nullable=False, index=True)
    status = Column(Enum(TreasuryDayStatus, native_enum=False, length=30, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, default=TreasuryDayStatus.OPEN, index=True)
    opening_balance = Column(Numeric(15, 2), nullable=False, default=0)
    total_money_in = Column(Numeric(15, 2), nullable=False, default=0)
    total_money_out = Column(Numeric(15, 2), nullable=False, default=0)
    expected_closing_balance = Column(Numeric(15, 2), nullable=False, default=0)
    declared_closing_balance = Column(Numeric(15, 2), nullable=True)
    variance_amount = Column(Numeric(15, 2), nullable=False, default=0)
    entry_count = Column(Integer, nullable=False, default=0)
    pending_entry_count = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime, nullable=True)
    auto_submitted_at = Column(DateTime, nullable=True)
    submitted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    branch = relationship("CompanyBranch")
    entries = relationship("TreasuryEntry", back_populates="daily_ledger", cascade="all, delete-orphan", passive_deletes=True)
    opening_sources = relationship("BranchOpeningSource", back_populates="daily_ledger", cascade="all, delete-orphan", passive_deletes=True)
    submissions = relationship("BranchDailySubmission", back_populates="daily_ledger", cascade="all, delete-orphan", passive_deletes=True)


class BranchOpeningSource(Base):
    __tablename__ = "branch_opening_sources"
    __table_args__ = (
        UniqueConstraint("daily_ledger_id", "source_type", "source_reference", name="uq_branch_opening_source_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    daily_ledger_id = Column(UUID(as_uuid=True), ForeignKey("branch_daily_ledgers.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(Enum(OpeningSourceType, native_enum=False, length=40, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, index=True)
    payment_method = Column(Enum(PaymentMethod, native_enum=False, length=40, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, default=PaymentMethod.CASH, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    description = Column(Text, nullable=False)
    source_reference = Column(String(180), nullable=False, index=True)
    proof_reference = Column(String(180), nullable=True)
    proof_url = Column(String(500), nullable=True)
    proof_notes = Column(Text, nullable=True)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("branch_funding_transfers.id", ondelete="SET NULL", use_alter=True), nullable=True, index=True)
    is_system_generated = Column(Boolean, nullable=False, default=False)
    is_confirmed = Column(Boolean, nullable=False, default=True, index=True)
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_voided = Column(Boolean, nullable=False, default=False, index=True)
    void_reason = Column(Text, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    daily_ledger = relationship("BranchDailyLedger", back_populates="opening_sources")
    branch = relationship("CompanyBranch", foreign_keys=[branch_id])
    transfer = relationship("BranchFundingTransfer", foreign_keys=[transfer_id], back_populates="opening_sources")


class TreasuryEntry(Base):
    __tablename__ = "treasury_entries"
    __table_args__ = (
        UniqueConstraint("payment_transaction_id", name="uq_treasury_entry_payment_transaction"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_treasury_entry_company_idempotency"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    daily_ledger_id = Column(UUID(as_uuid=True), ForeignKey("branch_daily_ledgers.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(Enum(TreasuryDirection, native_enum=False, length=20, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, index=True)
    entry_type = Column(Enum(TreasuryEntryType, native_enum=False, length=40, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, index=True)
    payment_method = Column(Enum(PaymentMethod, native_enum=False, length=40, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, default=PaymentMethod.CASH, index=True)
    approval_status = Column(Enum(TreasuryEntryApprovalStatus, native_enum=False, length=20, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, default=TreasuryEntryApprovalStatus.POSTED, index=True)
    requires_approval = Column(Boolean, nullable=False, default=False, index=True)
    idempotency_key = Column(String(180), nullable=True, index=True)
    voucher_number = Column(String(100), nullable=True, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    occurred_at = Column(DateTime, nullable=False, index=True)
    description = Column(Text, nullable=False)
    proof_reference = Column(String(180), nullable=True, index=True)
    proof_url = Column(String(500), nullable=True)
    proof_notes = Column(Text, nullable=True)
    external_reference = Column(String(180), nullable=True, index=True)
    expense_category_id = Column(UUID(as_uuid=True), ForeignKey("expense_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_transaction_id = Column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    transfer_id = Column(UUID(as_uuid=True), ForeignKey("branch_funding_transfers.id", ondelete="SET NULL"), nullable=True, index=True)
    counterparty_branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejected_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    is_voided = Column(Boolean, nullable=False, default=False, index=True)
    void_reason = Column(Text, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    daily_ledger = relationship("BranchDailyLedger", back_populates="entries")
    branch = relationship("CompanyBranch", foreign_keys=[branch_id])
    counterparty_branch = relationship("CompanyBranch", foreign_keys=[counterparty_branch_id])
    expense_category = relationship("ExpenseCategory")
    payment_transaction = relationship("PaymentTransaction")
    loan = relationship("ClientCompanyLoan")
    borrower = relationship("Borrower")


class BranchFundingTransfer(Base):
    __tablename__ = "branch_funding_transfers"
    __table_args__ = (UniqueConstraint("reference", name="uq_branch_funding_transfer_reference"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    source_branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    target_branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    business_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    payment_method = Column(Enum(PaymentMethod, native_enum=False, length=40, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, default=PaymentMethod.CASH)
    reference = Column(String(100), nullable=False, index=True)
    status = Column(Enum(BranchTransferStatus, native_enum=False, length=20, values_callable=lambda enum_cls: [item.value for item in enum_cls]), nullable=False, default=BranchTransferStatus.ISSUED, index=True)
    proof_reference = Column(String(180), nullable=True)
    proof_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    issued_at = Column(DateTime, nullable=False)
    issued_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_at = Column(DateTime, nullable=True)
    received_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    source_branch = relationship("CompanyBranch", foreign_keys=[source_branch_id])
    target_branch = relationship("CompanyBranch", foreign_keys=[target_branch_id])
    entries = relationship("TreasuryEntry", foreign_keys="TreasuryEntry.transfer_id")
    opening_sources = relationship("BranchOpeningSource", foreign_keys="BranchOpeningSource.transfer_id", back_populates="transfer")


class BranchDailySubmission(Base):
    __tablename__ = "branch_daily_submissions"
    __table_args__ = (UniqueConstraint("daily_ledger_id", "sequence_number", name="uq_branch_daily_submission_sequence"),)

    daily_ledger_id = Column(UUID(as_uuid=True), ForeignKey("branch_daily_ledgers.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_to_branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    business_date = Column(Date, nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False, default=1)
    is_automatic = Column(Boolean, nullable=False, default=False)
    opening_balance = Column(Numeric(15, 2), nullable=False)
    total_money_in = Column(Numeric(15, 2), nullable=False)
    total_money_out = Column(Numeric(15, 2), nullable=False)
    closing_balance = Column(Numeric(15, 2), nullable=False)
    declared_closing_balance = Column(Numeric(15, 2), nullable=True)
    variance_amount = Column(Numeric(15, 2), nullable=False, default=0)
    entry_count = Column(Integer, nullable=False, default=0)
    pending_entry_count = Column(Integer, nullable=False, default=0)
    channel_totals = Column(JSONB, nullable=False, default=dict)
    expense_totals = Column(JSONB, nullable=False, default=dict)
    opening_source_totals = Column(JSONB, nullable=False, default=dict)
    submitted_at = Column(DateTime, nullable=False)
    submitted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    pdf_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="SET NULL"), nullable=True, index=True)

    daily_ledger = relationship("BranchDailyLedger", back_populates="submissions")
    submitted_to_branch = relationship("CompanyBranch", foreign_keys=[submitted_to_branch_id])
    pdf_file = relationship("ManagedFile", foreign_keys=[pdf_file_id])
