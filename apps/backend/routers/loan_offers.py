from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.access_control import (
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_current_active_user,
    get_tenant_context,
    require_tenant_roles,
    resolve_tenant_context,
)
from database.models.enums import LoanRequestStatus, OfferStatus, UserRole
from database.models.loan_offer import LoanOffer
from database.models.loan_request import LoanRequest
from database.models.user import User
from database.schemas.loan_offer import LoanOfferCreate, LoanOfferResponse, LoanOfferUpdate
from database.session import get_db
from services.billing_service import company_has_request_access
from services.loan_service import calculate_offer_totals


router = APIRouter(prefix="/loan-offers", tags=["Loan Offers"])


def offer_or_404(db: Session, offer_id: UUID) -> LoanOffer:
    offer = db.query(LoanOffer).filter(LoanOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Loan offer not found")
    return offer


def request_or_404(db: Session, request_id: UUID) -> LoanRequest:
    request = db.query(LoanRequest).filter(LoanRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Loan request not found")
    return request


@router.post("/", response_model=LoanOfferResponse, status_code=status.HTTP_201_CREATED)
def create_offer(
    payload: LoanOfferCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=400, detail="A loan-company context is required to submit an offer")
    request = request_or_404(db, payload.loan_request_id)
    if request.status not in {LoanRequestStatus.OPEN, LoanRequestStatus.OFFERED} or not request.visible_to_lenders:
        raise HTTPException(status_code=409, detail="Loan request is not open for offers")
    if not company_has_request_access(
        db,
        company_id=context.company_id,
        loan_request_id=request.id,
    ):
        raise HTTPException(status_code=402, detail="Unlock this loan request before making an offer")

    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)

    duplicate = (
        db.query(LoanOffer)
        .filter(
            LoanOffer.loan_request_id == request.id,
            LoanOffer.company_id == context.company_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Your company already submitted an offer")

    if len(payload.installment_due_dates) != payload.term_months:
        raise HTTPException(
            status_code=422,
            detail=f"Enter exactly {payload.term_months} installment due dates before submitting the offer",
        )
    try:
        monthly, total, calculation_breakdown = calculate_offer_totals(
            payload.approved_amount,
            payload.interest_rate_percent or 0,
            payload.term_months,
            payload.processing_fee,
            payload.calculation_method,
            due_dates=payload.installment_due_dates,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    offer = LoanOffer(
        loan_request_id=request.id,
        company_id=context.company_id,
        branch_id=branch_id,
        offered_by_user_id=context.user.id,
        approved_amount=payload.approved_amount,
        term_months=payload.term_months,
        interest_rate_percent=payload.interest_rate_percent or 0,
        processing_fee=payload.processing_fee,
        monthly_repayment=monthly,
        total_repayment=total,
        calculation_method=payload.calculation_method.value,
        calculation_breakdown=calculation_breakdown,
        notes=payload.notes,
        status=OfferStatus.PENDING,
    )
    db.add(offer)
    if request.status == LoanRequestStatus.OPEN:
        request.status = LoanRequestStatus.OFFERED
    db.commit()
    db.refresh(offer)
    return offer


@router.get("/request/{loan_request_id}", response_model=list[LoanOfferResponse])
def list_offers_by_request(
    loan_request_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    request = request_or_404(db, loan_request_id)
    query = db.query(LoanOffer).filter(LoanOffer.loan_request_id == request.id)

    if current_user.role == UserRole.SUPERADMIN:
        pass
    elif current_user.role == UserRole.BORROWER:
        if not current_user.borrower_profile or request.borrower_id != current_user.borrower_profile.id:
            raise HTTPException(status_code=403, detail="This request does not belong to you")
    else:
        context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
        require_tenant_roles(context, LENDING_ROLES)
        query = query.filter(LoanOffer.company_id == context.company_id)
        if context.branch_id and context.role not in {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}:
            query = query.filter(LoanOffer.branch_id == context.branch_id)

    return query.order_by(LoanOffer.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{offer_id}", response_model=LoanOfferResponse)
def get_offer(
    offer_id: UUID,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    offer = offer_or_404(db, offer_id)
    request = request_or_404(db, offer.loan_request_id)

    if current_user.role == UserRole.SUPERADMIN:
        return offer
    if current_user.role == UserRole.BORROWER:
        if not current_user.borrower_profile or request.borrower_id != current_user.borrower_profile.id:
            raise HTTPException(status_code=403, detail="This offer is not available to you")
        return offer

    context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
    if offer.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    assert_branch_scope(context, offer.branch_id)
    return offer


@router.patch("/{offer_id}", response_model=LoanOfferResponse)
def update_offer(
    offer_id: UUID,
    payload: LoanOfferUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    offer = offer_or_404(db, offer_id)
    if offer.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    assert_branch_scope(context, offer.branch_id)
    if offer.status != OfferStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only pending offers can be edited")

    changes = payload.model_dump(exclude_unset=True)
    changes.pop("status", None)
    supplied_due_dates = changes.pop("installment_due_dates", None)
    for field, value in changes.items():
        setattr(offer, field, value)

    if supplied_due_dates is None:
        supplied_due_dates = [
            date.fromisoformat(str(row["due_date"]))
            for row in (offer.calculation_breakdown or {}).get("schedule_rows", [])
            if row.get("due_date")
        ]
    if len(supplied_due_dates) != offer.term_months:
        raise HTTPException(
            status_code=422,
            detail=f"Enter exactly {offer.term_months} installment due dates before updating the offer",
        )
    try:
        monthly, total, calculation_breakdown = calculate_offer_totals(
            offer.approved_amount,
            offer.interest_rate_percent or 0,
            offer.term_months,
            offer.processing_fee or 0,
            offer.calculation_method,
            due_dates=supplied_due_dates,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    offer.monthly_repayment = monthly
    offer.total_repayment = total
    offer.calculation_method = calculation_breakdown["method"]
    offer.calculation_breakdown = calculation_breakdown
    db.commit()
    db.refresh(offer)
    return offer


@router.post("/{offer_id}/withdraw", response_model=LoanOfferResponse)
def withdraw_offer(
    offer_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    offer = offer_or_404(db, offer_id)
    if offer.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    assert_branch_scope(context, offer.branch_id)
    if offer.status != OfferStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only pending offers can be withdrawn")
    offer.status = OfferStatus.WITHDRAWN
    db.commit()
    db.refresh(offer)
    return offer


@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_offer(
    offer_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    offer = offer_or_404(db, offer_id)
    if offer.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    assert_branch_scope(context, offer.branch_id)
    if offer.status != OfferStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only pending offers can be deleted")
    db.delete(offer)
    db.commit()
