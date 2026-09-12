from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


BORROWER_SERVICE_REQUEST_TYPES = {
    "settlement_quote",
    "payment_arrangement",
    "change_payment_date",
    "top_up",
    "refinance",
    "consolidation",
    "early_repayment",
    "payment_allocation_dispute",
    "balance_dispute",
    "hardship",
    "paid_up_letter",
    "statement",
    "update_payment_account",
}

BORROWER_SERVICE_REQUEST_STATUSES = {
    "submitted",
    "under_review",
    "approved",
    "declined",
    "completed",
    "cancelled",
}


class BorrowerServiceRequestCreate(BaseModel):
    request_type: str
    loan_id: UUID | None = None
    company_id: UUID | None = None
    subject: str | None = Field(default=None, max_length=180)
    details: str | None = Field(default=None, max_length=4000)
    requested_value: Decimal | None = Field(default=None, ge=0)

    @field_validator("request_type")
    @classmethod
    def validate_request_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in BORROWER_SERVICE_REQUEST_TYPES:
            raise ValueError("Unsupported borrower service request type")
        return normalized

    @field_validator("subject", "details")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class BorrowerServiceRequestCompanyUpdate(BaseModel):
    status: str
    company_response: str | None = Field(default=None, max_length=5000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in BORROWER_SERVICE_REQUEST_STATUSES - {"cancelled"}:
            raise ValueError("Unsupported borrower service request status")
        return normalized

    @field_validator("company_response")
    @classmethod
    def clean_response(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class BorrowerConsentUpdate(BaseModel):
    consent_to_share_profile: bool | None = None
    consent_to_credit_checks: bool | None = None
