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
