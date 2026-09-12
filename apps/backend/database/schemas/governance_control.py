from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class DecisionRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class GatewayAdjustmentConfirmation(BaseModel):
    provider_reference: str = Field(min_length=5, max_length=180)


class PaymentAdjustmentCreate(BaseModel):
    payment_id: UUID
    adjustment_type: str = Field(pattern=r"^(refund|reversal|chargeback)$")
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    reason: str = Field(min_length=10, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=180)


class AccountingPeriodCreate(BaseModel):
    period_start: date
    period_end: date


class AccountingPeriodAction(BaseModel):
    note: str = Field(min_length=5, max_length=2000)


class BankStatementLineCreate(BaseModel):
    account_reference: str | None = Field(default=None, max_length=180)
    transaction_date: date
    description: str = Field(min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=180)
    amount: Decimal = Field(max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", min_length=3, max_length=3)


class BankStatementMatch(BaseModel):
    payment_id: UUID


class GuarantorCreate(BaseModel):
    loan_id: UUID
    guarantor_borrower_id: UUID | None = None
    full_name: str = Field(min_length=3, max_length=240)
    national_id: str = Field(min_length=5, max_length=80)
    phone: str = Field(min_length=8, max_length=30)
    relationship_to_borrower: str = Field(min_length=2, max_length=100)
    guaranteed_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    consent_obtained: bool = False


class GuarantorVerify(BaseModel):
    verification_status: str = Field(pattern=r"^(verified|rejected)$")


class CollateralCreate(BaseModel):
    loan_id: UUID
    collateral_type: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=5, max_length=2000)
    ownership_reference: str | None = Field(default=None, max_length=180)
    estimated_value: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    forced_sale_value: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", min_length=3, max_length=3)
    valuation_date: date | None = None


class ComplaintCreate(BaseModel):
    company_id: UUID | None = None
    loan_id: UUID | None = None
    category: str = Field(min_length=2, max_length=80)
    subject: str = Field(min_length=5, max_length=240)
    description: str = Field(min_length=10, max_length=5000)
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|urgent)$")


class ComplaintUpdate(BaseModel):
    status: str = Field(pattern=r"^(open|acknowledged|investigating|resolved|closed)$")
    resolution: str | None = Field(default=None, max_length=5000)
    assigned_to_user_id: UUID | None = None


class DataRightsCreate(BaseModel):
    request_type: str = Field(pattern=r"^(access|correction|portability|restriction|objection|deletion)$")
    description: str | None = Field(default=None, max_length=5000)


class DataRightsComplete(BaseModel):
    decision: str = Field(min_length=10, max_length=5000)
