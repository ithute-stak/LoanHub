from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_user_context,
    require_platform_admin,
    require_tenant_roles,
)
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import LoanStatus, NotificationType, RiskLevel, UserRole
from database.models.file_management import ManagedFile
from database.models.loan_product import LoanProduct
from database.models.notification import Notification
from database.models.origination import AffordabilityAssessment
from database.models.person import Person
from database.models.professional_lending import (
    CreditBlacklist,
    DirectLoanApplication,
    OfferWallInterest,
    OfferWallPost,
    PaymentReceipt,
    PrintAgent,
    PrintJob,
    Suggestion,
)
from database.models.user import User
from database.schemas.professional_lending import (
    AssistantQuestion,
    DirectApplicationApprove,
    DirectApplicationCreate,
    DirectApplicationReject,
    DirectApplicationReview,
    PrintAgentCreate,
    PrintJobCreate,
    SuggestionCreate,
    SuggestionUpdate,
    WallPostCreate,
)
from database.session import get_db
from services.file_service import read_file_bytes
from services.interest_calculation_service import calculate_loan_terms
from services.loan_service import (
    create_repayment_schedule,
    generate_loan_reference,
)
from services.origination_service import (
    assessment_effective_decision,
    enforce_duplicate_policy,
    get_or_create_policy,
)

router = APIRouter(prefix="/professional", tags=["Professional lending"])

DIRECT_APPLICATION_VIEW_ROLES = (
    LENDING_ROLES
    | FINANCE_ROLES
    | {UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR}
)
DIRECT_APPLICATION_REVIEW_ROLES = COMPANY_MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.RISK_MANAGER,
}
DIRECT_APPLICATION_APPROVAL_ROLES = COMPANY_MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER}


def ref(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(4).upper()}"


def serialize(obj):
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


def _borrower_name(db: Session, borrower_id: UUID) -> str:
    row = (
        db.query(Person.first_name, Person.middle_name, Person.last_name)
        .join(User, User.id == Person.user_id)
        .join(Borrower, Borrower.user_id == User.id)
        .filter(Borrower.id == borrower_id)
        .first()
    )
    if not row:
        return "Registered borrower"
    return " ".join(value for value in row if value).strip() or "Registered borrower"


def _application_payload(db: Session, application: DirectLoanApplication) -> dict:
    data = serialize(application)
    data["borrower_name"] = _borrower_name(db, application.borrower_id)
    client = (
        db.query(CompanyBorrowerAccount)
        .filter(
            CompanyBorrowerAccount.company_id == application.company_id,
            CompanyBorrowerAccount.borrower_id == application.borrower_id,
        )
        .first()
    )
    data["account_reference"] = client.account_reference if client else None
    product = db.get(LoanProduct, application.product_id) if application.product_id else None
    data["product_name"] = product.name if product else None
    loan = db.get(ClientCompanyLoan, application.loan_id) if application.loan_id else None
    data["loan_reference"] = loan.loan_reference if loan else None
    return data


def _direct_application_or_404(
    db: Session,
    *,
    application_id: UUID,
    context: TenantContext,
    lock: bool = False,
) -> DirectLoanApplication:
    query = db.query(DirectLoanApplication).filter(
        DirectLoanApplication.id == application_id,
        DirectLoanApplication.company_id == context.company_id,
    )
    if lock:
        query = query.with_for_update()
    application = query.first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    assert_branch_scope(context, application.branch_id)
    return application


def _company_product_or_404(
    db: Session,
    *,
    product_id: UUID,
    company_id: UUID,
) -> LoanProduct:
    product = (
        db.query(LoanProduct)
        .filter(
            LoanProduct.id == product_id,
            LoanProduct.company_id == company_id,
            LoanProduct.is_active.is_(True),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="The selected active loan product was not found")
    return product


@router.get("/credit-check/{borrower_id}")
def credit_check(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(
        context,
        LENDING_ROLES | {UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER},
    )
    borrower = db.get(Borrower, borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    if not borrower.consent_to_credit_checks:
        raise HTTPException(status_code=409, detail="Borrower consent to credit checks is required")
    blacklist = (
        db.query(CreditBlacklist)
        .filter(
            CreditBlacklist.borrower_id == borrower_id,
            CreditBlacklist.is_active.is_(True),
        )
        .first()
    )
    loans = (
        db.query(ClientCompanyLoan, LoanCompany.name)
        .join(LoanCompany, LoanCompany.id == ClientCompanyLoan.company_id)
        .filter(
            ClientCompanyLoan.borrower_id == borrower_id,
            ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
        )
        .all()
    )
    return {
        "blacklisted": bool(blacklist),
        "blacklist_reason": blacklist.reason if blacklist else None,
        "active_obligations": [
            {
                "company_id": str(loan.company_id),
                "company_name": company_name,
                "loan_reference": loan.loan_reference,
                "balance": str(loan.balance),
                "status": loan.status.value,
            }
            for loan, company_name in loans
        ],
        "warning": (
            "The applicant has active obligations with another participating lender."
            if any(loan.company_id != context.company_id for loan, _ in loans)
            else None
        ),
    }


@router.post("/direct-applications", status_code=status.HTTP_201_CREATED)
def create_direct(
    payload: DirectApplicationCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    assert_branch_scope(context, payload.branch_id or context.branch_id)
    borrower = db.get(Borrower, payload.borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    client_account = (
        db.query(CompanyBorrowerAccount)
        .filter(
            CompanyBorrowerAccount.company_id == context.company_id,
            CompanyBorrowerAccount.borrower_id == payload.borrower_id,
            CompanyBorrowerAccount.status == "active",
        )
        .first()
    )
    if not client_account:
        raise HTTPException(
            status_code=409,
            detail="The borrower must be an active company client before an internal application is created",
        )
    if payload.product_id:
        product = _company_product_or_404(
            db,
            product_id=payload.product_id,
            company_id=context.company_id,
        )
        if not (Decimal(product.min_amount) <= payload.requested_amount <= Decimal(product.max_amount)):
            raise HTTPException(status_code=422, detail="Requested amount is outside the selected product range")
        if not (product.min_term_months <= payload.term_count <= product.max_term_months):
            raise HTTPException(status_code=422, detail="Term is outside the selected product range")

    policy = get_or_create_policy(db, context.company_id, context.user.id)
    enforce_duplicate_policy(
        db,
        borrower_id=payload.borrower_id,
        company_id=context.company_id,
        policy=policy,
    )
    warning = credit_check(payload.borrower_id, db, context)
    application = DirectLoanApplication(
        company_id=context.company_id,
        branch_id=payload.branch_id or client_account.branch_id or context.branch_id,
        borrower_id=payload.borrower_id,
        product_id=payload.product_id,
        application_reference=ref("DLA"),
        channel="internal_client_offer",
        requested_amount=payload.requested_amount,
        term_count=payload.term_count,
        repayment_type=payload.repayment_type,
        purpose=payload.purpose,
        first_payment_date=payload.installment_due_dates[0],
        preferred_payment_day=None,
        installment_due_dates=[value.isoformat() for value in payload.installment_due_dates],
        status="submitted",
        submitted_at=datetime.now(timezone.utc),
        affordability_snapshot={
            "monthly_income": str(borrower.monthly_income or 0),
            "existing_loan_total": str(borrower.existing_loan_total or 0),
        },
        credit_warning=warning,
        captured_by_user_id=context.user.id,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return _application_payload(db, application)


@router.get("/direct-applications")
def list_direct(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, DIRECT_APPLICATION_VIEW_ROLES)
    query = db.query(DirectLoanApplication).filter(
        DirectLoanApplication.company_id == context.company_id
    )
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(DirectLoanApplication.branch_id == context.branch_id)
    applications = query.order_by(DirectLoanApplication.created_at.desc()).limit(500).all()
    return [_application_payload(db, application) for application in applications]


@router.get("/direct-applications/{application_id}")
def get_direct_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, DIRECT_APPLICATION_VIEW_ROLES)
    application = _direct_application_or_404(
        db,
        application_id=application_id,
        context=context,
    )
    return _application_payload(db, application)


@router.post("/direct-applications/{application_id}/review")
def review_direct_application(
    application_id: UUID,
    payload: DirectApplicationReview,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, DIRECT_APPLICATION_REVIEW_ROLES)
    application = _direct_application_or_404(
        db,
        application_id=application_id,
        context=context,
        lock=True,
    )
    if application.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted applications can enter review")
    application.status = "under_review"
    application.reviewed_at = datetime.now(timezone.utc)
    application.reviewed_by_user_id = context.user.id
    application.decision_notes = (payload.notes or "").strip() or application.decision_notes
    db.commit()
    db.refresh(application)
    return _application_payload(db, application)


@router.post("/direct-applications/{application_id}/approve")
def approve_direct(
    application_id: UUID,
    payload: DirectApplicationApprove,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, DIRECT_APPLICATION_APPROVAL_ROLES)
    application = _direct_application_or_404(
        db,
        application_id=application_id,
        context=context,
        lock=True,
    )
    if application.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="Application is not awaiting approval")
    if application.loan_id:
        raise HTTPException(status_code=409, detail="A loan has already been created for this application")

    policy = get_or_create_policy(db, context.company_id, context.user.id)
    enforce_duplicate_policy(
        db,
        borrower_id=application.borrower_id,
        company_id=context.company_id,
        policy=policy,
        exclude_application_id=application.id,
        application_type=application.application_type or "new_loan",
        parent_loan_id=application.parent_loan_id,
        top_up_exception_approved=bool(application.top_up_exception_approved),
    )
    if application.channel == "credit_origination":
        assessment = (
            db.get(AffordabilityAssessment, application.affordability_assessment_id)
            if application.affordability_assessment_id
            else None
        )
        decision = assessment_effective_decision(assessment)
        if decision not in {"eligible", "conditionally_eligible"}:
            raise HTTPException(
                status_code=409,
                detail="A positive affordability assessment is required before approval",
            )

    product_id = payload.product_id or application.product_id
    if not product_id:
        raise HTTPException(status_code=422, detail="Select a loan product before approving the application")
    product = _company_product_or_404(
        db,
        product_id=product_id,
        company_id=context.company_id,
    )
    if not (Decimal(product.min_amount) <= payload.approved_amount <= Decimal(product.max_amount)):
        raise HTTPException(
            status_code=422,
            detail=f"Approved amount must be between {product.min_amount} and {product.max_amount}",
        )
    if not (product.min_term_months <= application.term_count <= product.max_term_months):
        raise HTTPException(
            status_code=422,
            detail=f"Term must be between {product.min_term_months} and {product.max_term_months} months",
        )

    interest_rate = (
        Decimal(payload.interest_rate)
        if payload.interest_rate is not None
        else Decimal(product.interest_rate_percent)
    )
    processing_fee = (
        Decimal(payload.processing_fee)
        if payload.processing_fee is not None
        else Decimal(product.processing_fee)
    )
    parent_loan = None
    top_up_settlement_amount = Decimal("0")
    top_up_cash_amount = Decimal(payload.approved_amount)
    if application.application_type == "top_up":
        if not application.parent_loan_id:
            raise HTTPException(status_code=409, detail="The top-up application is not linked to an existing loan")
        parent_loan = (
            db.query(ClientCompanyLoan)
            .filter(
                ClientCompanyLoan.id == application.parent_loan_id,
                ClientCompanyLoan.company_id == context.company_id,
                ClientCompanyLoan.borrower_id == application.borrower_id,
                ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
            )
            .with_for_update()
            .first()
        )
        if not parent_loan:
            raise HTTPException(status_code=409, detail="The existing loan selected for this top-up is no longer active")
        top_up_settlement_amount = Decimal(parent_loan.balance)
        top_up_cash_amount = Decimal(payload.approved_amount) - top_up_settlement_amount
        if top_up_cash_amount <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"The approved top-up amount must exceed the existing balance of {top_up_settlement_amount}",
            )

    if len(payload.installment_due_dates) != application.term_count:
        raise HTTPException(
            status_code=422,
            detail=f"Enter exactly {application.term_count} installment due dates before approving the loan",
        )
    try:
        monthly, total, calculation_breakdown = calculate_loan_terms(
            principal=payload.approved_amount,
            rate_percent=interest_rate,
            term_months=application.term_count,
            processing_fee=processing_fee,
            interest_method=product.interest_method or "micro_loan",
            due_dates=payload.installment_due_dates,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    application.installment_due_dates = [value.isoformat() for value in payload.installment_due_dates]
    application.first_payment_date = payload.installment_due_dates[0]
    application.preferred_payment_day = None
    calculation_breakdown["top_up"] = {
        "is_top_up": application.application_type == "top_up",
        "parent_loan_id": str(parent_loan.id) if parent_loan else None,
        "settlement_amount": str(top_up_settlement_amount),
        "cash_to_borrower": str(top_up_cash_amount),
    }
    company = db.get(LoanCompany, application.company_id)
    if not company:
        raise HTTPException(status_code=409, detail="Lending company is unavailable")

    loan = ClientCompanyLoan(
        loan_request_id=None,
        loan_offer_id=None,
        company_id=application.company_id,
        branch_id=application.branch_id,
        borrower_id=application.borrower_id,
        loan_reference=generate_loan_reference(db, company),
        origination_channel=application.channel,
        direct_application_id=application.id,
        is_top_up=application.application_type == "top_up",
        parent_loan_id=parent_loan.id if parent_loan else None,
        top_up_settlement_amount=top_up_settlement_amount,
        top_up_cash_amount=top_up_cash_amount,
        principal_amount=payload.approved_amount,
        interest_rate=interest_rate,
        processing_fee=processing_fee,
        total_repayable=total,
        repayment_type=application.repayment_type,
        repayment_period=application.term_count,
        installment_amount=monthly,
        calculation_method=calculation_breakdown["method"],
        calculation_breakdown=calculation_breakdown,
        first_payment_due=application.first_payment_date,
        preferred_payment_day=application.preferred_payment_day,
        amount_paid=0,
        balance=total,
        status=LoanStatus.APPROVED,
        risk_level=(
            RiskLevel.HIGH
            if (application.credit_warning or {}).get("blacklisted")
            else RiskLevel.MEDIUM
        ),
        approved_at=datetime.now(timezone.utc),
        approved_by_user_id=context.user.id,
    )
    db.add(loan)
    try:
        db.flush()
        create_repayment_schedule(db, loan)

        application.status = "approved"
        application.product_id = product.id
        application.approved_amount = payload.approved_amount
        if application.application_type == "top_up":
            application.top_up_settlement_amount = top_up_settlement_amount
            application.top_up_cash_to_borrower = top_up_cash_amount
        application.interest_rate = interest_rate
        application.approved_at = datetime.now(timezone.utc)
        application.approved_by_user_id = context.user.id
        application.decision_notes = (payload.decision_notes or "").strip() or application.decision_notes
        application.loan_id = loan.id
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This application has already been converted into a loan",
        ) from exc
    db.refresh(application)
    db.refresh(loan)
    return {
        "application": _application_payload(db, application),
        "loan": serialize(loan),
    }


@router.post("/direct-applications/{application_id}/reject")
def reject_direct_application(
    application_id: UUID,
    payload: DirectApplicationReject,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, DIRECT_APPLICATION_APPROVAL_ROLES)
    application = _direct_application_or_404(
        db,
        application_id=application_id,
        context=context,
        lock=True,
    )
    if application.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="Application is not awaiting a decision")
    application.status = "rejected"
    application.rejected_at = datetime.now(timezone.utc)
    application.rejected_by_user_id = context.user.id
    application.decision_notes = payload.reason.strip()
    db.commit()
    db.refresh(application)
    return _application_payload(db, application)


def _create_platform_query(payload: SuggestionCreate, db: Session, context: TenantContext):
    item = Suggestion(
        company_id=context.company_id,
        branch_id=context.branch_id,
        submitted_by_user_id=context.user.id,
        reference=ref('QRY' if payload.category == 'support_query' else 'SGT'),
        title=payload.title,
        category=payload.category,
        description=payload.description,
        priority=payload.priority,
    )
    db.add(item)
    db.flush()
    admins = db.query(User).filter(User.role == UserRole.SUPERADMIN, User.is_active.is_(True)).all()
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            actor_user_id=context.user.id,
            company_id=context.company_id,
            branch_id=context.branch_id,
            title='New user query' if payload.category == 'support_query' else 'New platform suggestion',
            message=f'{item.reference}: {item.title}',
            notification_type=NotificationType.SYSTEM,
            event_type='platform.query.submitted',
            action='view',
            entity_type='platform_suggestion',
            entity_id=str(item.id),
            action_url='/superadmin/queries',
            priority=payload.priority,
            deduplication_key=f'platform-query:{item.id}',
        ))
    db.commit()
    db.refresh(item)
    return serialize(item)

@router.post('/suggestions',status_code=201)
def create_suggestion(payload:SuggestionCreate,db:Session=Depends(get_db),context:TenantContext=Depends(get_user_context)):
    return _create_platform_query(payload, db, context)

@router.post('/queries',status_code=201)
def create_query(payload:SuggestionCreate,db:Session=Depends(get_db),context:TenantContext=Depends(get_user_context)):
    payload.category = 'support_query'
    return _create_platform_query(payload, db, context)

@router.get('/suggestions')
@router.get('/queries')
def list_suggestions(db:Session=Depends(get_db),context:TenantContext=Depends(get_user_context)):
    q=db.query(Suggestion)
    if not context.is_platform_admin:
        if context.user.role == UserRole.BORROWER:
            q=q.filter(Suggestion.submitted_by_user_id==context.user.id)
        else:
            q=q.filter(Suggestion.company_id==context.company_id)
    return [serialize(x) for x in q.order_by(Suggestion.created_at.desc()).limit(500)]
@router.patch('/suggestions/{suggestion_id}')
def update_suggestion(suggestion_id:UUID,payload:SuggestionUpdate,db:Session=Depends(get_db),admin:User=Depends(require_platform_admin)):
    item=db.get(Suggestion,suggestion_id)
    if not item:raise HTTPException(404,'Suggestion not found')
    item.status=payload.status;item.platform_response=payload.platform_response;db.commit();return serialize(item)

@router.post('/wall-posts',status_code=201)
def create_wall_post(payload:WallPostCreate,db:Session=Depends(get_db),context:TenantContext=Depends(get_user_context)):
    require_tenant_roles(context,COMPANY_MANAGEMENT_ROLES|LENDING_ROLES)
    post=OfferWallPost(company_id=context.company_id,branch_id=payload.branch_id,product_id=payload.product_id,title=payload.title,summary=payload.summary,terms=payload.terms,status='published' if payload.publish else 'draft',published_at=datetime.now(timezone.utc) if payload.publish else None,expires_at=payload.expires_at,created_by_user_id=context.user.id)
    db.add(post);db.commit();db.refresh(post);return serialize(post)
@router.get('/wall-posts')
def wall_posts(db:Session=Depends(get_db)):
    now=datetime.now(timezone.utc)
    rows=db.query(OfferWallPost,LoanCompany.name).join(LoanCompany,LoanCompany.id==OfferWallPost.company_id).filter(OfferWallPost.status=='published',or_(OfferWallPost.expires_at.is_(None),OfferWallPost.expires_at>now)).order_by(OfferWallPost.published_at.desc()).all()
    return [{**serialize(p),'company_name':name} for p,name in rows]
@router.post('/wall-posts/{post_id}/interest',status_code=201)
def wall_interest(post_id:UUID,db:Session=Depends(get_db),context:TenantContext=Depends(get_user_context)):
    if context.user.role!=UserRole.BORROWER: raise HTTPException(403,'Borrower account required')
    borrower=db.query(Borrower).filter(Borrower.user_id==context.user.id).first()
    if not borrower:raise HTTPException(409,'Borrower profile required')
    existing=db.query(OfferWallInterest).filter_by(post_id=post_id,borrower_id=borrower.id).first()
    if existing:return serialize(existing)
    item=OfferWallInterest(post_id=post_id,borrower_id=borrower.id);db.add(item);db.commit();db.refresh(item);return serialize(item)

@router.post('/print-agents',status_code=201)
def register_agent(payload:PrintAgentCreate,db:Session=Depends(get_db),context:TenantContext=Depends(get_user_context)):
    require_tenant_roles(context,COMPANY_MANAGEMENT_ROLES|FINANCE_ROLES)
    raw=secrets.token_urlsafe(40); item=PrintAgent(user_id=context.user.id,company_id=context.company_id,name=payload.name,secret_hash=hashlib.sha256(raw.encode()).hexdigest())
    db.add(item);db.commit();db.refresh(item);return {'agent_id':str(item.id),'agent_secret':raw,'name':item.name}
@router.post('/print-jobs',status_code=201)
def create_print(payload:PrintJobCreate,db:Session=Depends(get_db),context:TenantContext=Depends(get_user_context)):
    agent=db.get(PrintAgent,payload.agent_id)
    if not agent or agent.company_id!=context.company_id:raise HTTPException(404,'Print agent not found')
    item=PrintJob(agent_id=agent.id,requested_by_user_id=context.user.id,file_id=payload.file_id,printer_name=payload.printer_name,copies=payload.copies)
    db.add(item);db.commit();db.refresh(item);return serialize(item)

def _assistant_guide(role: UserRole):
    if role == UserRole.BORROWER:
        return [
            (("cash", "payment", "repay"), "/borrower/payments", "View cash repayment receipts and loan balances."),
            (("loan", "balance"), "/borrower/loans", "View your loans, balances and repayment options."),
            (("offer", "advert", "wall"), "/borrower/offers-wall", "Browse offers published by participating lending companies."),
            (("query", "support", "suggest", "problem"), "/borrower/queries", "Submit a traceable query or suggestion to the platform owner."),
            (("chat", "message"), "/borrower/chat", "Open secure LoanHub chat."),
        ]
    if role == UserRole.SUPERADMIN:
        return [
            (("cash", "payment"), "/superadmin/payments", "Monitor cash-in and cash-out records across the platform."),
            (("query", "support", "suggest"), "/superadmin/queries", "Review and respond to user queries and product suggestions."),
            (("company", "lender"), "/superadmin/companies", "Review and manage lending companies."),
            (("error", "incident"), "/superadmin/system-errors", "Review technical incidents reported by LoanHub."),
            (("chat", "message"), "/superadmin/chat", "Open secure LoanHub chat."),
        ]
    return [
        (("cash", "payment", "disburse", "instalment"), "/company/cashier", "Receive cash instalments, record partial or advance payments and disburse approved loans in cash."),
        (("branch",), "/company/branches", "Create and manage operating branches."),
        (("staff", "employee"), "/company/staff", "Create staff accounts and assign roles."),
        (("walk in", "walk-in", "direct lending"), "/company/direct-lending", "Capture a walk-in client and create a direct loan application."),
        (("accounting", "journal"), "/company/accounting", "Review journals and financial statements."),
        (("report",), "/company/reports", "Generate or download operational reports."),
        (("query", "support", "suggest", "problem"), "/company/queries", "Submit a traceable query or functionality suggestion to the platform owner."),
        (("product", "offer", "advert"), "/company/products", "Manage loan products and terms that can be promoted to borrowers."),
        (("chat", "message"), "/company/chat", "Open secure LoanHub chat."),
    ]


@router.post('/assistant')
def assistant(payload: AssistantQuestion, context: TenantContext = Depends(get_user_context)):
    question = payload.question.lower().strip()
    for keywords, path, answer in _assistant_guide(context.user.role):
        if any(keyword in question for keyword in keywords):
            return {
                'answer': answer,
                'action_label': 'Open page',
                'action_path': path,
            }
    return {
        'answer': (
            'I can guide you through cash payments, loans, walk-in lending, '
            'branches, staff, accounting, reports, support queries, offer posts '
            'and secure chat. Ask what you want to do.'
        ),
        'action_label': None,
        'action_path': None,
    }

@router.get('/print-agent/jobs')
def agent_jobs(x_print_agent_id: str = Header(alias="X-Print-Agent-ID"), x_print_agent_secret: str = Header(alias="X-Print-Agent-Secret"), db: Session = Depends(get_db)):
    aid = UUID(x_print_agent_id)
    agent = db.get(PrintAgent, aid)
    digest = hashlib.sha256(x_print_agent_secret.encode()).hexdigest()
    if not agent or not agent.is_active or not secrets.compare_digest(agent.secret_hash, digest):
        raise HTTPException(401, 'Invalid print agent')
    agent.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return [serialize(x) for x in db.query(PrintJob).filter(PrintJob.agent_id == aid, PrintJob.status == 'queued').order_by(PrintJob.created_at).limit(20)]

@router.get('/print-agent/jobs/{job_id}/file')
def agent_job_file(job_id: UUID, x_print_agent_id: str = Header(alias="X-Print-Agent-ID"), x_print_agent_secret: str = Header(alias="X-Print-Agent-Secret"), db: Session = Depends(get_db)):
    from fastapi.responses import Response
    agent = db.get(PrintAgent, UUID(x_print_agent_id))
    job = db.get(PrintJob, job_id)
    digest = hashlib.sha256(x_print_agent_secret.encode()).hexdigest()
    if not agent or not job or job.agent_id != agent.id or not secrets.compare_digest(agent.secret_hash, digest):
        raise HTTPException(401, 'Invalid print agent')
    file = db.get(ManagedFile, job.file_id)
    if not file:
        raise HTTPException(404, 'Print file not found')
    return Response(read_file_bytes(file), media_type=file.mime_type, headers={'Content-Disposition': f'attachment; filename="{file.original_name}"'})

@router.post('/print-agent/jobs/{job_id}/complete')
def agent_job_complete(job_id: UUID, x_print_agent_id: str = Header(alias="X-Print-Agent-ID"), x_print_agent_secret: str = Header(alias="X-Print-Agent-Secret"), db: Session = Depends(get_db)):
    agent = db.get(PrintAgent, UUID(x_print_agent_id))
    job = db.get(PrintJob, job_id)
    digest = hashlib.sha256(x_print_agent_secret.encode()).hexdigest()
    if not agent or not job or job.agent_id != agent.id or not secrets.compare_digest(agent.secret_hash, digest):
        raise HTTPException(401, 'Invalid print agent')
    job.status = 'completed'
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {'status': 'completed'}
