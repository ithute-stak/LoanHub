from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class MaturityRenewalPolicyRead(BaseModel):
    id: UUID
    company_id: UUID
    enabled: bool
    rollover_basis: str
    reuse_original_rate: bool
    renewal_rate_percent: Decimal | None
    reuse_original_term: bool
    renewal_term_months: int | None
    include_processing_fee: bool
    grace_days: int
    max_cycles: int | None
    notify_borrower: bool
    configured_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaturityRenewalPolicyUpdate(BaseModel):
    enabled: bool
    rollover_basis: str = Field(default="outstanding_balance", pattern=r"^outstanding_balance$")
    reuse_original_rate: bool = True
    renewal_rate_percent: Decimal | None = Field(default=None, ge=0, le=1000)
    reuse_original_term: bool = True
    renewal_term_months: int | None = Field(default=None, ge=1, le=120)
    include_processing_fee: bool = False
    grace_days: int = Field(default=0, ge=0, le=365)
    max_cycles: int | None = Field(default=None, ge=1, le=120)
    notify_borrower: bool = True

    @model_validator(mode="after")
    def validate_overrides(self):
        if not self.reuse_original_rate and self.renewal_rate_percent is None:
            raise ValueError("Set a renewal rate or reuse the original rate")
        if not self.reuse_original_term and self.renewal_term_months is None:
            raise ValueError("Set a renewal term or reuse the original term")
        return self


class StopLoanRenewalRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class LoanRenewalCycleRead(BaseModel):
    id: UUID
    company_id: UUID
    loan_id: UUID
    borrower_id: UUID
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
    previous_terms_snapshot: dict[str, Any]
    previous_schedule_snapshot: list[dict[str, Any]]
    calculation_breakdown: dict[str, Any]
    created_by_user_id: UUID | None

    model_config = {"from_attributes": True}
