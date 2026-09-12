from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from core.access_control import LENDING_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.borrower import Borrower
from database.models.enums import LoanRequestStatus, PaymentProvider
from database.models.file_management import ManagedFile
from database.models.loan_request import LoanRequest
from database.models.user import User
from database.schemas.billing import MarketplaceUnlockCreate, MarketplaceUnlockRead
from database.schemas.marketplace import (
    MarketplaceBorrowerDetail,
    MarketplaceBorrowerSummary,
    MarketplaceEvidenceDocument,
    MarketplaceRequestCard,
    MarketplaceRequestDetail,
)
from database.session import get_db
from services.borrower_profile_service import build_borrower_evaluation
from services.billing_service import (
    company_has_request_access,
    unlock_marketplace_request,
    unlock_price,
)


router = APIRouter(prefix="/marketplace", tags=["Loan Marketplace"])


def request_query(db: Session):
    return db.query(LoanRequest).options(
        joinedload(LoanRequest.borrower).joinedload(Borrower.user).joinedload(User.person),
    )


def request_or_404(db: Session, request_id: UUID) -> LoanRequest:
    request = request_query(db).filter(LoanRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Loan request not found")
    return request


def income_band(value) -> str | None:
    if value is None:
        return None
    amount = Decimal(value)
    if amount < 3000:
        return "Below M3,000"
    if amount < 7000:
        return "M3,000 - M6,999"
    if amount < 15000:
        return "M7,000 - M14,999"
    if amount < 30000:
        return "M15,000 - M29,999"
    return "M30,000 and above"


def card_for(
    db: Session,
    request: LoanRequest,
    context: TenantContext,
) -> MarketplaceRequestCard:
    borrower = request.borrower
    person = borrower.user.person if borrower and borrower.user else None
    unlocked = bool(
        context.is_platform_admin
        or company_has_request_access(
            db,
            company_id=context.company_id,
            loan_request_id=request.id,
        )
    )
    price = Decimal("0") if context.is_platform_admin else unlock_price(db, context.company_id)
    return MarketplaceRequestCard(
        id=request.id,
        requested_amount=request.requested_amount,
        preferred_term_months=request.preferred_term_months,
        loan_purpose=request.loan_purpose,
        status=request.status,
        allow_lenders_to_call=request.allow_lenders_to_call,
        created_at=request.created_at,
        expires_at=request.expires_at,
        is_unlocked=unlocked,
        unlock_price=price,
        borrower=MarketplaceBorrowerSummary(
            district=person.district if person else None,
            employment_status=borrower.employment_status.value,
            monthly_income_band=income_band(borrower.monthly_income),
            has_existing_loans=borrower.has_existing_loans,
        ),
    )


def borrower_detail_for(db: Session, request: LoanRequest) -> MarketplaceBorrowerDetail:
    borrower = request.borrower
    user = borrower.user
    person = user.person
    if not person:
        raise HTTPException(status_code=409, detail="Borrower person profile is incomplete")

    evidence = []
    if borrower.consent_to_share_profile and borrower.consent_to_share_documents:
        evidence = (
            db.query(ManagedFile)
            .filter(
                ManagedFile.owner_user_id == user.id,
                ManagedFile.linked_entity_type == "borrower_evaluation",
                ManagedFile.linked_entity_id == str(borrower.id),
                ManagedFile.is_deleted.is_(False),
                ManagedFile.scan_status != "quarantined",
            )
            .order_by(ManagedFile.created_at.desc())
            .all()
        )
    evaluation = build_borrower_evaluation(borrower, person, evidence)

    return MarketplaceBorrowerDetail(
        borrower_id=borrower.id,
        user_id=user.id,
        full_name=person.full_name,
        phone=user.phone,
        email=user.email,
        gender=person.gender.value if person.gender else None,
        date_of_birth=person.date_of_birth.isoformat() if person.date_of_birth else None,
        national_id=person.national_id,
        passport_number=person.passport_number,
        district=person.district,
        town_or_village=person.town_or_village,
        physical_address=person.physical_address,
        employment_status=borrower.employment_status.value,
        employment_type=borrower.employment_type,
        employer_name=borrower.employer_name,
        job_title=borrower.job_title,
        employment_start_date=(
            borrower.employment_start_date.isoformat()
            if borrower.employment_start_date
            else None
        ),
        monthly_income=borrower.monthly_income,
        net_monthly_income=borrower.net_monthly_income,
        other_monthly_income=borrower.other_monthly_income,
        other_income_source=borrower.other_income_source,
        monthly_living_expenses=borrower.monthly_living_expenses,
        monthly_debt_repayments=borrower.monthly_debt_repayments,
        dependants=borrower.dependants,
        residential_status=borrower.residential_status,
        years_at_address=borrower.years_at_address,
        existing_loan_total=borrower.existing_loan_total,
        bank_name=borrower.bank_name,
        account_holder_name=borrower.account_holder_name,
        account_last_four=borrower.account_last_four,
        consent_to_credit_checks=borrower.consent_to_credit_checks,
        consent_to_share_documents=borrower.consent_to_share_documents,
        evidence_documents=[
            MarketplaceEvidenceDocument(
                id=item.id,
                category=item.category,
                original_name=item.original_name,
                mime_type=item.mime_type,
                size_bytes=item.size_bytes,
                created_at=item.created_at,
            )
            for item in evidence
        ],
        **evaluation,
    )


@router.get("/requests", response_model=list[MarketplaceRequestCard])
def list_marketplace_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    requests = (
        request_query(db)
        .filter(
            LoanRequest.status.in_([LoanRequestStatus.OPEN, LoanRequestStatus.OFFERED]),
            LoanRequest.visible_to_lenders.is_(True),
        )
        .order_by(LoanRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [card_for(db, request, context) for request in requests]


@router.get("/requests/{request_id}", response_model=MarketplaceRequestDetail)
def get_marketplace_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    request = request_or_404(db, request_id)
    if request.status not in {LoanRequestStatus.OPEN, LoanRequestStatus.OFFERED} or not request.visible_to_lenders:
        raise HTTPException(status_code=404, detail="Loan request is not available in the marketplace")

    card = card_for(db, request, context)
    detail = borrower_detail_for(db, request) if card.is_unlocked else None
    return MarketplaceRequestDetail(**card.model_dump(), borrower_detail=detail)


@router.post(
    "/requests/{request_id}/unlock",
    response_model=MarketplaceUnlockRead,
    status_code=status.HTTP_201_CREATED,
)
def unlock_request(
    request_id: UUID,
    payload: MarketplaceUnlockCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=400, detail="Select a loan company account to purchase marketplace access")
    request = request_or_404(db, request_id)
    if request.status not in {LoanRequestStatus.OPEN, LoanRequestStatus.OFFERED} or not request.visible_to_lenders:
        raise HTTPException(status_code=409, detail="Loan request is not open for lender access")

    unlock, _payment = unlock_marketplace_request(
        db,
        company_id=context.company_id,
        loan_request_id=request.id,
        provider=payload.provider or (PaymentProvider.CASH if payload.payment_method.value == "cash" else PaymentProvider.MANUAL),
        payer_phone=payload.payer_phone,
        initiated_by_user_id=context.user.id,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes,
    )
    return unlock
