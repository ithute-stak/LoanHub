from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from core.access_control import get_current_active_user, require_platform_admin, require_platform_finance
from database.models.borrower import Borrower
from database.models.enums import LoanRequestStatus, UserRole
from database.models.loan_offer import LoanOffer
from database.models.loan_request import LoanRequest
from database.models.user import User
from database.schemas.cash import CashBorrowerRequestFeeCreate, CashPaymentResult
from database.schemas.loan import LoanRead
from database.schemas.loan_request_schema import LoanRequestCreate, LoanRequestResponse, LoanRequestUpdate
from database.session import get_db
from services.loan_service import accept_offer, record_borrower_request_fee
from services.platform_finance_service import apply_fee_snapshot_to_request


router = APIRouter(prefix="/loan_requests", tags=["Loan Requests"])


def require_borrower(user: User) -> Borrower:
    if user.role != UserRole.BORROWER or not user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower account is required")
    return user.borrower_profile


def owned_request_or_404(db: Session, request_id: UUID, borrower_id: UUID) -> LoanRequest:
    request = (
        db.query(LoanRequest)
        .filter(LoanRequest.id == request_id, LoanRequest.borrower_id == borrower_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Loan request not found")
    return request


@router.post("/", response_model=LoanRequestResponse, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: LoanRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = require_borrower(current_user)
    visible = payload.visible_to_lenders
    if visible and not borrower.consent_to_share_profile:
        raise HTTPException(
            status_code=409,
            detail="Consent to share the borrower profile is required before broadcasting a request",
        )
    now = datetime.now(timezone.utc)
    request = LoanRequest(
        borrower_id=borrower.id,
        requested_amount=payload.requested_amount,
        preferred_term_months=payload.preferred_term_months,
        loan_purpose=payload.loan_purpose,
        visible_to_lenders=visible,
        allow_lenders_to_call=payload.allow_lenders_to_call,
        origination_channel="online",
        captured_by_user_id=current_user.id,
        status=LoanRequestStatus.DRAFT,
    )
    apply_fee_snapshot_to_request(db, request)
    if request.service_fee_status == "not_required":
        request.status = LoanRequestStatus.OPEN if visible else LoanRequestStatus.SUBMITTED
        request.submitted_at = now
        request.expires_at = now + timedelta(days=30) if visible else None
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/", response_model=list[LoanRequestResponse])
def get_all_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    return (
        db.query(LoanRequest)
        .order_by(LoanRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/my", response_model=list[LoanRequestResponse])
def get_my_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = require_borrower(current_user)
    return (
        db.query(LoanRequest)
        .filter(LoanRequest.borrower_id == borrower.id)
        .order_by(LoanRequest.created_at.desc())
        .all()
    )


@router.get("/open", response_model=list[LoanRequestResponse])
def get_open_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    # Lenders must use /marketplace/requests so private borrower data can be gated.
    return (
        db.query(LoanRequest)
        .filter(
            LoanRequest.status == LoanRequestStatus.OPEN,
            LoanRequest.visible_to_lenders.is_(True),
        )
        .order_by(LoanRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{request_id}", response_model=LoanRequestResponse)
def get_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == UserRole.SUPERADMIN:
        request = db.query(LoanRequest).filter(LoanRequest.id == request_id).first()
        if not request:
            raise HTTPException(status_code=404, detail="Loan request not found")
        return request

    borrower = require_borrower(current_user)
    return owned_request_or_404(db, request_id, borrower.id)


@router.patch("/{request_id}", response_model=LoanRequestResponse)
def update_request(
    request_id: UUID,
    payload: LoanRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = require_borrower(current_user)
    request = owned_request_or_404(db, request_id, borrower.id)

    if request.status in {LoanRequestStatus.ACCEPTED, LoanRequestStatus.CANCELLED, LoanRequestStatus.EXPIRED}:
        raise HTTPException(status_code=409, detail="This loan request can no longer be edited")

    changes = payload.model_dump(exclude_unset=True)
    requested_status = changes.pop("status", None)
    if "requested_amount" in changes and request.service_fee_status == "paid":
        raise HTTPException(
            status_code=409,
            detail="The requested amount cannot be changed after the service fee has been paid",
        )
    if requested_status and requested_status not in {
        LoanRequestStatus.DRAFT,
        LoanRequestStatus.SUBMITTED,
        LoanRequestStatus.OPEN,
        LoanRequestStatus.CANCELLED,
    }:
        raise HTTPException(status_code=400, detail="Invalid borrower-controlled status")

    for field, value in changes.items():
        setattr(request, field, value)

    if "requested_amount" in changes and request.service_fee_status != "paid":
        apply_fee_snapshot_to_request(db, request)

    if requested_status:
        if requested_status in {LoanRequestStatus.SUBMITTED, LoanRequestStatus.OPEN} and request.service_fee_status not in {
            "paid",
            "not_required",
        }:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="The configured borrower service fee must be paid before submission",
            )
        request.status = requested_status
    if request.visible_to_lenders and not borrower.consent_to_share_profile:
        raise HTTPException(
            status_code=409,
            detail="Consent to share the borrower profile is required before broadcasting a request",
        )
    if (
        request.visible_to_lenders
        and request.status in {LoanRequestStatus.DRAFT, LoanRequestStatus.SUBMITTED}
        and request.service_fee_status in {"paid", "not_required"}
    ):
        request.status = LoanRequestStatus.OPEN
        request.submitted_at = request.submitted_at or datetime.now(timezone.utc)
        request.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    if not request.visible_to_lenders and request.status == LoanRequestStatus.OPEN:
        request.status = LoanRequestStatus.SUBMITTED

    db.commit()
    db.refresh(request)
    return request


@router.post("/{request_id}/submit", response_model=LoanRequestResponse)
def submit_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = require_borrower(current_user)
    request = owned_request_or_404(db, request_id, borrower.id)
    if request.status not in {LoanRequestStatus.DRAFT, LoanRequestStatus.SUBMITTED}:
        raise HTTPException(status_code=409, detail="Request cannot be submitted in its current state")
    if request.service_fee_status not in {"paid", "not_required"}:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "The configured borrower service fee must be paid before submission",
                "service_fee_status": request.service_fee_status,
                "service_fee_amount": str(request.service_fee_amount),
                "service_fee_currency": request.service_fee_currency,
            },
        )
    if not borrower.consent_to_share_profile:
        raise HTTPException(
            status_code=409,
            detail="Consent to share the borrower profile is required before broadcasting a request",
        )
    now = datetime.now(timezone.utc)
    request.status = LoanRequestStatus.OPEN
    request.visible_to_lenders = True
    request.submitted_at = now
    request.expires_at = now + timedelta(days=30)
    db.commit()
    db.refresh(request)
    return request


@router.post(
    "/{request_id}/service-fee-payment",
    response_model=CashPaymentResult,
    summary="Record a verified borrower request service-fee payment",
)
@router.post(
    "/{request_id}/cash-service-fee",
    response_model=CashPaymentResult,
    include_in_schema=False,
)
def collect_service_fee_payment(
    request_id: UUID,
    payload: CashBorrowerRequestFeeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_finance),
):
    request = db.query(LoanRequest).filter(LoanRequest.id == request_id).with_for_update().first()
    if not request:
        raise HTTPException(status_code=404, detail="Loan request not found")
    payment, cash = record_borrower_request_fee(
        db,
        request=request,
        initiated_by_user_id=user.id,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
    )
    return {
        "payment_id": payment.id,
        "payment_method": payment.payment_method,
        "provider_reference": payment.provider_reference,
        "proof_reference": payment.proof_reference,
        "cash_transaction": cash,
        "preview": None,
    }


@router.post("/{request_id}/cancel", response_model=LoanRequestResponse)
def cancel_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = require_borrower(current_user)
    request = owned_request_or_404(db, request_id, borrower.id)
    if request.status == LoanRequestStatus.ACCEPTED:
        raise HTTPException(status_code=409, detail="Accepted request cannot be cancelled")
    request.status = LoanRequestStatus.CANCELLED
    request.visible_to_lenders = False
    db.commit()
    db.refresh(request)
    return request


@router.post("/{request_id}/offers/{offer_id}/accept", response_model=LoanRead)
def accept_request_offer(
    request_id: UUID,
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = require_borrower(current_user)
    request = (
        db.query(LoanRequest)
        .options(joinedload(LoanRequest.borrower))
        .filter(LoanRequest.id == request_id, LoanRequest.borrower_id == borrower.id)
        # The borrower is eager-loaded through a LEFT OUTER JOIN. PostgreSQL
        # rejects a bare FOR UPDATE because it also tries to lock the nullable
        # joined borrower side. Lock only the authoritative loan_requests row.
        .with_for_update(of=LoanRequest)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Loan request not found")
    offer = (
        db.query(LoanOffer)
        .filter(LoanOffer.id == offer_id)
        .with_for_update()
        .first()
    )
    if not offer:
        raise HTTPException(status_code=404, detail="Loan offer not found")
    return accept_offer(
        db,
        request=request,
        offer=offer,
        borrower_user_id=current_user.id,
    )


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = require_borrower(current_user)
    request = owned_request_or_404(db, request_id, borrower.id)
    if request.status == LoanRequestStatus.ACCEPTED:
        raise HTTPException(status_code=409, detail="Accepted request cannot be deleted")
    db.delete(request)
    db.commit()
