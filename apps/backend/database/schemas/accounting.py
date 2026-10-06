from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ACCOUNT_TYPES = {"asset", "liability", "equity", "revenue", "expense"}
NORMAL_BALANCES = {"debit", "credit"}


class AccountingAccountCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=180)
    account_type: str
    normal_balance: str
    description: str | None = None
    parent_id: UUID | None = None
    branch_id: UUID | None = None

    @field_validator("account_type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        value = value.lower()
        if value not in ACCOUNT_TYPES:
            raise ValueError("Invalid account type")
        return value

    @field_validator("normal_balance")
    @classmethod
    def valid_balance(cls, value: str) -> str:
        value = value.lower()
        if value not in NORMAL_BALANCES:
            raise ValueError("Normal balance must be debit or credit")
        return value


class AccountingAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    is_active: bool | None = None


class AccountingAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scope_key: str
    scope_type: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    parent_id: UUID | None = None
    code: str
    name: str
    account_type: str
    normal_balance: str
    description: str | None = None
    is_system: bool
    is_active: bool
    created_at: datetime


class JournalLineCreate(BaseModel):
    account_id: UUID
    description: str | None = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")

    @model_validator(mode="after")
    def one_side_only(self):
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debit and credit cannot be negative")
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Each line must contain either a debit or a credit")
        return self


class OpeningBalanceMigrationCreate(BaseModel):
    entry_date: date
    description: str = Field(min_length=5, max_length=1000)
    migration_reference: str = Field(min_length=3, max_length=120)
    branch_id: UUID | None = None
    lines: list[JournalLineCreate]

    @field_validator("lines")
    @classmethod
    def enough_opening_lines(cls, value: list[JournalLineCreate]) -> list[JournalLineCreate]:
        if len(value) < 2:
            raise ValueError("Opening balances need at least two lines")
        debit = sum((line.debit for line in value), Decimal("0"))
        credit = sum((line.credit for line in value), Decimal("0"))
        if debit <= 0 or debit != credit:
            raise ValueError("Opening balance debits and credits must be equal and greater than zero")
        if len({line.account_id for line in value}) < 2:
            raise ValueError("Opening balances must affect at least two accounts")
        return value


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    lines: list[JournalLineCreate]

    @field_validator("lines")
    @classmethod
    def enough_lines(cls, value: list[JournalLineCreate]) -> list[JournalLineCreate]:
        if len(value) < 2:
            raise ValueError("A journal entry needs at least two lines")
        return value


class JournalLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_id: UUID
    description: str | None = None
    debit: Decimal
    credit: Decimal
    account: AccountingAccountRead


class JournalEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scope_key: str
    scope_type: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    entry_number: str
    entry_date: date
    description: str
    reference_type: str | None = None
    reference_id: str | None = None
    status: str
    total_debit: Decimal
    total_credit: Decimal
    posted_at: datetime | None = None
    created_at: datetime
    lines: list[JournalLineRead]


class TrialBalanceLine(BaseModel):
    account_id: UUID
    code: str
    name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class TrialBalanceRead(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    lines: list[TrialBalanceLine]
    total_debit: Decimal
    total_credit: Decimal


class FinancialStatementLine(BaseModel):
    code: str
    name: str
    amount: Decimal


class FinancialStatementRead(BaseModel):
    statement: str
    from_date: date | None = None
    to_date: date
    sections: dict[str, list[FinancialStatementLine]]
    totals: dict[str, Decimal]


class LedgerLineRead(BaseModel):
    entry_id: UUID
    entry_number: str
    entry_date: date
    description: str
    reference_type: str | None = None
    reference_id: str | None = None
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


class LedgerRead(BaseModel):
    account: AccountingAccountRead
    from_date: date | None = None
    to_date: date | None = None
    opening_balance: Decimal
    closing_balance: Decimal
    lines: list[LedgerLineRead]


class ExpensePostCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    description: str = Field(min_length=2, max_length=1000)
    expense_account_code: str = Field(default="6500", min_length=4, max_length=30)
    branch_id: UUID | None = None
    paid_now: bool = True
    entry_date: date | None = None
    external_reference: str | None = Field(default=None, max_length=120)


class AccountingDashboardRead(BaseModel):
    as_of: date
    cash_and_bank: Decimal
    loans_receivable: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    equity: Decimal
    revenue: Decimal
    expenses: Decimal
    net_profit: Decimal
    trial_balance_difference: Decimal


class DepreciationAdjustmentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class ShareIssueCreate(BaseModel):
    shares_issued: int = Field(gt=0)
    nominal_value_per_share: Decimal = Field(gt=0)
    issue_price_per_share: Decimal = Field(gt=0)
    settlement_account_code: str = Field(default="1010", min_length=4, max_length=30)
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_issue_price(self):
        if self.issue_price_per_share < self.nominal_value_per_share:
            raise ValueError("Issue price cannot be below nominal value in this workflow")
        return self


class DividendPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    settlement_account_code: str = Field(default="1010", min_length=4, max_length=30)
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class CorporationTaxCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class LoanNoteIssueCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    settlement_account_code: str = Field(default="1010", min_length=4, max_length=30)
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class InventoryValuationItem(BaseModel):
    reference: str = Field(min_length=1, max_length=120)
    cost: Decimal = Field(ge=0)
    expected_selling_price: Decimal = Field(ge=0)
    costs_to_sell: Decimal = Field(default=Decimal("0"), ge=0)


class InventoryValuationRequest(BaseModel):
    items: list[InventoryValuationItem] = Field(min_length=1)


class CapitalExpenditureComponent(BaseModel):
    description: str = Field(min_length=2, max_length=240)
    amount: Decimal = Field(gt=0)
    category: str = Field(pattern=(
        "^(purchase_price|delivery|non_refundable_tax|site_preparation|"
        "assembly_installation|testing|professional_fees|improvement|"
        "repair_maintenance|insurance|fuel|day_to_day|borrowing_cost_construction)$"
    ))


class CapitalExpenditureAssessment(BaseModel):
    components: list[CapitalExpenditureComponent] = Field(min_length=1)
    borrowing_costs_directly_attributable: bool = False
    asset_requires_substantial_time_to_prepare: bool = False


class AccruedIncomeAdjustmentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    revenue_account_code: str = Field(default="4900", min_length=4, max_length=30)
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class AccrualAdjustmentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    description: str = Field(min_length=2, max_length=1000)
    expense_account_code: str = Field(default="6500", min_length=4, max_length=30)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class PrepaymentAdjustmentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    description: str = Field(min_length=2, max_length=1000)
    expense_account_code: str = Field(default="6500", min_length=4, max_length=30)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class DoubtfulDebtAllowanceCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    direction: str = Field(pattern="^(increase|decrease)$")
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class VatTransactionCreate(BaseModel):
    transaction_type: str = Field(pattern="^(sale|purchase|expense|asset)$")
    net_amount: Decimal = Field(gt=0)
    vat_amount: Decimal = Field(ge=0)
    account_code: str = Field(min_length=4, max_length=30)
    settlement_account_code: str = Field(default="1000", min_length=4, max_length=30)
    vat_registered: bool = True
    description: str = Field(min_length=2, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)


class SuspenseCorrectionCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    target_account_code: str = Field(min_length=4, max_length=30)
    target_side: str = Field(pattern="^(debit|credit)$")
    description: str = Field(min_length=5, max_length=1000)
    branch_id: UUID | None = None
    entry_date: date | None = None
    reference_id: str | None = Field(default=None, max_length=120)





class TreasuryCommitmentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    category: str = Field(pattern="^(expense|payroll|provider|tax|refund|capital|other)$")
    due_date: date
    amount: Decimal = Field(gt=0)
    branch_id: UUID | None = None
    description: str | None = Field(default=None, max_length=1000)


class TreasuryForecastRequest(BaseModel):
    from_date: date
    to_date: date
    minimum_cash: Decimal = Field(default=Decimal("0"), ge=0)
    collection_rate: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    obligation_rate: Decimal = Field(default=Decimal("1"), ge=0)
    unexpected_outflow: Decimal = Field(default=Decimal("0"), ge=0)
    branch_id: UUID | None = None

    @model_validator(mode="after")
    def validate_forecast_period(self):
        if self.to_date < self.from_date:
            raise ValueError("to_date must be on or after from_date")
        if (self.to_date - self.from_date).days > 366:
            raise ValueError("Treasury forecast horizon cannot exceed 366 days")
        return self

class FinancialPlanLineCreate(BaseModel):
    account_code: str = Field(min_length=4, max_length=30)
    period_start: date
    amount: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class FinancialPlanCreate(BaseModel):
    name: str = Field(min_length=3, max_length=240)
    plan_type: str = Field(pattern="^(budget|forecast)$")
    fiscal_start: date
    fiscal_end: date
    branch_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[FinancialPlanLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan_period(self):
        if self.fiscal_end < self.fiscal_start:
            raise ValueError("fiscal_end must be on or after fiscal_start")
        for line in self.lines:
            if line.period_start < self.fiscal_start or line.period_start > self.fiscal_end:
                raise ValueError("Plan line period_start must fall within the plan period")
        return self

class MonthEndAdjustmentDraftCreate(BaseModel):
    adjustment_type: str = Field(pattern="^(accrual|prepayment|accrued_income)$")
    amount: Decimal = Field(gt=0)
    account_code: str = Field(min_length=4, max_length=30)
    description: str = Field(min_length=5, max_length=1000)
    entry_date: date
    branch_id: UUID | None = None
    reference_id: str | None = Field(default=None, max_length=120)
    reversal_date: date | None = None

    @model_validator(mode="after")
    def validate_reversal_date(self):
        if self.reversal_date is not None and self.reversal_date <= self.entry_date:
            raise ValueError("reversal_date must be after entry_date")
        return self

class FixedAssetCreate(BaseModel):
    reference: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    acquisition_date: date
    cost: Decimal = Field(gt=0)
    residual_value: Decimal = Field(default=Decimal("0"), ge=0)
    useful_life_years: int = Field(ge=1, le=100)
    depreciation_method: str = Field(pattern="^(straight_line|reducing_balance)$")
    depreciation_rate: Decimal | None = Field(default=None, gt=0, le=100)
    branch_id: UUID | None = None
    location: str | None = Field(default=None, max_length=240)
    serial_number: str | None = Field(default=None, max_length=180)
    assigned_to: str | None = Field(default=None, max_length=240)
    settlement_account_code: str | None = Field(default=None, min_length=4, max_length=30)
    post_acquisition: bool = False

    @model_validator(mode="after")
    def validate_asset_policy(self):
        if self.residual_value >= self.cost:
            raise ValueError("Residual value must be lower than cost")
        if self.depreciation_method == "reducing_balance" and self.depreciation_rate is None:
            raise ValueError("Reducing-balance assets require depreciation_rate")
        return self


class FixedAssetDepreciationRun(BaseModel):
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class FixedAssetDisposeCreate(BaseModel):
    disposal_date: date
    proceeds: Decimal = Field(ge=0)
    settlement_account_code: str = Field(default="1010", min_length=4, max_length=30)
    description: str = Field(min_length=5, max_length=1000)


class FixedAssetRead(BaseModel):
    id: UUID
    reference: str
    name: str
    description: str | None = None
    status: str
    branch_id: UUID | None = None
    currency: str
    cost: Decimal
    acquisition_date: date
    residual_value: Decimal
    useful_life_years: int
    depreciation_method: str
    depreciation_rate: Decimal | None = None
    accumulated_depreciation: Decimal
    carrying_amount: Decimal
    location: str | None = None
    serial_number: str | None = None
    assigned_to: str | None = None
    last_depreciation_date: date | None = None
    disposed_at: date | None = None
    disposal_proceeds: Decimal | None = None


class LoanWriteOffCreate(BaseModel):
    loan_id: UUID
    write_off_date: date
    description: str = Field(min_length=5, max_length=1000)


class PeriodAdjustmentReversalCreate(BaseModel):
    reversal_date: date
    description: str = Field(min_length=5, max_length=1000)


class WrittenOffLoanRecoveryCreate(BaseModel):
    loan_id: UUID
    amount: Decimal = Field(gt=0)
    recovery_date: date
    payment_method: str = Field(pattern="^(cash|bank|electronic)$")
    proof_reference: str | None = Field(default=None, max_length=180)
    description: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def validate_recovery_evidence(self):
        if self.payment_method != "cash" and not (self.proof_reference or "").strip():
            raise ValueError("Non-cash recoveries require a proof_reference")
        return self


class ElectronicClearingSettlementCreate(BaseModel):
    settlement_date: date
    amount: Decimal = Field(gt=0)
    direction: str = Field(pattern="^(provider_to_bank|bank_to_provider)$")
    provider_reference: str = Field(min_length=2, max_length=180)
    proof_reference: str = Field(min_length=2, max_length=180)
    branch_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)
