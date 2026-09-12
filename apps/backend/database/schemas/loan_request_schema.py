from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from database.models.enums import LoanRequestStatus


class LoanRequestBase(BaseModel):
    requested_amount: Decimal = Field(..., gt=0)

    preferred_term_months: Optional[int] = Field(default=None, gt=0, le=120)
    loan_purpose: Optional[str] = Field(default=None, max_length=500)

    visible_to_lenders: bool = True
    allow_lenders_to_call: bool = True


class LoanRequestCreate(LoanRequestBase):
    pass


class LoanRequestUpdate(BaseModel):
    requested_amount: Optional[Decimal] = Field(default=None, gt=0)
    preferred_term_months: Optional[int] = Field(default=None, gt=0, le=120)
    loan_purpose: Optional[str] = Field(default=None, max_length=500)

    visible_to_lenders: Optional[bool] = None
    allow_lenders_to_call: Optional[bool] = None

    status: Optional[LoanRequestStatus] = None


class LoanRequestResponse(LoanRequestBase):
    id: UUID
    borrower_id: UUID
    status: LoanRequestStatus

    selected_offer_id: Optional[UUID]
    origination_channel: str
    captured_by_user_id: Optional[UUID]
    service_fee_amount: Decimal
    service_fee_currency: str
    service_fee_status: str
    service_fee_payment_id: Optional[UUID]
    submitted_at: Optional[datetime]
    expires_at: Optional[datetime]
    accepted_at: Optional[datetime]

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
