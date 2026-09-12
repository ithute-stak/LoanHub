from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from database.models.enums import PaymentDirection, PaymentMethod, PaymentProvider


class BorrowerRequestFeeWrite(BaseModel):
    company_id: UUID | None = None
    name: str = Field(default="Borrow request service fee", min_length=3, max_length=160)
    fee_type: str = Field(default="flat", pattern="^(flat|percentage|hybrid)$")
    flat_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=10, decimal_places=6)
    minimum_amount: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    maximum_amount: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", pattern="^[A-Z]{3}$")
    required_before_submission: bool = True
    refundable: bool = False
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_amounts(self):
        if self.is_active and self.fee_type == "flat" and self.flat_amount <= 0:
            raise ValueError("An active flat fee must be greater than zero")
        if self.is_active and self.fee_type == "percentage" and self.percentage <= 0:
            raise ValueError("An active percentage fee must be greater than zero")
        if self.is_active and self.fee_type == "hybrid" and self.flat_amount <= 0 and self.percentage <= 0:
            raise ValueError("An active hybrid fee needs a flat amount or percentage")
        if self.minimum_amount is not None and self.maximum_amount is not None and self.minimum_amount > self.maximum_amount:
            raise ValueError("Minimum amount cannot exceed maximum amount")
        return self


class BorrowerRequestFeeRead(BorrowerRequestFeeWrite):
    id: UUID
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountOpeningFeeWrite(BaseModel):
    company_id: UUID | None = None
    name: str = Field(default="Assisted borrower account opening fee", min_length=3, max_length=160)
    fee_type: str = Field(default="flat", pattern="^(flat|percentage|hybrid)$")
    flat_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=10, decimal_places=6)
    minimum_amount: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    maximum_amount: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", pattern="^[A-Z]{3}$")
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_amounts(self):
        if self.is_active and self.fee_type == "flat" and self.flat_amount <= 0:
            raise ValueError("An active flat fee must be greater than zero")
        if self.is_active and self.fee_type == "percentage" and self.percentage <= 0:
            raise ValueError("An active percentage fee must be greater than zero")
        if self.is_active and self.fee_type == "hybrid" and self.flat_amount <= 0 and self.percentage <= 0:
            raise ValueError("An active hybrid fee needs a flat amount or percentage")
        if self.minimum_amount is not None and self.maximum_amount is not None and self.minimum_amount > self.maximum_amount:
            raise ValueError("Minimum amount cannot exceed maximum amount")
        return self


class AccountOpeningFeeRead(AccountOpeningFeeWrite):
    id: UUID
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionAgreementWrite(BaseModel):
    company_id: UUID
    name: str = Field(default="Platform cash transaction charge agreement", min_length=3, max_length=180)
    inbound_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=10, decimal_places=6)
    outbound_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=10, decimal_places=6)
    inbound_flat_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    outbound_flat_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=2)
    minimum_charge: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    maximum_charge: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", pattern="^[A-Z]{3}$")
    settlement_frequency: str = Field(default="monthly", pattern="^(daily|weekly|monthly|quarterly|custom)$")
    settlement_day: int | None = Field(default=None, ge=1, le=31)
    effective_from: date
    effective_to: date | None = None
    terms: str | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def validate_period(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("Effective-to date cannot be before effective-from")
        if self.minimum_charge is not None and self.maximum_charge is not None and self.minimum_charge > self.maximum_charge:
            raise ValueError("Minimum charge cannot exceed maximum charge")
        return self


class TransactionAgreementRead(TransactionAgreementWrite):
    id: UUID
    agreement_number: str
    status: str
    owner_accepted_by_user_id: UUID | None
    company_accepted_by_user_id: UUID | None
    owner_accepted_at: datetime | None
    company_accepted_at: datetime | None
    activated_at: datetime | None
    suspended_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgreementDecision(BaseModel):
    accept: bool = True
    reason: str | None = Field(default=None, max_length=1000)


class ChargeLedgerRead(BaseModel):
    id: UUID
    company_id: UUID
    agreement_id: UUID
    payment_id: UUID
    claim_id: UUID | None
    direction: PaymentDirection
    provider: PaymentProvider
    payment_purpose: str
    gross_amount: Decimal
    percentage_rate: Decimal
    flat_fee: Decimal
    charge_amount: Decimal
    currency: str
    status: str
    accrued_at: datetime
    claimed_at: datetime | None
    settled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChargeClaimCreate(BaseModel):
    company_id: UUID
    period_start: date
    period_end: date
    due_days: int = Field(default=14, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("Claim period end cannot be before its start")
        return self


class ChargeClaimRead(BaseModel):
    id: UUID
    company_id: UUID
    agreement_id: UUID
    claim_number: str
    period_start: date
    period_end: date
    transaction_count: int
    gross_transaction_value: Decimal
    amount: Decimal
    currency: str
    status: str
    issued_at: datetime | None
    due_at: datetime | None
    acknowledged_at: datetime | None
    paid_at: datetime | None
    disputed_at: datetime | None
    notes: str | None
    dispute_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClaimCompanyDecision(BaseModel):
    action: str = Field(pattern="^(acknowledge|dispute)$")
    reason: str | None = Field(default=None, max_length=2000)


class ClaimCashSettlementCreate(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CASH
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)
