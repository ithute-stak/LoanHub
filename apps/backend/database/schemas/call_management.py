from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


CALL_OUTCOMES = {
    "payment_made",
    "payment_promise",
    "client_unavailable",
    "wrong_number",
    "dispute",
    "refused_to_pay",
    "callback_requested",
    "information_provided",
    "other",
}


class DeviceRegistrationRequest(BaseModel):
    device_uuid: str = Field(min_length=8, max_length=160)
    device_name: str | None = Field(default=None, max_length=180)
    platform: str = Field(default="android", max_length=40)
    os_version: str | None = Field(default=None, max_length=80)
    app_version: str | None = Field(default=None, max_length=80)


class CallCreateRequest(BaseModel):
    device_call_uuid: str = Field(min_length=8, max_length=120)
    phone_number: str = Field(min_length=5, max_length=40)
    direction: str
    started_at: datetime
    borrower_id: UUID | None = None
    loan_id: UUID | None = None
    device_id: UUID | None = None
    status: str = "started"

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"incoming", "outgoing"}:
            raise ValueError("direction must be incoming or outgoing")
        return normalized

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"started", "ringing", "answered", "completed", "missed", "failed", "cancelled"}:
            raise ValueError("Unsupported call status")
        return normalized


class CallUpdateRequest(BaseModel):
    status: str | None = None
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    outcome: str | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"started", "ringing", "answered", "completed", "missed", "failed", "cancelled"}:
            raise ValueError("Unsupported call status")
        return normalized

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().lower()
        if normalized not in CALL_OUTCOMES:
            raise ValueError("Unsupported call outcome")
        return normalized


class CallDescriptionUpdateRequest(BaseModel):
    """The employee's own factual description of their call."""

    description: str | None = Field(default=None, max_length=5000)


class CallManagementPolicyUpdate(BaseModel):
    recording_enabled: bool
    recording_retention_days: int = Field(ge=1, le=3650)
    call_metadata_retention_months: int = Field(ge=1, le=120)
    automatic_deletion_enabled: bool
    live_monitoring_enabled: bool
    manager_downloads_enabled: bool
    legal_hold_enabled: bool
    recording_notice: str | None = Field(default=None, max_length=2000)


class SipPolicyUpdate(BaseModel):
    outbound_trunk_id: str | None = Field(default=None, max_length=160)
    caller_number: str | None = Field(default=None, max_length=40)

    @field_validator("outbound_trunk_id", "caller_number")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LegalHoldCreateRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class LiveMediaTokenRequest(BaseModel):
    purpose: str = "employee_call"


class CallQualityReviewRequest(BaseModel):
    score: int = Field(ge=0, le=100)
    compliance_status: str = Field(default="not_assessed", max_length=40)
    customer_care_status: str = Field(default="not_assessed", max_length=40)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("compliance_status", "customer_care_status")
    @classmethod
    def validate_review_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"not_assessed", "pass", "needs_improvement", "fail"}:
            raise ValueError("Review status must be not_assessed, pass, needs_improvement or fail")
        return normalized
