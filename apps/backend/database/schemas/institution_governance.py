from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from database.models.enums import InstitutionType, UserRole


ReadinessState = Literal["complete", "attention", "not_applicable"]


class InstitutionGovernanceProfileUpdate(BaseModel):
    regulator_name: str | None = Field(default=None, max_length=200)
    regulatory_license_category: str | None = Field(default=None, max_length=160)
    license_expiry_date: date | None = None
    bank_code: str | None = Field(default=None, max_length=40)
    swift_bic: str | None = Field(default=None, max_length=20)

    aml_cft_officer_name: str | None = Field(default=None, max_length=200)
    aml_cft_officer_email: EmailStr | None = None
    data_protection_officer_name: str | None = Field(default=None, max_length=200)
    data_protection_officer_email: EmailStr | None = None
    regulatory_reporting_contact_email: EmailStr | None = None
    complaints_contact: str | None = Field(default=None, max_length=200)

    privacy_notice_url: str | None = Field(default=None, max_length=500)
    data_retention_months: int | None = Field(default=None, ge=1, le=120)
    consent_management_enabled: bool | None = None
    data_export_enabled: bool | None = None

    ai_decisioning_enabled: bool | None = None
    ai_human_review_required: bool | None = None
    ai_explainability_required: bool | None = None
    ai_bias_monitoring_enabled: bool | None = None

    govstack_interoperability_status: Literal[
        "not_started", "planned", "in_progress", "ready"
    ] | None = None
    dpg_readiness_status: Literal[
        "not_started", "assessment", "remediation", "ready_for_review"
    ] | None = None
    open_api_published: bool | None = None
    low_bandwidth_supported: bool | None = None
    accessibility_reviewed: bool | None = None
    english_sesotho_supported: bool | None = None
    business_continuity_tested: bool | None = None
    incident_response_tested: bool | None = None
    interoperability_notes: str | None = Field(default=None, max_length=5000)


class InstitutionGovernanceProfileRead(InstitutionGovernanceProfileUpdate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime


class InstitutionRoleRead(BaseModel):
    role: UserRole
    label: str
    scope: Literal["institution", "branch", "institution_or_branch"]
    purpose: str


class ReadinessControlRead(BaseModel):
    key: str
    category: str
    label: str
    state: ReadinessState
    required: bool
    detail: str


class InstitutionReadinessRead(BaseModel):
    company_id: UUID
    institution_type: InstitutionType
    score_percent: int
    completed_required_controls: int
    required_controls: int
    controls: list[ReadinessControlRead]
    assigned_roles: list[UserRole]
    missing_recommended_roles: list[UserRole]


class GovStackCapabilityRead(BaseModel):
    key: str
    label: str
    status: Literal["implemented", "integration_ready", "planned"]
    implementation: str
