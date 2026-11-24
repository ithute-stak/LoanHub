"""Phase 90: authenticated, informational new-only registration availability.

This endpoint MUST NOT accept borrower PII or call any registration writer.
No production policy flag enables registration via this route. Existing
assisted-client endpoints are separate and unchanged.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from database.models.enums import CompanyStatus

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_tenant_context,
)


router = APIRouter(prefix="/batlokoa/registration", tags=["Batlokoa Registration"])


class RegistrationAvailabilityRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    new_only_registration_available: bool = False
    can_submit_new_only_registration: bool = False
    requires_identity_migration_approval: bool = True
    requires_independent_release_approval: bool = True
    reason_code: str = "NEW_ONLY_REGISTRATION_NOT_RELEASED"


def registration_availability_for_staff(context: TenantContext) -> RegistrationAvailabilityRead:
    """Return a constant non-activating status after tenant membership checks.

    This is an informational screen hint, NOT a transaction authorization
    decision. Future writes must reverify persisted staff, active branch,
    global identities and DB indexes within their own transaction.
    """
    if (
        not isinstance(context, TenantContext)
        or context.is_platform_admin
        or context.staff is None
        or context.user.is_active is not True
        or context.staff.is_active is not True
        or not isinstance(context.company_id, UUID)
        or not isinstance(context.user.id, UUID)
        or context.company is None
        or context.company.id != context.company_id
        or context.company.status != CompanyStatus.APPROVED
        or context.company.is_active is not True
        or context.staff.company_id != context.company_id
        or context.staff.user_id != context.user.id
        or context.staff.role not in LENDING_ROLES
    ):
        raise HTTPException(status_code=403, detail="Active lending staff membership required")
    if (
        context.staff.role not in COMPANY_MANAGEMENT_ROLES
        and (
            not isinstance(context.branch_id, UUID)
            or context.staff.branch_id != context.branch_id
        )
    ):
        raise HTTPException(status_code=403, detail="Assigned lending branch required")
    return RegistrationAvailabilityRead()


@router.get("/availability", response_model=RegistrationAvailabilityRead)
def get_registration_availability(
    context: TenantContext = Depends(get_tenant_context),
) -> RegistrationAvailabilityRead:
    return registration_availability_for_staff(context)


class RegistrationFormSectionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    fields: tuple[str, ...]
    deferred_fields: tuple[str, ...] = ()


class RegistrationFieldRequirementRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    kind: str
    required: bool
    deferred: bool
    sensitive: bool


class RegistrationFormRequirementsRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 2
    identity_alternatives: tuple[str, ...] = ("national_id", "passport_number")
    field_details: tuple[RegistrationFieldRequirementRead, ...] = ()
    registration_available: bool = False
    submit_allowed: bool = False
    client_data_requested: bool = False
    sections: tuple[RegistrationFormSectionRead, ...]


# These are keys only, never borrower values. All full-capture fields must
# appear in exactly one section. A deferred field must not be rendered as
# a data-entry control or submitted to the protected new-only writer.
_FORM_SECTIONS = (
    RegistrationFormSectionRead(
        id="identity", title="Identity and contact",
        fields=(
            "branch_id", "first_name", "middle_name", "last_name", "gender",
            "date_of_birth", "national_id", "passport_number", "nationality",
            "marital_status", "phone", "email", "temporary_password",
        ),
        deferred_fields=("email", "temporary_password"),
    ),
    RegistrationFormSectionRead(
        id="residence", title="Residence",
        fields=("district", "town_or_village", "physical_address"),
    ),
    RegistrationFormSectionRead(
        id="employment", title="Employment and income",
        fields=(
            "employment_status", "employment_type", "employer_name",
            "employer_group_id", "new_employer_group",
            "cdas_employee_number", "income_day", "job_title",
            "monthly_income", "salary_date",
        ),
        deferred_fields=(
            "employer_group_id", "new_employer_group", "cdas_employee_number",
        ),
    ),
    RegistrationFormSectionRead(
        id="obligations", title="Banking and other obligations",
        fields=(
            "has_existing_loans", "existing_loan_total",
            "external_debts", "bank_account",
        ),
    ),
    RegistrationFormSectionRead(
        id="consent", title="Client consent",
        fields=("consent_to_share_profile", "consent_to_credit_checks"),
    ),
)


# Presentation metadata is descriptive only and cannot authorize saving data.
# Keep these keys synchronized with FullNewOnlyClientCapture through tests.
_FIELD_KIND_GROUPS: dict[str, tuple[str, ...]] = {
    "select": (
        "gender", "marital_status", "employment_status",
    ),
    "date": ("date_of_birth",),
    "boolean": (
        "has_existing_loans", "consent_to_share_profile",
        "consent_to_credit_checks",
    ),
    "currency": ("monthly_income", "existing_loan_total"),
    "integer": ("income_day",),
    "email": ("email",),
    "password": ("temporary_password",),
    "uuid": ("branch_id", "employer_group_id"),
    "debt_list": ("external_debts",),
    "bank_account": ("bank_account",),
    "employer_group": ("new_employer_group",),
}
_FIELD_KINDS = {
    key: kind for kind, keys in _FIELD_KIND_GROUPS.items() for key in keys
}
_EXPLICIT_REQUIRED = frozenset({
    "branch_id", "first_name", "last_name", "phone",
    "gender", "date_of_birth", "district", "employment_status",
    "consent_to_share_profile", "consent_to_credit_checks",
})
# Required identity is a CROSS-FIELD rule: national_id OR passport_number.
_IDENTITY_ALTERNATIVES = ("national_id", "passport_number")
_SENSITIVE_FIELDS = frozenset({
    "national_id", "passport_number", "date_of_birth", "phone",
    "email", "temporary_password", "physical_address",
    "monthly_income", "existing_loan_total", "external_debts",
    "bank_account", "cdas_employee_number",
})


def _form_field_details() -> tuple[RegistrationFieldRequirementRead, ...]:
    from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture

    keys = tuple(key for section in _FORM_SECTIONS for key in section.fields)
    if len(keys) != len(set(keys)) or set(keys) != set(FullNewOnlyClientCapture.model_fields):
        # Fail closed if the backend model changes without a reviewed form plan.
        raise RuntimeError("Registration form field inventory requires review")
    deferred = {
        key for section in _FORM_SECTIONS for key in section.deferred_fields
    }
    if not deferred.issubset(set(keys)):
        raise RuntimeError("Invalid deferred registration field inventory")
    return tuple(
        RegistrationFieldRequirementRead(
            key=key,
            kind=_FIELD_KINDS.get(key, "text"),
            required=key in _EXPLICIT_REQUIRED,
            deferred=key in deferred,
            sensitive=key in _SENSITIVE_FIELDS,
        )
        for key in keys
    )


def registration_form_requirements_for_staff(
    context: TenantContext,
) -> RegistrationFormRequirementsRead:
    """Return static field metadata after the same staff access check.

    The form is informational and submit-disabled. No source accepts customer
    values; this cannot be used to register a borrower.
    """
    registration_availability_for_staff(context)
    return RegistrationFormRequirementsRead(
        sections=_FORM_SECTIONS,
        field_details=_form_field_details(),
        identity_alternatives=_IDENTITY_ALTERNATIVES,
    )


@router.get("/form-requirements", response_model=RegistrationFormRequirementsRead)
def get_registration_form_requirements(
    context: TenantContext = Depends(get_tenant_context),
) -> RegistrationFormRequirementsRead:
    return registration_form_requirements_for_staff(context)
