"""Tenant-scoped, strictly non-posting LoanHub -> IthutePay preview.

No DB mutations, payment creation, provider initiation, ledger posting or
idempotency reservation. Uses the already verified Phase 30 authorizer.
"""
from __future__ import annotations

import re
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.config.config import settings
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from integrations.ithutepay_batlokoa_handshake import COMPANY_ID
from integrations.ithutepay_batlokoa_intent_preview import (
    BatlokoaPreviewError,
    perform_readonly_collection_preview,
)
from services.batlokoa_collection_preview_authorization import (
    BatlokoaCollectionAuthorizationError,
    authorize_batlokoa_collection_preview,
)

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def prepare_verified_batlokoa_collection_preview(
    *,
    db: Session,
    context: TenantContext,
    loan_id: UUID,
    amount: Decimal,
    idempotency_key: str,
) -> dict:
    """Verify borrower and loan against DB records before previewing only.

    The source idempotency key is a fingerprint input, not a reserved key.
    A successful result does not constitute a borrower debit mandate.
    """
    if not settings.ITHUTEPAY_BATLOKOA_INTENT_PREVIEW_ENABLED:
        raise HTTPException(status_code=404, detail="Collection preview unavailable")
    if (context.is_platform_admin or context.staff is None or
            context.company_id is None or str(context.company_id) != COMPANY_ID):
        raise HTTPException(status_code=403, detail="Company collection preview not permitted")
    if not isinstance(idempotency_key, str) or not KEY_PATTERN.fullmatch(idempotency_key):
        raise HTTPException(status_code=422, detail="Invalid preview request key")

    # Borrower ownership must come from LoanHub's own scoped loan relation.
    borrower_user_id = db.scalar(
        select(Borrower.user_id)
        .join(ClientCompanyLoan, ClientCompanyLoan.borrower_id == Borrower.id)
        .where(
            ClientCompanyLoan.id == loan_id,
            ClientCompanyLoan.company_id == context.company_id,
        )
    )
    if borrower_user_id is None:
        raise HTTPException(status_code=404, detail="Loan not available")

    try:
        authorization = authorize_batlokoa_collection_preview(
            db=db,
            context=context,
            loan_id=loan_id,
            borrower_user_id=borrower_user_id,
            amount=amount,
        )
    except BatlokoaCollectionAuthorizationError as exc:
        raise HTTPException(status_code=404, detail="Loan not available for preview") from exc

    if authorization.payment_execution_enabled or authorization.company_id != COMPANY_ID:
        raise HTTPException(status_code=409, detail="Preview safety boundary mismatch")

    try:
        quote = perform_readonly_collection_preview(
            verified_company_id=authorization.company_id,
            amount=authorization.amount,
            source_reference=authorization.source_reference,
            idempotency_key=idempotency_key,
        )
    except BatlokoaPreviewError as exc:
        raise HTTPException(status_code=502, detail="Collection preview provider unavailable") from exc

    if (quote.get("financial_posting_enabled") is not False or
            quote.get("provider_execution_enabled") is not False or
            quote.get("idempotency_reserved") is not False or
            quote.get("provider_charges_included") is not False):
        raise HTTPException(status_code=502, detail="Unsafe collection preview response")

    return {
        "loan_id": str(loan_id),
        "company_id": authorization.company_id,
        "amount": authorization.amount,
        "currency": "LSL",
        "request_fingerprint": quote["request_fingerprint"],
        "ithutepay_platform_total_fee": quote["ithutepay_platform_total_fee"],
        "provider_charges_included": False,
        "financial_posting_enabled": False,
        "provider_execution_enabled": False,
        "idempotency_reserved": False,
        "preview_only": True,
    }
