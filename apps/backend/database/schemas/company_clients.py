from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from database.models.enums import (
    EmploymentStatus,
    Gender,
    MaritalStatus,
    PaymentMethod,
)
from database.schemas.origination import BankAccountInput
from database.schemas.employer_group import EmployerGroupCreate
from utils.banking import standard_bank_fields, validate_account_number_for_bank


ExternalDebtStatus = Literal["active", "settled", "defaulted", "restructured", "written_off", "unknown"]
ExternalDebtFrequency = Literal["weekly", "fortnightly", "monthly", "quarterly", "custom"]


class CompanyClientExternalDebtInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creditor: str = Field(min_length=2, max_length=200)
    account_reference: str | None = Field(default=None, max_length=140)
    debt_type: str = Field(default="other", max_length=80)
    started_on: date | None = None
    original_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    current_balance: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    installment_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    installment_frequency: ExternalDebtFrequency = "monthly"
    total_installments: int | None = Field(default=None, ge=0, le=5000)
    installments_paid: int = Field(default=0, ge=0, le=5000)
    remaining_installments: int | None = Field(default=None, ge=0, le=5000)
    next_due_date: date | None = None
    status: ExternalDebtStatus = "active"
    source: str = Field(default="declared", max_length=60)
    is_verified: bool = False
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.started_on and self.started_on > date.today():
            raise ValueError("An existing loan start date cannot be in the future")
        if self.total_installments is not None and self.installments_paid > self.total_installments:
            raise ValueError("Paid installments cannot exceed total installments")
        if self.remaining_installments is None and self.total_installments is not None:
            self.remaining_installments = max(self.total_installments - self.installments_paid, 0)
        if (
            self.total_installments is not None
            and self.remaining_installments is not None
            and self.installments_paid + self.remaining_installments > self.total_installments
        ):
            raise ValueError("Paid and remaining installments cannot exceed total installments")
        if self.status in {"active", "defaulted", "restructured", "unknown"} and self.current_balance > 0:
            if self.installment_amount <= 0:
                raise ValueError("Enter the installment amount for an active existing loan")
            if self.remaining_installments is None:
                raise ValueError("Enter the number of installments remaining")
        return self


class CompanyClientExternalDebtCreate(CompanyClientExternalDebtInput):
    pass


class CompanyClientExternalDebtUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creditor: str | None = Field(default=None, min_length=2, max_length=200)
    account_reference: str | None = Field(default=None, max_length=140)
    debt_type: str | None = Field(default=None, max_length=80)
    started_on: date | None = None
    original_amount: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    current_balance: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    installment_amount: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    installment_frequency: ExternalDebtFrequency | None = None
    total_installments: int | None = Field(default=None, ge=0, le=5000)
    installments_paid: int | None = Field(default=None, ge=0, le=5000)
    remaining_installments: int | None = Field(default=None, ge=0, le=5000)
    next_due_date: date | None = None
    status: ExternalDebtStatus | None = None
    source: str | None = Field(default=None, max_length=60)
    is_verified: bool | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CompanyClientExternalDebtPaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    paid_on: date = Field(default_factory=date.today)
    installments_covered: int = Field(default=1, ge=0, le=5000)
    next_due_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CompanyClientExternalDebtEventRead(BaseModel):
    id: UUID
    event_type: str
    event_at: datetime
    amount: Decimal | None = None
    balance_after: Decimal | None = None
    remaining_installments_after: int | None = None
    notes: str | None = None
    recorded_by_user_id: UUID | None = None


class CompanyClientExternalDebtRead(BaseModel):
    id: UUID
    company_id: UUID
    borrower_id: UUID
    creditor: str
    account_reference: str | None = None
    debt_type: str
    started_on: date | None = None
    original_amount: Decimal
    current_balance: Decimal
    installment_amount: Decimal
    installment_frequency: str
    monthly_installment: Decimal
    total_installments: int | None = None
    installments_paid: int
    remaining_installments: int | None = None
    next_due_date: date | None = None
    status: str
    source: str
    is_verified: bool
    last_reviewed_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    events: list[CompanyClientExternalDebtEventRead] = Field(default_factory=list)


class AssistedCompanyClientCreate(BaseModel):
    branch_id: UUID | None = None
    email: EmailStr | None = None
    phone: str = Field(min_length=8, max_length=30)
    temporary_password: str | None = Field(default=None, min_length=10, max_length=128)

    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    gender: Gender
    date_of_birth: date
    national_id: str | None = Field(default=None, max_length=100)
    passport_number: str | None = Field(default=None, max_length=100)
    marital_status: MaritalStatus | None = None
    nationality: str | None = Field(default="Mosotho", max_length=100)
    district: str = Field(min_length=1, max_length=100)
    town_or_village: str | None = Field(default=None, max_length=150)
    physical_address: str | None = Field(default=None, max_length=500)

    employment_status: EmploymentStatus
    employer_name: str | None = Field(default=None, max_length=200)
    employer_group_id: UUID | None = None
    new_employer_group: EmployerGroupCreate | None = None
    income_day: int | None = Field(default=None, ge=1, le=31)
    job_title: str | None = Field(default=None, max_length=150)
    monthly_income: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    salary_date: str | None = Field(default=None, max_length=20)
    has_existing_loans: bool = False
    existing_loan_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    external_debts: list[CompanyClientExternalDebtInput] = Field(default_factory=list, max_length=50)
    consent_to_share_profile: bool = False
    consent_to_credit_checks: bool = False
    bank_account: BankAccountInput | None = None


class CompanyClientExistingLoanCheckRead(BaseModel):
    national_id: str
    borrower_found: bool
    already_company_client: bool
    company_client_account_id: UUID | None = None
    has_existing_loans: bool
    total_loan_count: int = Field(default=0, ge=0)
    active_loan_count: int = Field(ge=0)
    completed_loan_count: int = Field(default=0, ge=0)
    defaulted_loan_count: int = Field(default=0, ge=0)
    overdue_loan_count: int = Field(default=0, ge=0)
    lender_count: int = Field(default=0, ge=0)
    loanhub_outstanding_total: Decimal = Field(ge=0, max_digits=15, decimal_places=2)
    declared_existing_loan_total: Decimal = Field(ge=0, max_digits=15, decimal_places=2)
    external_debt_count: int = Field(default=0, ge=0)
    external_debt_balance_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    external_debt_monthly_commitment: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    external_debts: list[CompanyClientExternalDebtRead] = Field(default_factory=list)
    existing_loan_total: Decimal = Field(ge=0, max_digits=15, decimal_places=2)
    lifetime_principal_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    lifetime_paid_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    latest_loan_at: datetime | None = None
    checked_at: datetime


class CompanyClientRead(BaseModel):
    id: UUID
    account_reference: str
    company_id: UUID
    branch_id: UUID | None
    borrower_id: UUID
    user_id: UUID
    opened_by_user_id: UUID | None
    source: str
    status: str
    opening_fee_amount: Decimal
    opening_fee_currency: str
    opening_fee_status: str
    opening_fee_payment_id: UUID | None

    first_name: str
    middle_name: str | None
    last_name: str
    full_name: str
    email: EmailStr | None
    phone: str
    gender: str | None
    date_of_birth: date | None
    marital_status: str | None = None
    nationality: str | None = None
    national_id: str | None
    passport_number: str | None
    district: str | None
    town_or_village: str | None
    physical_address: str | None
    employment_status: str
    employer_name: str | None
    employer_group_id: UUID | None = None
    employer_group_code: str | None = None
    income_day: int | None = None
    job_title: str | None
    monthly_income: Decimal | None
    has_existing_loans: bool
    existing_loan_total: Decimal
    consent_to_credit_checks: bool
    is_login_active: bool
    salary_date: str | None = None

    # Safe directory / portfolio summary fields. Full bank account numbers are
    # never returned by this endpoint; only the masked last four are exposed.
    has_bank_account: bool = False
    bank_account_holder: str | None = None
    bank_name: str | None = None
    bank_branch_name: str | None = None
    bank_branch_code: str | None = None
    bank_account_last4: str | None = None
    masked_bank_account: str | None = None
    bank_account_type: str | None = None
    bank_currency: str | None = None
    bank_verification_status: str | None = None
    salary_account: bool = False
    next_salary_pay_date: date | None = None

    loan_count: int = 0
    active_loan_count: int = 0
    loan_statuses: list[str] = Field(default_factory=list)
    outstanding_balance: Decimal = Decimal("0")
    next_due_date: date | None = None
    next_due_amount: Decimal | None = None
    overdue_installment_count: int = 0
    recent_loan_id: UUID | None = None
    recent_loan_reference: str | None = None
    recent_loan_status: str | None = None
    recent_loan_created_at: datetime | None = None

    case_entry_count: int = 0
    comment_count: int = 0
    legal_action_count: int = 0
    open_legal_action_count: int = 0
    latest_case_entry_at: datetime | None = None
    latest_case_entry_kind: str | None = None

    created_at: datetime
    updated_at: datetime


class CompanyClientBankAccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_holder: str | None = Field(default=None, min_length=2, max_length=200)
    bank_name: str | None = Field(default=None, min_length=2, max_length=160)
    branch_name: str | None = Field(default=None, max_length=160)
    branch_code: str | None = Field(default=None, max_length=40)
    account_type: str | None = Field(default=None, max_length=40)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    account_number: str | None = Field(default=None, min_length=4, max_length=40)
    salary_account: bool | None = None

    @model_validator(mode="after")
    def enforce_supported_bank(self):
        bank_name = str(self.bank_name or "").strip()
        account_number = str(self.account_number or "").strip()
        if account_number and not bank_name:
            raise ValueError("Select FNB, PB, STD or NB when changing the account number")
        if bank_name and not account_number:
            raise ValueError("Changing the bank requires the matching new account number")
        if bank_name:
            normalized_bank, branch_name, branch_code = standard_bank_fields(bank_name)
            self.bank_name = normalized_bank
            self.branch_name = branch_name
            self.branch_code = branch_code
            self.account_number = validate_account_number_for_bank(normalized_bank, account_number)
        elif self.branch_name is not None or self.branch_code is not None:
            raise ValueError("Branch and bank code are determined by the selected bank")
        return self


class CompanyClientProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    gender: Gender | None = None
    date_of_birth: date | None = None
    passport_number: str | None = Field(default=None, max_length=50)
    marital_status: MaritalStatus | None = None
    nationality: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    town_or_village: str | None = Field(default=None, max_length=150)
    physical_address: str | None = Field(default=None, max_length=1000)

    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=30)
    is_login_active: bool | None = None
    account_status: str | None = Field(default=None, pattern="^(active|inactive|suspended|closed)$")

    employment_status: EmploymentStatus | None = None
    employer_name: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=150)
    monthly_income: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    salary_date: str | None = Field(default=None, max_length=20)
    has_existing_loans: bool | None = None
    existing_loan_total: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)

    bank_account: CompanyClientBankAccountUpdate | None = None


class CompanyClientProfilePermissionsRead(BaseModel):
    can_edit_profile: bool = False
    can_edit_contact: bool = False
    can_edit_banking: bool = False
    can_edit_account_status: bool = False
    can_request_national_id_change: bool = False
    can_approve_national_id_change: bool = False


class CompanyClientNationalIdChangeRequestCreate(BaseModel):
    proposed_national_id: str = Field(min_length=4, max_length=50)
    reason: str = Field(min_length=10, max_length=2000)


class CompanyClientNationalIdChangeDecision(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if not self.approve and not str(self.reason or "").strip():
            raise ValueError("A rejection reason is required")
        return self


class CompanyClientNationalIdChangeRequestRead(BaseModel):
    id: UUID
    reference: str
    company_id: UUID
    branch_id: UUID | None
    company_borrower_account_id: UUID
    borrower_id: UUID
    current_national_id: str | None
    proposed_national_id: str
    reason: str
    status: str
    borrower_approved_at: datetime | None = None
    company_owner_approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejected_by_role: str | None = None
    rejection_reason: str | None = None
    applied_at: datetime | None = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class CompanyClientPaymentRatingRead(BaseModel):
    score: int | None = Field(default=None, ge=0, le=100)
    grade: str
    label: str
    has_history: bool = False
    explanation: str
    total_due_installments: int = Field(default=0, ge=0)
    paid_installments: int = Field(default=0, ge=0)
    on_time_installments: int = Field(default=0, ge=0)
    late_installments: int = Field(default=0, ge=0)
    overdue_installments: int = Field(default=0, ge=0)
    undated_paid_installments: int = Field(default=0, ge=0)
    on_time_rate: float = Field(default=0, ge=0, le=1)
    completion_rate: float = Field(default=0, ge=0, le=1)
    average_days_late: float = Field(default=0, ge=0)
    total_due_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    total_paid_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    last_payment_at: datetime | None = None


class CompanyClientProfileStatsRead(BaseModel):
    total_loans: int = Field(default=0, ge=0)
    active_loans: int = Field(default=0, ge=0)
    completed_loans: int = Field(default=0, ge=0)
    defaulted_loans: int = Field(default=0, ge=0)
    overdue_loans: int = Field(default=0, ge=0)
    lifetime_principal_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    lifetime_paid_total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    outstanding_balance: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    document_count: int = Field(default=0, ge=0)
    comment_count: int = Field(default=0, ge=0)
    legal_action_count: int = Field(default=0, ge=0)
    open_legal_action_count: int = Field(default=0, ge=0)


class CompanyClientProfileLoanRead(BaseModel):
    id: UUID
    loan_reference: str
    status: str
    risk_level: str
    principal_amount: Decimal
    total_repayable: Decimal
    amount_paid: Decimal
    balance: Decimal
    installment_amount: Decimal
    repayment_type: str
    repayment_period: int
    approved_at: datetime | None = None
    disbursed_at: datetime | None = None
    first_payment_due: date | None = None
    maturity_date: date | None = None
    is_overdue: bool = False
    overdue_installment_count: int = Field(default=0, ge=0)


class CompanyClientProfileDocumentRead(BaseModel):
    id: UUID
    reference: str
    document_type: str
    original_name: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    description: str | None = None
    is_confidential: bool = False
    created_at: datetime


class CompanyClientProfileRead(BaseModel):
    client: CompanyClientRead
    stats: CompanyClientProfileStatsRead
    payment_rating: CompanyClientPaymentRatingRead
    permissions: CompanyClientProfilePermissionsRead = Field(default_factory=CompanyClientProfilePermissionsRead)
    latest_national_id_change_request: CompanyClientNationalIdChangeRequestRead | None = None
    loans: list[CompanyClientProfileLoanRead] = Field(default_factory=list)
    external_debts: list[CompanyClientExternalDebtRead] = Field(default_factory=list)
    documents: list[CompanyClientProfileDocumentRead] = Field(default_factory=list)
    profile_image: CompanyClientProfileDocumentRead | None = None
    recent_case_entries: list[CompanyClientCaseEntryRead] = Field(default_factory=list)


class CompanyClientLoanInsightRead(BaseModel):
    loan_id: UUID
    loan_reference: str
    client_account_id: UUID
    borrower_id: UUID
    client_name: str
    status: str
    balance: Decimal
    installment_amount: Decimal
    due_date: date | None = None
    due_amount: Decimal | None = None
    created_at: datetime


class CompanyClientPortfolioInsightsRead(BaseModel):
    due_within_days: int
    soon_due: list[CompanyClientLoanInsightRead] = Field(default_factory=list)
    recent_loans: list[CompanyClientLoanInsightRead] = Field(default_factory=list)


class CompanyClientCaseEntryCreate(BaseModel):
    entry_type: Literal["comment", "legal_action"] = "comment"
    category: str = Field(default="general", min_length=1, max_length=60)
    title: str | None = Field(default=None, max_length=180)
    body: str = Field(min_length=1, max_length=5000)
    status: str | None = Field(default=None, max_length=40)
    action_date: datetime | None = None
    reference_number: str | None = Field(default=None, max_length=180)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", min_length=3, max_length=3)


class CompanyClientCaseEntryUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=40)


class CompanyClientCaseEntryRead(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID | None
    company_borrower_account_id: UUID
    borrower_id: UUID
    created_by_user_id: UUID | None
    created_by_name: str | None = None
    entry_type: str
    category: str
    title: str | None
    body: str
    status: str
    action_date: datetime | None
    reference_number: str | None
    amount: Decimal | None
    currency: str
    created_at: datetime
    updated_at: datetime


class CompanyClientCaseRecordRead(BaseModel):
    client_account_id: UUID
    borrower_id: UUID
    branch_id: UUID | None
    account_reference: str
    client_name: str
    phone: str
    comment_count: int = 0
    legal_action_count: int = 0
    open_legal_action_count: int = 0
    latest_entry_at: datetime
    latest_entry_kind: str
    latest_entry_status: str
    latest_entry_preview: str


class CashOpeningFeeSettlementCreate(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CASH
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)


class InternalClientLoanRequestCreate(BaseModel):
    branch_id: UUID | None = None
    product_id: UUID | None = None
    requested_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    term_count: int = Field(gt=0, le=600)
    repayment_type: str = Field(default="monthly", pattern="^(daily|weekly|monthly|custom)$")
    purpose: str | None = Field(default=None, max_length=5000)
    installment_due_dates: list[date] = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def validate_due_dates(self):
        if len(self.installment_due_dates) != self.term_count:
            raise ValueError(f"Enter exactly {self.term_count} installment due dates")
        for index in range(1, len(self.installment_due_dates)):
            if self.installment_due_dates[index] <= self.installment_due_dates[index - 1]:
                raise ValueError(f"Installment {index + 1} due date must be after installment {index}")
        return self


class InternalClientLoanRequestRead(BaseModel):
    id: UUID
    application_reference: str
    company_id: UUID
    branch_id: UUID | None
    borrower_id: UUID
    product_id: UUID | None
    requested_amount: Decimal
    term_count: int
    repayment_type: str
    purpose: str | None
    installment_due_dates: list[str] = Field(default_factory=list)
    channel: str
    status: str
    captured_by_user_id: UUID | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime