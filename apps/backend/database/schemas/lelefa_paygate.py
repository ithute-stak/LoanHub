from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class BorrowerGatewayCheckoutCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)


class BorrowerGatewayCheckoutRead(BaseModel):
    payment_id: UUID
    status: str
    amount: Decimal
    currency: str
    checkout_url: str


class BorrowerSettlementQuoteCreate(BaseModel):
    settlement_date: date
    valid_for_days: int = Field(default=3, ge=1, le=7)


class BorrowerSettlementCheckoutCreate(BaseModel):
    borrower_acknowledged: bool
    agreement_note: str = Field(min_length=3, max_length=2000)
    agreement_reference: str | None = Field(default=None, max_length=160)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)

    @model_validator(mode="after")
    def require_acknowledgement(self):
        if not self.borrower_acknowledged:
            raise ValueError("Borrower acknowledgement is required")
        return self


class LelefaPayGateConfigurationRead(BaseModel):
    enabled: bool
    effective_enabled: bool
    environment: str
    base_url: str
    api_key_configured: bool
    api_key_hint: str | None = None
    webhook_secret_configured: bool
    request_signing_enabled: bool
    timeout_seconds: float
    webhook_tolerance_seconds: int
    collection_provider: str
    payout_provider: str
    updated_at: datetime | None = None


class LelefaPayGateConfigurationUpdate(BaseModel):
    enabled: bool = False
    base_url: str = Field(min_length=8, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    webhook_secret: str | None = Field(default=None, max_length=1000)
    clear_api_key: bool = False
    clear_webhook_secret: bool = False
    request_signing_enabled: bool = True
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    webhook_tolerance_seconds: int = Field(default=300, ge=30, le=900)
    collection_provider: str = Field(default="mpesa", min_length=1, max_length=50)
    payout_provider: str = Field(default="mpesa", min_length=1, max_length=50)
