from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from database.models.enums import InstallmentStatus, LoanStatus, RepaymentType, RiskLevel


class InstallmentDueDateAdjustmentCreate(BaseModel):
    new_due_date: date
    agreement_note: str = Field(min_length=3, max_length=1000)
    agreement_reference: str | None = Field(default=None, max_length=160)


class RepaymentInstallmentRead(BaseModel):
    id: UUID
    renewal_cycle_id: UUID | None = None
    superseded_by_cycle_id: UUID | None = None
    is_superseded: bool = False
    superseded_at: datetime | None = None
    installment_number: int
    due_date: date
    principal_due: Decimal
    interest_due: Decimal
    fee_due: Decimal
    total_due: Decimal
    paid_amount: Decimal
    status: InstallmentStatus
    paid_at: datetime | None

    model_config = {"from_attributes": True}


class LoanRenewalCycleRead(BaseModel):
    id: UUID
    cycle_number: int
    status: str
    automatic: bool
    opening_balance: Decimal
    rollover_basis: str
    rate_percent: Decimal
    processing_fee: Decimal
    term_months: int
    calculation_method: str
    installment_amount: Decimal
    total_repayable: Decimal
    started_on: date
    maturity_date: date
    rolled_at: datetime

    model_config = {"from_attributes": True}


class LoanRead(BaseModel):
    id: UUID
    loan_request_id: UUID | None
    loan_offer_id: UUID | None
    company_id: UUID
    branch_id: UUID | None
    borrower_id: UUID
    loan_reference: str
    origination_channel: str
    is_top_up: bool = False
    parent_loan_id: UUID | None = None
    top_up_settlement_amount: Decimal = Decimal("0")
    top_up_cash_amount: Decimal = Decimal("0")
    principal_amount: Decimal
    interest_rate: Decimal
    processing_fee: Decimal
    total_repayable: Decimal
    repayment_type: RepaymentType
    repayment_period: int
    installment_amount: Decimal
    calculation_method: str
    calculation_breakdown: dict[str, Any]
    approved_at: datetime | None
    disbursed_at: datetime | None
    first_payment_due: date | None
    maturity_date: date | None
    amount_paid: Decimal
    balance: Decimal
    status: LoanStatus
    risk_level: RiskLevel
    is_overdue: bool
    automatic_renewal_enabled: bool | None = None
    renewal_cycle_count: int = 0
    original_maturity_date: date | None = None
    last_renewed_at: datetime | None = None
    renewal_stopped_at: datetime | None = None
    renewal_stop_reason: str | None = None
    installments: list[RepaymentInstallmentRead] = []
    renewal_cycles: list[LoanRenewalCycleRead] = []

    model_config = {"from_attributes": True}


class LoanPaymentSlipRead(BaseModel):
    id: UUID
    payment_id: UUID
    receipt_number: str
    payment_purpose: str
    payment_method: str
    amount: Decimal
    provider_reference: str | None
    verification_code: str
    completed_at: datetime | None
    pdf_file_id: UUID | None
