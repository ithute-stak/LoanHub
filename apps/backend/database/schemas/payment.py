from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from database.models.enums import PaymentDirection, PaymentMethod, PaymentProvider, PaymentPurpose, PaymentStatus
from database.schemas.cash import CashTransactionRead


class PaymentTransactionRead(BaseModel):
    id: UUID
    company_id: UUID | None
    borrower_id: UUID | None
    loan_request_id: UUID | None
    loan_id: UUID | None
    direct_application_id: UUID | None
    initiated_by_user_id: UUID | None
    provider: PaymentProvider
    payment_method: PaymentMethod
    direction: PaymentDirection
    purpose: PaymentPurpose
    status: PaymentStatus
    amount: Decimal
    currency: str
    idempotency_key: str
    provider_reference: str | None
    proof_reference: str | None
    proof_url: str | None
    proof_notes: str | None
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    provider_payload: dict[str, Any]
    failure_reason: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    cash_transaction: CashTransactionRead | None = None

    model_config = {"from_attributes": True}
