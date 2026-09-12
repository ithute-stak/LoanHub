from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_user_context
from database.config.config import settings
from database.models.enums import (
    PaymentDirection,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
)
from database.models.payment import PaymentTransaction
from database.session import get_db
from services.realtime_event_service import build_realtime_event, emit_realtime_event


router = APIRouter(prefix="/loanhub-money", tags=["LoanHub Money"])

TransferType = Literal["c2c", "c2b", "b2c", "b2b"]


class MoneyTransferCreate(BaseModel):
    transfer_type: TransferType
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", min_length=3, max_length=3)
    counterparty_phone: str | None = Field(default=None, max_length=30)
    counterparty_reference: str | None = Field(default=None, max_length=180)
    note: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=120)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("counterparty_phone", "counterparty_reference", "note")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class MoneyTransferRead(BaseModel):
    id: str
    transfer_type: TransferType
    amount: Decimal
    currency: str
    status: str
    provider: str
    payer_phone: str | None
    payee_phone: str | None
    counterparty_reference: str | None
    note: str | None
    settlement_ready: bool
    created_at: str | None


def _is_business_origin(context: TenantContext) -> bool:
    return bool(context.company_id)


def _validate_transfer_scope(context: TenantContext, payload: MoneyTransferCreate) -> None:
    business_origin = _is_business_origin(context)
    if payload.transfer_type in {"b2c", "b2b"} and not business_origin and not context.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="B2C and B2B transfers require an active LoanHub business context.",
        )
    if payload.transfer_type in {"c2c", "c2b"} and business_origin:
        # Company users can still use consumer transfers only when they switch
        # to a personal/borrower session. This avoids silently spending company funds.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Switch to a personal LoanHub context for C2C or C2B transfers.",
        )
    if not payload.counterparty_phone and not payload.counterparty_reference:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide a counterparty phone number or LoanHub reference.",
        )


def _transfer_payload(row: PaymentTransaction) -> MoneyTransferRead:
    provider_payload = row.provider_payload or {}
    return MoneyTransferRead(
        id=str(row.id),
        transfer_type=provider_payload.get("transfer_type", "c2c"),
        amount=row.amount,
        currency=row.currency,
        status=row.status.value,
        provider=row.provider.value,
        payer_phone=row.payer_phone,
        payee_phone=row.payee_phone,
        counterparty_reference=provider_payload.get("counterparty_reference"),
        note=provider_payload.get("note"),
        settlement_ready=bool(settings.LELEFAPAYGATE_ENABLED),
        created_at=row.created_at.isoformat() if getattr(row, "created_at", None) else None,
    )


@router.get("/configuration")
def money_configuration(
    context: TenantContext = Depends(get_user_context),
):
    return {
        "currency": "LSL",
        "supported_transfer_types": ["c2c", "c2b", "b2c", "b2b"],
        "provider": "lelefapaygate",
        "provider_enabled": bool(settings.LELEFAPAYGATE_ENABLED),
        "business_context": bool(context.company_id),
        "company_id": str(context.company_id) if context.company_id else None,
        "settlement_mode": "provider_backed",
        "message": (
            "LoanHub Money is ready to submit provider-backed transfer instructions."
            if settings.LELEFAPAYGATE_ENABLED
            else "LoanHub Money is in transfer-intent mode until LelefaPayGate is configured."
        ),
    }


@router.get("/transfers", response_model=list[MoneyTransferRead])
def list_money_transfers(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    visibility = [PaymentTransaction.initiated_by_user_id == context.user.id]
    if context.user.phone:
        visibility.append(PaymentTransaction.payee_phone == context.user.phone)

    query = db.query(PaymentTransaction).filter(
        PaymentTransaction.purpose == PaymentPurpose.BUSINESS_PAYMENT,
        PaymentTransaction.provider_operation == "loanhub_money_transfer",
        or_(*visibility),
    )
    if context.company_id:
        query = query.filter(PaymentTransaction.company_id == context.company_id)
    rows = query.order_by(PaymentTransaction.created_at.desc()).limit(limit).all()
    return [_transfer_payload(row) for row in rows]


@router.post(
    "/transfers",
    response_model=MoneyTransferRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_money_transfer(
    payload: MoneyTransferCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _validate_transfer_scope(context, payload)

    key = payload.idempotency_key or uuid.uuid4().hex
    idempotency_key = f"loanhub-money:{context.user.id}:{key}"
    existing = db.query(PaymentTransaction).filter(
        PaymentTransaction.idempotency_key == idempotency_key
    ).first()
    if existing:
        return _transfer_payload(existing)

    outgoing = payload.transfer_type in {"c2c", "c2b", "b2c", "b2b"}
    payer_phone = context.user.phone if outgoing else payload.counterparty_phone
    payee_phone = payload.counterparty_phone if outgoing else context.user.phone

    row = PaymentTransaction(
        company_id=context.company_id,
        initiated_by_user_id=context.user.id,
        provider=PaymentProvider.LELEFAPAYGATE,
        payment_method=PaymentMethod.LELEFAPAYGATE,
        direction=PaymentDirection.OUTBOUND,
        purpose=PaymentPurpose.BUSINESS_PAYMENT,
        status=PaymentStatus.PENDING,
        amount=payload.amount,
        currency=payload.currency,
        payer_phone=payer_phone,
        payee_phone=payee_phone,
        provider_operation="loanhub_money_transfer",
        idempotency_key=idempotency_key,
        provider_payload={
            "transfer_type": payload.transfer_type,
            "counterparty_reference": payload.counterparty_reference,
            "note": payload.note,
            "settlement_requested": bool(settings.LELEFAPAYGATE_ENABLED),
            "settlement_state": (
                "provider_dispatch_pending"
                if settings.LELEFAPAYGATE_ENABLED
                else "awaiting_provider_configuration"
            ),
        },
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    await emit_realtime_event(
        [context.user.id],
        build_realtime_event(
            "MONEY_TRANSFER_CREATED",
            domain="money",
            entity_id=row.id,
            data={
                "transfer": _transfer_payload(row).model_dump(mode="json"),
            },
        ),
    )
    return _transfer_payload(row)
