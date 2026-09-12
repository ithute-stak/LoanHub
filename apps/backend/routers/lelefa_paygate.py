from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from core.access_control import (
    PLATFORM_FINANCE_ROLES,
    get_current_active_user,
    is_platform_role,
    resolve_tenant_context,
)
from database.config.config import settings
from database.models.client_loan_company import ClientCompanyLoan
from database.models.early_settlement import LoanEarlySettlement
from database.models.enums import LoanStatus, PaymentStatus, UserRole
from database.models.payment import PaymentTransaction
from database.models.user import User
from database.schemas.early_settlement import EarlySettlementRead
from database.schemas.lelefa_paygate import (
    BorrowerGatewayCheckoutCreate,
    BorrowerGatewayCheckoutRead,
    BorrowerSettlementCheckoutCreate,
    BorrowerSettlementQuoteCreate,
)
from database.schemas.payment import PaymentTransactionRead
from database.session import get_db
from integrations.lelefa_paygate import (
    LelefaPayGateClient,
    LelefaPayGateError,
    LelefaPayGateWebhookError,
    verify_webhook_signature,
)
from services.lelefa_paygate_service import (
    initiate_borrower_gateway_checkout,
    initiate_borrower_settlement_checkout,
    process_gateway_webhook,
    refresh_gateway_payment,
)
from services.early_settlement_service import quote_early_settlement
from services.loan_service import preview_cash_repayment
from services.payment_service import build_idempotency_key
from services.realtime_event_service import (
    build_realtime_event,
    emit_realtime_event,
    payment_recipient_user_ids,
)


router = APIRouter(prefix="/lelefapaygate", tags=["LelefaPayGate"])


@router.get("/configuration")
def gateway_configuration(
    current_user: User = Depends(get_current_active_user),
):
    return {
        "enabled": settings.LELEFAPAYGATE_ENABLED,
        "environment": (
            "test"
            if (settings.LELEFAPAYGATE_API_KEY or "").startswith("ipb_test_")
            else "live"
            if (settings.LELEFAPAYGATE_API_KEY or "").startswith("ipb_live_")
            else "unconfigured"
        ),
        "base_url": settings.LELEFAPAYGATE_BASE_URL,
        "request_signing": settings.LELEFAPAYGATE_REQUEST_SIGNING_ENABLED,
        "webhook_configured": bool(settings.LELEFAPAYGATE_WEBHOOK_SECRET),
        "collection_provider": settings.LELEFAPAYGATE_COLLECTION_PROVIDER,
        "payout_provider": settings.LELEFAPAYGATE_PAYOUT_PROVIDER,
    }


@router.get("/payment-methods")
def gateway_payment_methods(
    currency: str = "LSL",
    current_user: User = Depends(get_current_active_user),
):
    if not settings.LELEFAPAYGATE_ENABLED:
        raise HTTPException(status_code=503, detail="LelefaPayGate is not enabled for LoanHub")
    try:
        return LelefaPayGateClient().list_payment_methods(currency=currency)
    except LelefaPayGateError as exc:
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=f"Could not load LelefaPayGate payment methods: {exc.detail}",
        ) from exc


@router.post(
    "/borrower/loans/{loan_id}/checkout",
    response_model=BorrowerGatewayCheckoutRead,
)
def create_borrower_checkout(
    loan_id: UUID,
    payload: BorrowerGatewayCheckoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.BORROWER or not current_user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access is required")
    loan = db.get(ClientCompanyLoan, loan_id)
    if not loan or loan.borrower_id != current_user.borrower_profile.id:
        raise HTTPException(status_code=404, detail="Loan is not available to you")
    if loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="This loan is not accepting repayments")

    preview = preview_cash_repayment(
        loan,
        amount_tendered=payload.amount,
        overpayment_action="carry_forward",
        installment_number=None,
    )
    if preview["early_settlement_required"]:
        raise HTTPException(
            status_code=409,
            detail=(
                "This amount would settle future instalments using full-term interest. "
                "Request an early-settlement quote so unearned interest is rebated."
            ),
        )
    amount = preview["amount_applied"]
    key = build_idempotency_key(
        "borrower-checkout",
        loan.id,
        payload.idempotency_key or uuid.uuid4().hex,
    )
    payment, checkout_url = initiate_borrower_gateway_checkout(
        db,
        loan=loan,
        amount=amount,
        idempotency_key=key,
        initiated_by_user_id=current_user.id,
    )
    return {
        "payment_id": payment.id,
        "status": payment.status.value,
        "amount": payment.amount,
        "currency": payment.currency,
        "checkout_url": checkout_url,
    }


@router.post(
    "/borrower/loans/{loan_id}/settlement-quotes",
    response_model=EarlySettlementRead,
    status_code=201,
)
def create_borrower_settlement_quote(
    loan_id: UUID,
    payload: BorrowerSettlementQuoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.BORROWER or not current_user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access is required")
    loan = db.get(ClientCompanyLoan, loan_id)
    if not loan or loan.borrower_id != current_user.borrower_profile.id:
        raise HTTPException(status_code=404, detail="Loan is not available to you")
    return quote_early_settlement(
        db,
        loan=loan,
        settlement_date=payload.settlement_date,
        quoted_by_user_id=current_user.id,
        valid_for_days=payload.valid_for_days,
    )


@router.post(
    "/borrower/loans/{loan_id}/settlement-quotes/{settlement_id}/checkout",
    response_model=BorrowerGatewayCheckoutRead,
)
def create_borrower_settlement_checkout(
    loan_id: UUID,
    settlement_id: UUID,
    payload: BorrowerSettlementCheckoutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.BORROWER or not current_user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access is required")
    loan = db.get(ClientCompanyLoan, loan_id)
    if not loan or loan.borrower_id != current_user.borrower_profile.id:
        raise HTTPException(status_code=404, detail="Loan is not available to you")
    quote = db.get(LoanEarlySettlement, settlement_id)
    if not quote or quote.loan_id != loan.id or quote.borrower_id != current_user.borrower_profile.id:
        raise HTTPException(status_code=404, detail="Settlement quote is not available to you")
    key = build_idempotency_key(
        "borrower-settlement-checkout",
        quote.id,
        payload.idempotency_key or uuid.uuid4().hex,
    )
    payment, checkout_url = initiate_borrower_settlement_checkout(
        db,
        loan=loan,
        quote=quote,
        idempotency_key=key,
        initiated_by_user_id=current_user.id,
        agreement_note=payload.agreement_note,
        agreement_reference=payload.agreement_reference,
    )
    return {
        "payment_id": payment.id,
        "status": payment.status.value,
        "amount": payment.amount,
        "currency": payment.currency,
        "checkout_url": checkout_url,
    }


@router.post("/webhooks")
async def gateway_webhook(
    request: Request,
    x_ipb_signature: str | None = Header(default=None, alias="X-IPB-Signature"),
    x_ipb_event_id: str | None = Header(default=None, alias="X-IPB-Event-ID"),
    db: Session = Depends(get_db),
):
    if not settings.LELEFAPAYGATE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Gateway webhook verification is not configured")
    raw_body = await request.body()
    try:
        verify_webhook_signature(
            raw_body,
            x_ipb_signature,
            settings.LELEFAPAYGATE_WEBHOOK_SECRET,
            tolerance_seconds=settings.LELEFAPAYGATE_WEBHOOK_TOLERANCE_SECONDS,
        )
    except LelefaPayGateWebhookError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    event_id = (x_ipb_event_id or "").strip()
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing X-IPB-Event-ID")
    event, duplicate = process_gateway_webhook(db, raw_body=raw_body, event_id=event_id)

    if not duplicate and event.payment_id:
        payment = db.get(PaymentTransaction, event.payment_id)
        if payment:
            recipient_ids = set(payment_recipient_user_ids(db, payment))
            if payment.initiated_by_user_id:
                recipient_ids.add(payment.initiated_by_user_id)

            status_event = build_realtime_event(
                "PAYMENT_STATUS_CHANGED",
                domain="money",
                entity_id=payment.id,
                data={
                    "payment_id": str(payment.id),
                    "amount": f"{payment.amount:.2f}",
                    "currency": payment.currency,
                    "status": payment.status.value,
                    "purpose": payment.purpose.value,
                    "provider": payment.provider.value,
                },
            )
            await emit_realtime_event(recipient_ids, status_event)

            # Only a provider-confirmed success can produce MONEY_RECEIVED. The
            # marker prevents two succeeded webhook variants from ringing the
            # same payment twice.
            provider_payload = dict(payment.provider_payload or {})
            if (
                payment.status == PaymentStatus.SUCCEEDED
                and not provider_payload.get("realtime_money_received_notified")
            ):
                money_recipients = payment_recipient_user_ids(db, payment)
                if money_recipients:
                    provider_payload["realtime_money_received_notified"] = True
                    payment.provider_payload = provider_payload
                    db.add(payment)
                    db.commit()
                    money_event = build_realtime_event(
                        "MONEY_RECEIVED",
                        domain="money",
                        entity_id=payment.id,
                        data={
                            "payment_id": str(payment.id),
                            "amount": f"{payment.amount:.2f}",
                            "currency": payment.currency,
                            "status": payment.status.value,
                            "purpose": payment.purpose.value,
                            "provider": payment.provider.value,
                        },
                        notification={
                            "category": "money",
                            "title": "Money received",
                            "body": f"{payment.currency} {payment.amount:.2f} received in LoanHub",
                            "route": f"money:{payment.id}",
                        },
                    )
                    await emit_realtime_event(money_recipients, money_event)

    return {
        "accepted": True,
        "duplicate": duplicate,
        "event_id": event.event_id,
        "status": event.processing_status,
    }


def _authorise_payment(
    db: Session,
    payment: PaymentTransaction,
    current_user: User,
    company_id: str | None,
    active_role: str | None,
) -> None:
    if is_platform_role(current_user.role):
        if current_user.role not in PLATFORM_FINANCE_ROLES:
            raise HTTPException(status_code=403, detail="Platform finance permission is required")
        return
    if current_user.role == UserRole.BORROWER:
        if not current_user.borrower_profile or payment.borrower_id != current_user.borrower_profile.id:
            raise HTTPException(status_code=403, detail="Payment is not available to you")
        return
    context = resolve_tenant_context(db, current_user, company_id, active_role)
    if payment.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")


@router.post("/payments/{payment_id}/refresh", response_model=PaymentTransactionRead)
def refresh_payment(
    payment_id: UUID,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    payment = db.get(PaymentTransaction, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment transaction not found")
    _authorise_payment(db, payment, current_user, x_company_id, x_active_role)
    return refresh_gateway_payment(db, payment)
