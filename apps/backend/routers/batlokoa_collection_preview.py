"""Tenant-authenticated, disabled-by-default Batlokoa collection preview.

This route never initiates collections, payouts, or repayments.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.session import get_db
from services.batlokoa_collection_preview_orchestration import (
    prepare_verified_batlokoa_collection_preview,
)

router = APIRouter(prefix="/loans", tags=["Batlokoa Collection Preview"])


class BatlokoaPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    idempotency_key: str = Field(min_length=16, max_length=128)


@router.post("/{loan_id}/batlokoa/collection-preview")
def readonly_collection_preview(
    loan_id: UUID,
    payload: BatlokoaPreviewInput,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    return prepare_verified_batlokoa_collection_preview(
        db=db,
        context=context,
        loan_id=loan_id,
        amount=payload.amount,
        idempotency_key=payload.idempotency_key,
    )
