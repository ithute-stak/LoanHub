from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class BorrowerMandateCreate(BaseModel):
    loan_id: UUID
    provider: Literal["mpesa"] = "mpesa"
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    first_debit_date: date
    expiry_date: date | None = None
    consent_reference: str = Field(min_length=6, max_length=160)
    borrower_authorized: bool

    @model_validator(mode="after")
    def require_authorization(self):
        if not self.borrower_authorized:
            raise ValueError("Explicit borrower authorization is required")
        if self.first_debit_date < date.today():
            raise ValueError("first_debit_date cannot be in the past")
        if self.expiry_date and self.expiry_date < self.first_debit_date:
            raise ValueError("expiry_date must not be before the first debit")
        return self


class ReminderPreferenceUpdate(BaseModel):
    in_app_enabled: bool = True
    sms_enabled: bool = False
    email_enabled: bool = False
    whatsapp_enabled: bool = False
    days_before_due: int = Field(default=3, ge=0, le=30)
    remind_on_due_date: bool = True
    overdue_interval_days: int = Field(default=3, ge=1, le=30)
    payment_link_enabled: bool = True
    timezone: str = Field(default="Africa/Maseru", min_length=3, max_length=80)


class RestructureRequestCreate(BaseModel):
    loan_id: UUID
    requested_term_months: int = Field(ge=1, le=120)
    payment_holiday_days: int = Field(default=0, ge=0, le=90)
    reason: str = Field(min_length=10, max_length=2000)
    borrower_accepted: bool = True

    @model_validator(mode="after")
    def require_acceptance(self):
        if not self.borrower_accepted:
            raise ValueError("Borrower acceptance is required before requesting a restructure")
        return self


class RestructureApprovalCreate(BaseModel):
    approved_rate_percent: Decimal | None = Field(default=None, ge=0, le=100)
    agreement_reference: str = Field(min_length=4, max_length=160)


class AccountingExportCreate(BaseModel):
    period_start: date
    period_end: date
    format: Literal["json", "csv"] = "json"
    destination: Literal["manual", "accounting_adapter"] = "manual"

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must not be before period_start")
        if (self.period_end - self.period_start).days > 366:
            raise ValueError("An accounting export cannot exceed 366 days")
        return self
