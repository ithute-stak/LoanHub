from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from database.schemas.file_management import ManagedFileRead

from database.models.enums import (
    BranchTransferStatus,
    OpeningSourceType,
    PaymentMethod,
    TreasuryDayStatus,
    TreasuryDirection,
    TreasuryEntryApprovalStatus,
    TreasuryEntryType,
)


class PaymentMethodOption(BaseModel):
    value: PaymentMethod
    label: str
    proof_recommended: bool = True


class TreasurySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headquarters_branch_id: UUID | None = None
    currency: str = Field(default="LSL", min_length=3, max_length=3)
    timezone: str = Field(default="Africa/Maseru", min_length=3, max_length=80)
    auto_open_enabled: bool = True
    auto_open_time: time = time(0, 1)
    auto_submit_enabled: bool = True
    auto_submit_time: time = time(16, 30)
    require_proof_for_non_cash: bool = True
    allow_branch_reopen: bool = False
    expense_approval_threshold: Decimal = Field(default=0, ge=0, max_digits=15, decimal_places=2)
    dual_control_expenses: bool = True

    @model_validator(mode="after")
    def validate_daily_cycle_times(self):
        if self.auto_open_enabled and self.auto_submit_enabled:
            if self.auto_open_time >= self.auto_submit_time:
                raise ValueError("The daily opening time must be earlier than the submission time")
        return self


class TreasurySettingsRead(TreasurySettingsUpdate):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class ExpenseCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class ExpenseCategoryRead(ExpenseCategoryCreate):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpeningSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID | None = None
    business_date: date | None = None
    source_type: OpeningSourceType
    payment_method: PaymentMethod = PaymentMethod.CASH
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", min_length=3, max_length=3)
    description: str = Field(min_length=3, max_length=2000)
    source_reference: str | None = Field(default=None, max_length=180)
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def forbid_system_previous_closing(self):
        if self.source_type == OpeningSourceType.PREVIOUS_CLOSING:
            raise ValueError("Previous closing is created automatically by LoanHub")
        return self


class OpeningSourceRead(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID
    daily_ledger_id: UUID
    source_type: OpeningSourceType
    payment_method: PaymentMethod
    amount: Decimal
    currency: str
    description: str
    source_reference: str
    proof_reference: str | None
    proof_url: str | None
    proof_notes: str | None
    transfer_id: UUID | None
    is_system_generated: bool
    is_confirmed: bool
    confirmed_at: datetime | None
    confirmed_by_user_id: UUID | None
    recorded_by_user_id: UUID | None
    is_voided: bool
    void_reason: str | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TreasuryEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID | None = None
    direction: TreasuryDirection
    entry_type: TreasuryEntryType
    payment_method: PaymentMethod = PaymentMethod.CASH
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", min_length=3, max_length=3)
    occurred_at: datetime | None = None
    description: str = Field(min_length=3, max_length=2000)
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    external_reference: str | None = Field(default=None, max_length=180)
    expense_category_id: UUID | None = None
    loan_id: UUID | None = None
    borrower_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=180)
    voucher_number: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_expense_category(self):
        if self.entry_type == TreasuryEntryType.EXPENSE and not self.expense_category_id:
            raise ValueError("An expense category is required for expense entries")
        return self


class TreasuryEntryRead(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID
    daily_ledger_id: UUID
    direction: TreasuryDirection
    entry_type: TreasuryEntryType
    payment_method: PaymentMethod
    approval_status: TreasuryEntryApprovalStatus
    requires_approval: bool
    idempotency_key: str | None
    voucher_number: str | None
    amount: Decimal
    currency: str
    occurred_at: datetime
    description: str
    proof_reference: str | None
    proof_url: str | None
    proof_notes: str | None
    external_reference: str | None
    expense_category_id: UUID | None
    payment_transaction_id: UUID | None
    loan_id: UUID | None
    borrower_id: UUID | None
    transfer_id: UUID | None
    counterparty_branch_id: UUID | None
    recorded_by_user_id: UUID | None
    approved_at: datetime | None
    approved_by_user_id: UUID | None
    rejected_at: datetime | None
    rejected_by_user_id: UUID | None
    rejection_reason: str | None
    is_voided: bool
    void_reason: str | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntryDecisionCreate(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class BranchDailySubmissionRead(BaseModel):
    id: UUID
    daily_ledger_id: UUID
    company_id: UUID
    branch_id: UUID
    submitted_to_branch_id: UUID | None
    business_date: date
    sequence_number: int
    is_automatic: bool
    opening_balance: Decimal
    total_money_in: Decimal
    total_money_out: Decimal
    closing_balance: Decimal
    declared_closing_balance: Decimal | None
    variance_amount: Decimal
    entry_count: int
    pending_entry_count: int
    channel_totals: dict[str, Any]
    expense_totals: dict[str, Any]
    opening_source_totals: dict[str, Any]
    submitted_at: datetime
    submitted_by_user_id: UUID | None
    notes: str | None
    pdf_file_id: UUID | None = None
    pdf_file: ManagedFileRead | None = None

    model_config = ConfigDict(from_attributes=True)


class BranchDailySubmissionListRead(BaseModel):
    items: list[BranchDailySubmissionRead]
    total: int
    skip: int
    limit: int


class BranchDailyLedgerRead(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID
    business_date: date
    status: TreasuryDayStatus
    opening_balance: Decimal
    total_money_in: Decimal
    total_money_out: Decimal
    expected_closing_balance: Decimal
    declared_closing_balance: Decimal | None
    variance_amount: Decimal
    entry_count: int
    pending_entry_count: int
    submitted_at: datetime | None
    auto_submitted_at: datetime | None
    submitted_by_user_id: UUID | None
    reviewed_at: datetime | None
    reviewed_by_user_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    entries: list[TreasuryEntryRead] = Field(default_factory=list)
    opening_sources: list[OpeningSourceRead] = Field(default_factory=list)
    submissions: list[BranchDailySubmissionRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DailySubmissionCreate(BaseModel):
    declared_closing_balance: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class ReopenDayCreate(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class VoidEntryCreate(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class VoidOpeningSourceCreate(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class BranchFundingTransferCreate(BaseModel):
    target_branch_id: UUID
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    payment_method: PaymentMethod = PaymentMethod.CASH
    business_date: date | None = None
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class BranchFundingTransferRead(BaseModel):
    id: UUID
    company_id: UUID
    source_branch_id: UUID
    target_branch_id: UUID
    business_date: date
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    reference: str
    status: BranchTransferStatus
    proof_reference: str | None
    proof_url: str | None
    notes: str | None
    issued_at: datetime
    issued_by_user_id: UUID | None
    received_at: datetime | None
    received_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MethodTotals(BaseModel):
    method: PaymentMethod
    opening_balance: Decimal = Decimal("0.00")
    money_in: Decimal
    money_out: Decimal
    net: Decimal
    closing_balance: Decimal = Decimal("0.00")
    entry_count: int


class OpeningSourceTotals(BaseModel):
    source_type: OpeningSourceType
    amount: Decimal
    source_count: int


class BranchDaySummary(BaseModel):
    branch_id: UUID
    branch_name: str
    is_headquarters: bool
    ledger_id: UUID
    status: TreasuryDayStatus
    opening_balance: Decimal
    total_money_in: Decimal
    total_money_out: Decimal
    expected_closing_balance: Decimal
    declared_closing_balance: Decimal | None
    variance_amount: Decimal
    entry_count: int
    pending_entry_count: int
    submitted_at: datetime | None


class TreasuryDashboardRead(BaseModel):
    business_date: date
    currency: str
    headquarters_branch_id: UUID | None
    auto_open_enabled: bool
    auto_open_time: time
    auto_submit_enabled: bool
    auto_submit_time: time
    consolidated_previous_closing: Decimal
    owner_contributions: Decimal
    headquarters_funding: Decimal
    other_opening_sources: Decimal
    total_opening_balance: Decimal
    total_money_in: Decimal
    total_money_out: Decimal
    internal_transfer_out: Decimal = Decimal("0.00")
    external_money_out: Decimal = Decimal("0.00")
    consolidated_closing_balance: Decimal
    pending_expense_amount: Decimal
    method_totals: list[MethodTotals]
    opening_source_totals: list[OpeningSourceTotals]
    branches: list[BranchDaySummary]


class TreasuryStatementRead(BaseModel):
    date_from: date
    date_to: date
    opening_balance: Decimal
    total_money_in: Decimal
    total_money_out: Decimal
    closing_balance: Decimal
    method_totals: list[MethodTotals]
    entries: list[TreasuryEntryRead]


class FinancialIntegrityIssueRead(BaseModel):
    code: str
    severity: Literal["critical", "warning", "info"]
    title: str
    detail: str
    record_type: str | None = None
    record_id: str | None = None
    branch_id: UUID | None = None
    amount: Decimal | None = None
    repairable: bool = False


class FinancialIntegrityReportRead(BaseModel):
    business_date: date
    branch_id: UUID | None = None
    generated_at: datetime
    status: Literal["healthy", "warning", "critical"]
    checks_run: int
    issue_count: int
    critical_count: int
    warning_count: int
    repairable_count: int
    succeeded_payment_count: int
    treasury_payment_count: int
    posted_treasury_count: int
    posted_journal_count: int
    pending_expense_count: int
    pending_expense_amount: Decimal
    proof_exception_count: int
    ledger_variance_count: int
    missing_treasury_count: int
    missing_journal_count: int
    unbalanced_journal_count: int
    issues: list[FinancialIntegrityIssueRead] = Field(default_factory=list)


class FinancialIntegrityRepairRead(BaseModel):
    repaired_treasury_entries: int = 0
    repaired_journals: int = 0
    recalculated_ledgers: int = 0
    report: FinancialIntegrityReportRead
