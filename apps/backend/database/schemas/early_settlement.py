from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from database.models.enums import PaymentMethod
from database.schemas.cash import CashPaymentResult


class EarlySettlementQuoteCreate(BaseModel):
    settlement_date: date
    valid_for_days: int = Field(default=3, ge=1, le=7)


class EarlySettlementPayCreate(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CASH
    gateway_provider: str | None = Field(default=None, min_length=2, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    gateway_customer_phone: str | None = Field(default=None, min_length=8, max_length=20)
    borrower_acknowledged: bool
    agreement_note: str = Field(min_length=3, max_length=2000)
    agreement_reference: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)

    @model_validator(mode="after")
    def validate_payment_boundary(self):
        if self.payment_method not in {PaymentMethod.CASH, PaymentMethod.LELEFAPAYGATE}:
            raise ValueError("Early settlement supports only Cash or LelefaPayGate")
        if not self.borrower_acknowledged:
            raise ValueError("Borrower acknowledgement is required before early settlement")
        return self


class EarlySettlementRead(BaseModel):
    id: UUID
    company_id: UUID
    borrower_id: UUID
    loan_id: UUID
    payment_id: UUID | None
    quoted_by_user_id: UUID | None
    settled_by_user_id: UUID | None
    status: str
    settlement_date: date
    quote_expires_at: datetime
    calculation_method: str
    original_term_months: int
    chargeable_periods: int
    original_maturity_date: date | None
    original_principal: Decimal
    original_total_repayable: Decimal
    original_balance: Decimal
    original_amount_paid: Decimal
    original_total_interest: Decimal
    earned_interest: Decimal
    unearned_interest_rebate: Decimal
    processing_fee_retained: Decimal
    payments_received: Decimal
    revised_total_repayable: Decimal
    settlement_amount: Decimal
    settlement_principal: Decimal
    settlement_interest: Decimal
    settlement_fees: Decimal
    overpayment_credit: Decimal
    borrower_acknowledged: bool
    agreement_note: str | None
    agreement_reference: str | None
    calculation_snapshot: dict[str, Any]
    installment_snapshot: list[dict[str, Any]]
    settled_at: datetime | None
    reversed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EarlySettlementPaymentResult(BaseModel):
    settlement: EarlySettlementRead
    payment: CashPaymentResult
