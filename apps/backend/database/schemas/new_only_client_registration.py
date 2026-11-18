"""Strict draft contract for the future Batlokoa staff new-client workflow.

Not connected to a router and never invokes a database writer. A separate
approval is required before any employee-facing endpoint is enabled.

Do not reuse the broad assisted-registration DTO for this initial pathway:
unknown or unsupported fields must be rejected, not silently discarded.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from database.models.enums import EmploymentStatus, Gender
from database.schemas.company_clients import AssistedCompanyClientCreate
from services.atomic_new_client_registration import _minimal_only


class StrictNewOnlyClientRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    branch_id: UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=8, max_length=30)
    gender: Gender
    date_of_birth: date
    national_id: str | None = Field(default=None, max_length=100)
    passport_number: str | None = Field(default=None, max_length=100)
    district: str = Field(min_length=1, max_length=100)
    employment_status: EmploymentStatus
    consent_to_share_profile: bool
    consent_to_credit_checks: bool

    @model_validator(mode="after")
    def validate_identity_and_age(self):
        if self.date_of_birth >= date.today():
            raise ValueError("Registration requires a date of birth in the past")
        if not any((identity or "").strip() for identity in (
            self.national_id, self.passport_number
        )):
            raise ValueError("National ID or passport number required")
        return self

    def to_internal_assisted_payload(self) -> AssistedCompanyClientCreate:
        """Explicitly map only supported fields, preserving all decisions.

        The protected write path must still independently validate
        staff authorization, existing identity conflicts, unique indexes
        and every transaction requirement.
        """
        assisted = AssistedCompanyClientCreate.model_validate(
            self.model_dump(mode="python")
        )
        _minimal_only(assisted)
        return assisted
