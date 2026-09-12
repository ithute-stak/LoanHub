from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from database.models.enums import LoanCalculationMethod


class LoanProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    min_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    max_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    min_term_months: int = Field(gt=0, le=120)
    max_term_months: int = Field(gt=0, le=120)
    interest_method: LoanCalculationMethod = LoanCalculationMethod.MICRO_LOAN
    interest_rate_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    processing_fee: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.max_amount < self.min_amount:
            raise ValueError("Maximum amount must be greater than or equal to minimum amount")
        if self.max_term_months < self.min_term_months:
            raise ValueError("Maximum term must be greater than or equal to minimum term")
        return self


class LoanProductCreate(LoanProductBase):
    company_id: UUID | None = None


class LoanProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    min_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    max_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_term_months: int | None = Field(default=None, gt=0, le=120)
    max_term_months: int | None = Field(default=None, gt=0, le=120)
    interest_method: LoanCalculationMethod | None = None
    interest_rate_percent: Decimal | None = Field(default=None, ge=0, le=100)
    processing_fee: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class LoanProductRead(LoanProductBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
