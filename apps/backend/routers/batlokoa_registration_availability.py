"""Phase 90: authenticated, informational new-only registration availability.

This endpoint MUST NOT accept borrower PII or call any registration writer.
No production policy flag enables registration via this route. Existing
assisted-client endpoints are separate and unchanged.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

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
        or context.company_id is None
        or context.staff.company_id != context.company_id
        or context.staff.user_id != context.user.id
        or context.staff.role not in LENDING_ROLES
    ):
        raise HTTPException(status_code=403, detail="Active lending staff membership required")
    if (
        context.staff.role not in COMPANY_MANAGEMENT_ROLES
        and (context.branch_id is None or context.staff.branch_id != context.branch_id)
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


class RegistrationFormRequirementsRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
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


def registration_form_requirements_for_staff(
    context: TenantContext,
) -> RegistrationFormRequirementsRead:
    """Return static field metadata after the same staff access check.

    The form is informational and submit-disabled. No source accepts customer
    values; this cannot be used to register a borrower.
    """
    registration_availability_for_staff(context)
    return RegistrationFormRequirementsRead(sections=_FORM_SECTIONS)


@router.get("/form-requirements", response_model=RegistrationFormRequirementsRead)
def get_registration_form_requirements(
    context: TenantContext = Depends(get_tenant_context),
) -> RegistrationFormRequirementsRead:
    return registration_form_requirements_for_staff(context)
