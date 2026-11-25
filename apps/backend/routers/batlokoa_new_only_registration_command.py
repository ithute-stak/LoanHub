"""Proposed Batlokoa new-only registration API — NOT included in api_router.

A future reviewed release must explicitly mount this router and replace the
non-activating release gate. Until then NO production client write is possible.
The request schema is lossless and the response never includes client PII.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from core.access_control import TenantContext, get_tenant_context
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from services.batlokoa_new_only_registration_command import (
    BatlokoaRegistrationNotReleased,
)

router = APIRouter(prefix="/batlokoa/registration", tags=["Batlokoa Registration"])


class NewOnlyClientReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    # Batlokoa's fail-closed Save Client parser requires explicit proof,
    # not merely an account UUID from an ambiguous response.
    registered: Literal[True] = True
    client_account_id: UUID
    replayed: bool


def _approved_production_release() -> bool:
    """Explicit deny: no environment variable, browser field or flag overrides it."""
    return False


@router.post(
    "/clients",
    response_model=NewOnlyClientReceipt,
    status_code=status.HTTP_201_CREATED,
)
def create_new_only_client(
    payload: FullNewOnlyClientCapture,
    context: TenantContext = Depends(get_tenant_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> NewOnlyClientReceipt:
    """Draft contract only — never mounted on the live API router.

    Authentication/tenant resolution remains a dependency even for a disabled
    endpoint. A future production implementation needs a dedicated session,
    independently approved migration and the validated command adapter.
    """
    if not _approved_production_release():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "NEW_ONLY_REGISTRATION_NOT_RELEASED"},
        )
    # In the draft the gate is permanently false. This explicit fallback
    # protects against accidental reassignment/mocking of the gate.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "NEW_ONLY_REGISTRATION_NOT_RELEASED"},
    )
