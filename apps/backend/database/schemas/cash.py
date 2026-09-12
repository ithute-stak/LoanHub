from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from database.models.enums import LoanCalculationMethod, PaymentDirection, PaymentMethod
from database.schemas.file_management import ManagedFileRead


class LoanCalculationRequest(BaseModel):
    principal: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    rate_percent: Decimal = Field(ge=0, max_digits=8, decimal_places=4)
    months: int = Field(ge=1, le=120)
    processing_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    interest_method: LoanCalculationMethod = LoanCalculationMethod.MICRO_LOAN
    interest_start_date: date | None = None
    due_dates: list[date] | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_manual_due_dates(self):
        # Due dates are optional for calculator/API compatibility. When they are
        # omitted the shared calculation engine generates a monthly schedule from
        # interest_start_date. Offer/approval flows may still provide explicit
        # dates and those dates remain strictly validated here.
        if self.due_dates is None:
            return self
        if len(self.due_dates) != self.months:
            raise ValueError(f"Enter exactly {self.months} installment due dates")
        previous = self.interest_start_date or date.today()
        for index, due_date in enumerate(self.due_dates, start=1):
            if due_date <= previous:
                if index == 1:
                    raise ValueError("Installment 1 due date must be after the interest start date")
                raise ValueError(f"Installment {index} due date must be after installment {index - 1}")
            previous = due_date
        return self


class InterestSegmentRead(BaseModel):
    period_start: date
    period_end: date
    days: int
    days_in_month: int
    interest: Decimal


class LoanCalculationScheduleRowRead(BaseModel):
    installment_number: int
    period_start: date
    due_date: date
    opening_balance: Decimal
    principal_due: Decimal
    interest_due: Decimal
    fee_due: Decimal
    total_due: Decimal
    closing_balance: Decimal
    interest_segments: list[InterestSegmentRead] = Field(default_factory=list)


class LoanCalculationRead(BaseModel):
    method: LoanCalculationMethod
    method_label: str
    rate_basis: str
    principal: Decimal
    rate_percent: Decimal
    months: int
    processing_fee: Decimal
    interest_start_date: date
    first_payment_date: date
    maturity_date: date
    total_interest: Decimal
    total_repayable: Decimal
    monthly_installment: Decimal
    schedule_amounts: list[Decimal]
    schedule: list[LoanCalculationScheduleRowRead]
    steps: list[dict[str, Any]] = Field(default_factory=list)



class MicroLoanCalculationRequest(BaseModel):
    principal: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    rate_percent: Decimal = Field(ge=0, max_digits=8, decimal_places=4)
    months: int = Field(ge=1, le=120)
    processing_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)


class MicroLoanStep(BaseModel):
    month: int
    opening_balance: Decimal
    amount_after_rate: Decimal
    component_amount: Decimal
    carried_balance: Decimal


class MicroLoanCalculationRead(BaseModel):
    method: Literal["micro_loan"] = "micro_loan"
    principal: Decimal
    rate_percent: Decimal
    months: int
    processing_fee: Decimal
    total_repayable: Decimal
    monthly_installment: Decimal
    schedule_amounts: list[Decimal]
    steps: list[MicroLoanStep]


class CashDisbursementCreate(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CASH
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)


class CashRepaymentPreviewCreate(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CASH
    payment_date: date | None = None
    loan_reference: str = Field(min_length=8, max_length=100)
    amount_tendered: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    overpayment_action: Literal["give_change", "carry_forward"] = "carry_forward"
    installment_number: int | None = Field(default=None, ge=1)


class CashRepaymentCreate(CashRepaymentPreviewCreate):
    gateway_provider: str | None = Field(default=None, min_length=2, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    gateway_customer_phone: str | None = Field(default=None, min_length=8, max_length=20)
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)


class InstallmentPaymentCreate(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CASH
    payment_date: date | None = None
    gateway_provider: str | None = Field(default=None, min_length=2, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    gateway_customer_phone: str | None = Field(default=None, min_length=8, max_length=20)
    amount_tendered: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)


class CashRepaymentPreviewRead(BaseModel):
    loan_id: UUID
    loan_reference: str
    borrower_name: str
    current_installment_number: int
    current_due_date: date
    expected_monthly_installment: Decimal
    installment_outstanding_before: Decimal
    amount_tendered: Decimal
    amount_applied: Decimal
    change_amount: Decimal
    forward_amount: Decimal
    installment_outstanding_after: Decimal
    loan_balance_before: Decimal
    loan_balance_after: Decimal
    installments_fully_covered: int
    payment_completes_loan: bool
    early_settlement_required: bool
    future_installments_in_payoff: int


class CashTransactionRead(BaseModel):
    id: UUID
    payment_id: UUID
    branch_id: UUID | None
    handled_by_user_id: UUID | None
    direction: PaymentDirection
    cash_reference: str
    tendered_amount: Decimal
    applied_amount: Decimal
    change_amount: Decimal
    forward_amount: Decimal
    installment_number: int | None
    expected_installment_amount: Decimal | None
    installment_outstanding_before: Decimal | None
    installment_outstanding_after: Decimal | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CashPaymentResult(BaseModel):
    payment_id: UUID
    payment_method: PaymentMethod
    status: str = "succeeded"
    provider_reference: str
    proof_reference: str | None = None
    receipt_number: str | None = None
    receipt_file: ManagedFileRead | None = None
    cash_transaction: CashTransactionRead | None = None
    preview: CashRepaymentPreviewRead | None = None


class CashBorrowerRequestFeeCreate(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CASH
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)
