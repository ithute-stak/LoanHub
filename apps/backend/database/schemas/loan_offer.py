from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from database.models.enums import LoanCalculationMethod, OfferStatus


class LoanOfferBase(BaseModel):
    approved_amount: Decimal = Field(..., max_digits=12, decimal_places=2, gt=0)
    term_months: int = Field(..., gt=0)
    interest_rate_percent: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2, ge=0)
    processing_fee: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2, ge=0)
    calculation_method: LoanCalculationMethod = LoanCalculationMethod.MICRO_LOAN
    notes: Optional[str] = None


class LoanOfferCreate(LoanOfferBase):
    loan_request_id: UUID
    branch_id: Optional[UUID] = None
    installment_due_dates: list[date] = Field(min_length=1, max_length=120)

    @field_validator("approved_amount", "interest_rate_percent", "processing_fee")
    @classmethod
    def round_financials(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None:
            return round(v, 2)
        return v


class LoanOfferUpdate(BaseModel):
    approved_amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2, gt=0)
    term_months: Optional[int] = Field(None, gt=0)
    interest_rate_percent: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2, ge=0)
    processing_fee: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2, ge=0)
    calculation_method: LoanCalculationMethod | None = None
    installment_due_dates: list[date] | None = Field(default=None, min_length=1, max_length=120)
    notes: Optional[str] = None
    status: Optional[OfferStatus] = None


class LoanOfferResponse(LoanOfferBase):
    id: UUID
    loan_request_id: UUID
    company_id: UUID
    branch_id: Optional[UUID]
    offered_by_user_id: UUID
    monthly_repayment: Optional[Decimal]
    total_repayment: Optional[Decimal]
    calculation_breakdown: dict = Field(default_factory=dict)
    status: OfferStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
