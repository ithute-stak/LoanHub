from __future__ import annotations

from io import BytesIO
from datetime import date, datetime, timezone
import secrets
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_user_context,
    require_tenant_roles,
)
from database.models.borrower import Borrower
from database.models.audit_log import AuditLog
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import LoanRequestStatus, LoanStatus, OfferStatus, UserRole
from database.models.lending_operations import CDASPayrollProfile
from database.models.loan_product import LoanProduct
from database.models.loan_offer import LoanOffer
from database.models.loan_request import LoanRequest
from database.models.origination import (
    AffordabilityAssessment,
    LoanContract,
    OriginationIntegrationConfiguration,
)
from database.models.professional_lending import DirectLoanApplication
from database.schemas.origination import (
    AffordabilityCalculateRequest,
    AffordabilityOverrideRequest,
    ContractBorrowerSignRequest,
    ContractCompanySignRequest,
    ContractGenerateRequest,
    ContractRegenerateRequest,
    FinancialProfileUpdate,
    IntegrationConfigurationUpdate,
    OriginationApplicationCreate,
    OriginationApplicationUpdate,
    OriginationPolicyUpdate,
    TopUpExceptionApproveRequest,
)
from database.session import get_db
from utils.payment_dates import current_payment_date
from integrations.cdas import CdasError
from services.cdas_collection_policy import build_cdas_collection_plan
from services.cdas_config_service import get_company_cdas_client, get_configuration, selected_environment
from services.platform_cdas_service import (
    assert_live_credit_available,
    record_successful_operation,
    require_approved_subscription,
)
from services.contract_service import (
    contract_pdf_bytes,
    generate_contract,
    refresh_contract_pdf_after_signature,
    regenerate_contract_pdf,
    update_contract_status,
)
from services.credential_service import encrypt_credential
from services.lending_integration_service import application_integration_readiness
from services.top_up_settlement import preview_top_up_settlement, replacement_principal
from services.interest_calculation_service import calculate_loan_terms
from services.origination_service import (
    assessment_effective_decision,
    borrower_identity,
    calculate_affordability,
    duplicate_exposure,
    enforce_duplicate_policy,
    financial_profile_payload,
    get_or_create_policy,
    save_financial_profile,
    serialize,
    top_up_eligibility,
    update_policy,
)

router = APIRouter(prefix="/origination", tags=["Credit Origination, KYC and Affordability"])

ORIGINATION_VIEW_ROLES = LENDING_ROLES | {
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.FINANCE_OFFICER,
}
ORIGINATION_EDIT_ROLES = LENDING_ROLES | {
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
}
ORIGINATION_POLICY_ROLES = COMPANY_MANAGEMENT_ROLES
ORIGINATION_OVERRIDE_ROLES = COMPANY_MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER, UserRole.RISK_MANAGER}
CONTRACT_SIGN_ROLES = COMPANY_MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER}


def _product(db: Session, *, company_id: UUID, product_id: UUID | None) -> LoanProduct | None:
    if not product_id:
        return None
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


def _application(
    db: Session,
    *,
    context: TenantContext,
    application_id: UUID,
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
        raise HTTPException(status_code=404, detail="Origination application not found")
    assert_branch_scope(context, application.branch_id)
    return application


def _require_cdas_payroll_profile(db: Session, *, company_id: UUID, borrower_id: UUID) -> CDASPayrollProfile:
    profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == company_id,
            CDASPayrollProfile.borrower_id == borrower_id,
            CDASPayrollProfile.employee_number.isnot(None),
            CDASPayrollProfile.employee_number != "",
            CDASPayrollProfile.verified.is_(True),
        )
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=409,
            detail="A verified CDAS payroll profile with an employee number is required before this loan can use CDAS collection",
        )
    return profile


def _application_payload(db: Session, application: DirectLoanApplication) -> dict:
    data = serialize(application)
    identity = borrower_identity(db, application.borrower_id)
    data["borrower_name"] = identity["full_name"]
    data["identity"] = identity
    product = db.get(LoanProduct, application.product_id) if application.product_id else None
    data["product_name"] = product.name if product else None
    assessment = db.get(AffordabilityAssessment, application.affordability_assessment_id) if application.affordability_assessment_id else None
    data["affordability_decision"] = assessment_effective_decision(assessment)
    data["affordability_assessment"] = serialize(assessment) if assessment else None
    kyc = financial_profile_payload(db, company_id=application.company_id, borrower_id=application.borrower_id)["kyc"]
    data["kyc_status"] = (kyc or {}).get("status") if kyc else None
    loan = db.get(ClientCompanyLoan, application.loan_id) if application.loan_id else None
    data["loan_reference"] = loan.loan_reference if loan else None
    contract = db.query(LoanContract).filter(LoanContract.loan_id == application.loan_id).first() if application.loan_id else None
    data["contract_status"] = contract.status if contract else None
    data["contract_id"] = contract.id if contract else None
    return data


def _contract_payload(contract: LoanContract) -> dict:
    data = serialize(contract)
    data["download_url"] = f"/files/{contract.pdf_file_id}/download" if contract.pdf_file_id else None
    raw_style = str((contract.terms_snapshot or {}).get("contract_template_style") or "loanhub_standard").strip().lower()
    data["template_style"] = "filizwa_style" if raw_style in {"filizwa", "filizwa_style", "filizwa-style"} else "loanhub_standard"
    return data


@router.get("/policy")
def get_policy(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    policy = get_or_create_policy(db, context.company_id, context.user.id)
    db.commit()
    db.refresh(policy)
    return serialize(policy)


@router.put("/policy")
def put_policy(
    payload: OriginationPolicyUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_POLICY_ROLES)
    return serialize(update_policy(db, company_id=context.company_id, user_id=context.user.id, payload=payload))


@router.get("/borrowers/{borrower_id}/duplicate-check")
def check_duplicate(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    borrower_identity(db, borrower_id)
    return duplicate_exposure(db, borrower_id=borrower_id)


@router.get("/borrowers/{borrower_id}/top-up-eligibility")
def get_top_up_eligibility(
    borrower_id: UUID,
    loan_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    borrower_identity(db, borrower_id)
    policy = get_or_create_policy(db, context.company_id, context.user.id)
    return top_up_eligibility(
        db,
        borrower_id=borrower_id,
        company_id=context.company_id,
        policy=policy,
        loan_id=loan_id,
    )


@router.get("/borrowers/{borrower_id}/financial-profile")
def get_financial_profile(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    return financial_profile_payload(db, company_id=context.company_id, borrower_id=borrower_id)


@router.put("/borrowers/{borrower_id}/financial-profile")
def put_financial_profile(
    borrower_id: UUID,
    payload: FinancialProfileUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_EDIT_ROLES)
    return save_financial_profile(
        db,
        company_id=context.company_id,
        borrower_id=borrower_id,
        user_id=context.user.id,
        payload=payload,
        actor_role=context.role.value,
    )


@router.post("/applications", status_code=status.HTTP_201_CREATED)
def create_application(
    payload: OriginationApplicationCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    assert_branch_scope(context, payload.branch_id or context.branch_id)
    borrower = db.get(Borrower, payload.borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    client = (
        db.query(CompanyBorrowerAccount)
        .filter(
            CompanyBorrowerAccount.company_id == context.company_id,
            CompanyBorrowerAccount.borrower_id == payload.borrower_id,
            CompanyBorrowerAccount.status == "active",
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=409, detail="The borrower must be an active company client")

    policy = get_or_create_policy(db, context.company_id, context.user.id)
    eligibility = None
    requested_amount = Decimal(payload.requested_amount)
    top_up_cash_requested = None
    top_up_exception_requested = False
    if payload.application_type == "top_up":
        eligibility = top_up_eligibility(
            db,
            borrower_id=payload.borrower_id,
            company_id=context.company_id,
            policy=policy,
            loan_id=payload.parent_loan_id,
        )
        if not eligibility["loan"]:
            raise HTTPException(status_code=409, detail=eligibility["reason"])
        exposure = duplicate_exposure(db, borrower_id=payload.borrower_id)
        if len(exposure["open_applications"]) >= int(policy.max_open_applications or 1):
            references = ", ".join(item["reference"] for item in exposure["open_applications"])
            raise HTTPException(
                status_code=409,
                detail=f"The borrower already has an open application: {references}",
            )
        parent_loan_id = eligibility["loan"]["id"]
        unrelated_loans = [item for item in exposure["active_loans"] if item["id"] != parent_loan_id]
        if unrelated_loans and not policy.allow_concurrent_active_loans:
            references = ", ".join(item["reference"] for item in unrelated_loans)
            raise HTTPException(
                status_code=409,
                detail=f"The borrower has another active loan that is not part of this top-up: {references}",
            )
        top_up_cash_requested = Decimal(payload.top_up_cash_requested or 0)
        parent = db.query(ClientCompanyLoan).filter(
            ClientCompanyLoan.id == parent_loan_id,
            ClientCompanyLoan.company_id == context.company_id,
        ).with_for_update().one()
        settlement_quote = preview_top_up_settlement(db, loan=parent, actor_user_id=context.user.id)
        requested_amount = replacement_principal(settlement_quote, top_up_cash_requested)
        if not eligibility["eligible"]:
            if not eligibility["requires_owner_exception"]:
                raise HTTPException(status_code=409, detail=eligibility["reason"])
            if not (payload.top_up_exception_reason or "").strip():
                raise HTTPException(status_code=422, detail="Explain why an owner exception is requested for this top-up")
            top_up_exception_requested = True
    else:
        enforce_duplicate_policy(
            db,
            borrower_id=payload.borrower_id,
            company_id=context.company_id,
            policy=policy,
        )

    # Inherit the parent loan's active product for the compact top-up when
    # the client has not selected another product. The assessment still
    # recalculates affordability and the final installment schedule.
    inherited_product_id = payload.product_id
    if payload.application_type == "top_up" and inherited_product_id is None:
        source = (
            db.query(DirectLoanApplication)
            .filter(
                DirectLoanApplication.id == parent.direct_application_id,
                DirectLoanApplication.company_id == context.company_id,
            )
            .first()
            if parent.direct_application_id else None
        )
        inherited_product_id = source.product_id if source else None
    product = _product(db, company_id=context.company_id, product_id=inherited_product_id)
    if product:
        if not (Decimal(product.min_amount) <= requested_amount <= Decimal(product.max_amount)):
            raise HTTPException(status_code=422, detail="Requested amount, including any old-loan settlement, is outside the selected product range")
        if not (product.min_term_months <= payload.term_count <= product.max_term_months):
            raise HTTPException(status_code=422, detail="Term is outside the selected product range")

    now = datetime.now(timezone.utc)
    application = DirectLoanApplication(
        company_id=context.company_id,
        branch_id=payload.branch_id or client.branch_id or context.branch_id,
        borrower_id=payload.borrower_id,
        product_id=inherited_product_id,
        application_reference=f"{'TOP' if payload.application_type == 'top_up' else 'ORG'}-{now:%Y%m%d}-{secrets.token_hex(4).upper()}",
        channel="credit_origination",
        application_type=payload.application_type,
        parent_loan_id=payload.parent_loan_id,
        requested_amount=requested_amount,
        top_up_cash_requested=top_up_cash_requested,
        top_up_settlement_amount=(settlement_quote.settlement_amount if eligibility else None),
        top_up_cash_to_borrower=top_up_cash_requested,
        top_up_eligibility_snapshot=(eligibility or {}),
        top_up_exception_requested=top_up_exception_requested,
        top_up_exception_reason=(payload.top_up_exception_reason or "").strip() or None,
        term_count=payload.term_count,
        repayment_type="monthly",
        purpose=payload.purpose,
        preferred_payment_day=None,
        first_payment_date=payload.installment_due_dates[0],
        installment_due_dates=[value.isoformat() for value in payload.installment_due_dates],
        cdas_collection_enabled=payload.cdas_collection_enabled,
        cdas_collection_plan=build_cdas_collection_plan(
            enabled=payload.cdas_collection_enabled,
            installment_due_dates=payload.installment_due_dates,
            term_count=payload.term_count,
            selected_by_user_id=context.user.id,
            selected_at=now,
        ),
        application_step=1,
        status="draft",
        captured_by_user_id=context.user.id,
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A duplicate application reference was generated; retry the request") from exc
    db.refresh(application)
    return _application_payload(db, application)


@router.get("/loans/{loan_id}/top-up-settlement-preview")
def top_up_settlement_preview(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.BRANCH_MANAGER})
    loan = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == context.company_id,
    ).first()
    if not loan:
        raise HTTPException(404, "Loan not found")
    assert_branch_scope(context, loan.branch_id)
    policy = get_or_create_policy(db, context.company_id, context.user.id)
    eligible = top_up_eligibility(
        db, borrower_id=loan.borrower_id, company_id=context.company_id,
        policy=policy, loan_id=loan.id,
    )
    if not (eligible["eligible"] or eligible["requires_owner_exception"]):
        raise HTTPException(409, eligible["reason"])
    quote = preview_top_up_settlement(db, loan=loan, actor_user_id=context.user.id)
    return {
        "loan_id": str(loan.id),
        "scheduled_balance": str(loan.balance),
        "settlement_amount": str(quote.settlement_amount),
        "unearned_interest_rebate": str(quote.unearned_interest_rebate),
        "earned_interest": str(quote.earned_interest),
        "calculation_method": quote.calculation_method,
        "settlement_date": quote.settlement_date.isoformat(),
        "original_amount_paid": str(quote.original_amount_paid),
    }


class TopUpCalculationPreviewRequest(BaseModel):
    cash_top_up: Decimal = Field(gt=0)
    due_dates: list[date] = Field(min_length=1, max_length=120)


@router.post("/loans/{loan_id}/top-up-calculation-preview")
def top_up_calculation_preview(
    loan_id: UUID,
    payload: TopUpCalculationPreviewRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.BRANCH_MANAGER})
    loan = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == context.company_id,
    ).first()
    if not loan:
        raise HTTPException(404, "Loan not found")
    assert_branch_scope(context, loan.branch_id)
    policy = get_or_create_policy(db, context.company_id, context.user.id)
    eligibility = top_up_eligibility(
        db, borrower_id=loan.borrower_id, company_id=context.company_id,
        policy=policy, loan_id=loan.id,
    )
    if not (eligibility["eligible"] or eligibility["requires_owner_exception"]):
        raise HTTPException(409, eligibility["reason"])

    source = (
        db.query(DirectLoanApplication)
        .filter(
            DirectLoanApplication.id == loan.direct_application_id,
            DirectLoanApplication.company_id == context.company_id,
        )
        .first()
        if loan.direct_application_id else None
    )
    product = _product(
        db, company_id=context.company_id,
        product_id=source.product_id if source else None,
    )
    quote = preview_top_up_settlement(db, loan=loan, actor_user_id=context.user.id)
    principal = replacement_principal(quote, payload.cash_top_up)
    term = len(payload.due_dates)
    if product and not (
        product.min_amount <= principal <= product.max_amount
        and product.min_term_months <= term <= product.max_term_months
    ):
        raise HTTPException(422, "Replacement loan does not satisfy current product limits")
    method = product.interest_method if product else loan.calculation_method
    rate = product.interest_rate_percent if product else loan.interest_rate
    fee = product.processing_fee if product else loan.processing_fee
    try:
        monthly, total, details = calculate_loan_terms(
            principal=principal,
            rate_percent=rate,
            term_months=term,
            processing_fee=fee,
            interest_method=method,
            start_date=current_payment_date(),
            due_dates=payload.due_dates,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "settlement_amount": str(quote.settlement_amount),
        "new_principal": str(principal),
        "monthly_installment": str(monthly),
        "total_repayable": str(total),
        "interest_rate_percent": str(rate),
        "interest_method": str(method.value if hasattr(method, "value") else method),
        "processing_fee": str(fee),
        "product_id": str(product.id) if product else None,
        "schedule_amounts": details["schedule_amounts"],
        "requires_credit_assessment": True,
    }


@router.post("/applications/{application_id}/refresh-draft-top-up")
def refresh_draft_top_up(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Refresh old draft principal/remaining dates before a new assessment.

    No loan or payout is created. Only authorized owners/managers can refresh.
    """
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.BRANCH_MANAGER})
    application = _application(db, context=context, application_id=application_id, lock=True)
    if application.application_type != "top_up" or application.status != "draft" or application.loan_id:
        raise HTTPException(409, "Only an unapproved draft top-up can be refreshed")
    if not application.parent_loan_id:
        raise HTTPException(409, "The original loan is missing")
    parent = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == application.parent_loan_id,
        ClientCompanyLoan.company_id == context.company_id,
        ClientCompanyLoan.borrower_id == application.borrower_id,
        ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
    ).with_for_update().first()
    if parent is None:
        raise HTTPException(409, "Original loan is no longer active")
    today = current_payment_date()
    remaining_dates = sorted(
        item.due_date
        for item in parent.installments
        if not item.is_superseded
        and Decimal(item.total_due) > Decimal(item.paid_amount)
        and item.due_date >= today
    )
    if not remaining_dates or len(remaining_dates) > 120:
        raise HTTPException(409, "Remaining loan dates require manual review")
    cash = Decimal(application.top_up_cash_requested or 0)
    quote = preview_top_up_settlement(db, loan=parent, actor_user_id=context.user.id)
    principal = replacement_principal(quote, cash)
    application.requested_amount = principal
    application.top_up_settlement_amount = quote.settlement_amount
    application.top_up_cash_to_borrower = cash
    application.term_count = len(remaining_dates)
    application.installment_due_dates = [value.isoformat() for value in remaining_dates]
    application.first_payment_date = remaining_dates[0]
    application.affordability_assessment_id = None
    application.application_step = 1
    db.commit()
    db.refresh(application)
    return _application_payload(db, application)


@router.post("/applications/compact-top-up", status_code=status.HTTP_201_CREATED)
def create_compact_top_up(
    payload: OriginationApplicationCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Owner/branch-manager-only compact top-up; standard credit approvals stay mandatory."""
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.BRANCH_MANAGER})
    if payload.application_type != "top_up" or payload.parent_loan_id is None:
        raise HTTPException(status_code=422, detail="An existing loan is required")
    return create_application(payload=payload, db=db, context=context)


@router.patch("/applications/{application_id}")
def update_application(
    application_id: UUID,
    payload: OriginationApplicationUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_EDIT_ROLES)
    application = _application(db, context=context, application_id=application_id, lock=True)
    if application.status not in {"draft", "submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="This application can no longer be edited")
    changes = payload.model_dump(exclude_unset=True)
    supplied_due_dates = changes.pop("installment_due_dates", None)
    cdas_selection = changes.pop("cdas_collection_enabled", None)
    was_cdas_enabled = bool(application.cdas_collection_enabled)
    final_term_count = int(changes.get("term_count", application.term_count))
    if supplied_due_dates is None:
        resolved_due_dates = list(application.installment_due_dates or [])
    else:
        resolved_due_dates = [value.isoformat() for value in supplied_due_dates]
    if len(resolved_due_dates) != final_term_count:
        raise HTTPException(
            status_code=422,
            detail=f"Enter exactly {final_term_count} installment due dates before saving the application",
        )
    if supplied_due_dates is not None:
        previous_due_dates = list(application.installment_due_dates or [])
        dates_changed = previous_due_dates != resolved_due_dates
        if dates_changed and application.application_type == "top_up":
            if application.status != "draft" or application.loan_id is not None or application.approved_at is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Only an unapproved, undisbursed draft top-up may be rescheduled here.",
                )
            db.add(AuditLog(
                user_id=context.user.id,
                company_id=context.company_id,
                branch_id=application.branch_id,
                action="top_up.installments_rescheduled",
                table_name="direct_loan_application",
                entity_type="application",
                record_id=application.id,
                description="Top-up installment schedule revised before approval and disbursement.",
                actor_role=context.role.value,
                status="success",
                event_data={
                    "original_due_dates": previous_due_dates,
                    "revised_due_dates": resolved_due_dates,
                    "application_reference": application.application_reference,
                },
            ))
            application.affordability_assessment_id = None
        application.installment_due_dates = resolved_due_dates
        application.first_payment_date = supplied_due_dates[0]
        application.preferred_payment_day = None
    if "product_id" in changes:
        _product(db, company_id=context.company_id, product_id=changes["product_id"])
    if application.application_type == "top_up":
        policy = get_or_create_policy(db, context.company_id, context.user.id)
        eligibility = top_up_eligibility(
            db,
            borrower_id=application.borrower_id,
            company_id=context.company_id,
            policy=policy,
            loan_id=application.parent_loan_id,
        )
        if not eligibility["loan"]:
            raise HTTPException(status_code=409, detail=eligibility["reason"])
        changes.pop("requested_amount", None)
        cash_requested = Decimal(
            changes.pop("top_up_cash_requested", application.top_up_cash_requested or 0)
        )
        parent = db.query(ClientCompanyLoan).filter(
            ClientCompanyLoan.id == application.parent_loan_id,
            ClientCompanyLoan.company_id == context.company_id,
        ).with_for_update().one()
        settlement_quote = preview_top_up_settlement(db, loan=parent, actor_user_id=context.user.id)
        settlement_amount = settlement_quote.settlement_amount
        application.top_up_cash_requested = cash_requested
        application.top_up_settlement_amount = settlement_amount
        application.top_up_cash_to_borrower = cash_requested
        application.requested_amount = replacement_principal(settlement_quote, cash_requested)
        application.top_up_eligibility_snapshot = eligibility
        if not eligibility["eligible"]:
            if not eligibility["requires_owner_exception"]:
                raise HTTPException(status_code=409, detail=eligibility["reason"])
            reason = str(changes.get("top_up_exception_reason") or application.top_up_exception_reason or "").strip()
            if not reason:
                raise HTTPException(status_code=422, detail="Explain why an owner exception is requested for this top-up")
            application.top_up_exception_requested = True
            application.top_up_exception_reason = reason
        else:
            application.top_up_exception_requested = False
            application.top_up_exception_reason = None
        changes.pop("top_up_exception_reason", None)
    for key, value in changes.items():
        setattr(application, key, value)

    if cdas_selection is not None:
        application.cdas_collection_enabled = bool(cdas_selection)
    if application.cdas_collection_enabled:
        existing_plan = dict(application.cdas_collection_plan or {})
        rebuilt_plan = build_cdas_collection_plan(
            enabled=True,
            installment_due_dates=application.installment_due_dates or [],
            term_count=application.term_count,
            selected_by_user_id=(context.user.id if cdas_selection is not None else None),
            selected_at=(datetime.now(timezone.utc) if cdas_selection is True and not was_cdas_enabled else None),
        )
        if cdas_selection is None:
            rebuilt_plan["selected_by_user_id"] = existing_plan.get("selected_by_user_id")
        if existing_plan.get("selected_at") and "selected_at" not in rebuilt_plan:
            rebuilt_plan["selected_at"] = existing_plan["selected_at"]
        application.cdas_collection_plan = rebuilt_plan
    else:
        application.cdas_collection_plan = {}

    product = _product(db, company_id=context.company_id, product_id=application.product_id)
    if product:
        if not (Decimal(product.min_amount) <= Decimal(application.requested_amount) <= Decimal(product.max_amount)):
            raise HTTPException(status_code=422, detail="Requested amount, including any old-loan settlement, is outside the selected product range")
        if not (product.min_term_months <= application.term_count <= product.max_term_months):
            raise HTTPException(status_code=422, detail="Term is outside the selected product range")
    db.commit()
    db.refresh(application)
    return _application_payload(db, application)


@router.get("/applications")
def list_applications(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    query = db.query(DirectLoanApplication).filter(
        DirectLoanApplication.company_id == context.company_id,
        DirectLoanApplication.channel == "credit_origination",
        DirectLoanApplication.status != "cancelled",
    )
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(DirectLoanApplication.branch_id == context.branch_id)
    return [_application_payload(db, item) for item in query.order_by(DirectLoanApplication.created_at.desc()).limit(500)]


@router.delete("/applications/{application_id}/draft-top-up")
def delete_draft_top_up(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Soft-delete a never-submitted top-up without touching the parent loan.

    Keep the application as an audit record; cancelled drafts no longer
    participate in duplicate-exposure checks or default list views.
    """
    require_tenant_roles(context, {UserRole.COMPANY_OWNER, UserRole.BRANCH_MANAGER})
    application = _application(db, context=context, application_id=application_id, lock=True)
    if application.application_type != "top_up" or application.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft top-up applications can be deleted")
    if (
        application.submitted_at is not None
        or application.approved_at is not None
        or application.loan_id is not None
    ):
        raise HTTPException(status_code=409, detail="This top-up has progressed and cannot be deleted")
    # A company-owner top-up threshold exception can be granted while the
    # application is still a draft. That exception is NOT loan approval.
    # Preserve its audit fields instead of blocking draft cancellation.
    application.status = "cancelled"
    application.decision_notes = (
        (application.decision_notes or "")
        + f"\\nDraft top-up deleted by {context.user.id} at {datetime.now(timezone.utc).isoformat()}."
    ).strip()
    db.commit()
    return {"id": str(application.id), "status": "cancelled"}


@router.get("/applications/{application_id}/workspace")
def application_workspace(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    application = _application(db, context=context, application_id=application_id)
    policy = get_or_create_policy(db, context.company_id, context.user.id)
    profile = financial_profile_payload(db, company_id=context.company_id, borrower_id=application.borrower_id)
    exposure = duplicate_exposure(db, borrower_id=application.borrower_id, exclude_application_id=application.id, exclude_loan_id=application.loan_id)
    assessments = (
        db.query(AffordabilityAssessment)
        .filter(AffordabilityAssessment.application_id == application.id)
        .order_by(AffordabilityAssessment.assessment_number.desc())
        .all()
    )
    return {
        "application": _application_payload(db, application),
        "policy": serialize(policy),
        "profile": profile,
        "duplicate_check": exposure,
        "assessments": [serialize(item) for item in assessments],
        "integration_readiness": application_integration_readiness(
            db,
            application=application,
            amount=Decimal(application.requested_amount or 0),
            product_id=application.product_id,
        ),
    }


@router.get("/applications/{application_id}/integration-readiness")
def application_integration_status(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    application = _application(db, context=context, application_id=application_id)
    return application_integration_readiness(
        db,
        application=application,
        amount=Decimal(application.requested_amount or 0),
        product_id=application.product_id,
    )


@router.post("/applications/{application_id}/assess")
async def assess_application(
    application_id: UUID,
    payload: AffordabilityCalculateRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_EDIT_ROLES)
    application = _application(db, context=context, application_id=application_id, lock=True)

    verified_cdas_profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == context.company_id,
            CDASPayrollProfile.borrower_id == application.borrower_id,
            CDASPayrollProfile.employee_number.isnot(None),
            CDASPayrollProfile.employee_number != "",
            CDASPayrollProfile.verified.is_(True),
        )
        .first()
    )
    live_cdas_affordability = None
    if verified_cdas_profile:
        subscription = require_approved_subscription(db, company_id=context.company_id)
        cdas_configuration = get_configuration(db, context.company_id)
        environment = selected_environment(cdas_configuration)
        assert_live_credit_available(
            db,
            subscription=subscription,
            environment=environment,
            operation_type="affordability",
        )
        client = get_company_cdas_client(db, context.company_id)
        try:
            live_cdas_affordability = await client.check_affordability(
                str(verified_cdas_profile.employee_number)
            )
        except CdasError as exc:
            raise HTTPException(
                status_code=exc.status_code if 400 <= exc.status_code <= 599 else 502,
                detail=f"CDAS affordability could not be verified: {exc.message}",
            ) from exc
        record_successful_operation(
            db,
            company_id=context.company_id,
            environment=environment,
            operation_type="affordability",
            actor_user_id=context.user.id,
            billing_key=f"cdas-affordability:{application.id}:{uuid4().hex}",
            source_reference=str(application.id),
            metadata={
                "request_origin": "origination_affordability",
                "employee_number_present": True,
            },
        )

    assessment = calculate_affordability(
        db,
        company_id=context.company_id,
        borrower_id=application.borrower_id,
        application=application,
        principal=payload.proposed_principal,
        rate_percent=payload.proposed_rate_percent,
        months=payload.proposed_months,
        processing_fee=payload.processing_fee,
        interest_method=payload.interest_method,
        calculated_by_user_id=context.user.id,
        live_cdas_affordability=live_cdas_affordability,
    )
    return serialize(assessment)


@router.post("/assessments/{assessment_id}/override")
def override_assessment(
    assessment_id: UUID,
    payload: AffordabilityOverrideRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_OVERRIDE_ROLES)
    assessment = (
        db.query(AffordabilityAssessment)
        .filter(
            AffordabilityAssessment.id == assessment_id,
            AffordabilityAssessment.company_id == context.company_id,
        )
        .with_for_update()
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Affordability assessment not found")
    policy = get_or_create_policy(db, context.company_id, context.user.id)
    # The company owner may explicitly accept credit risk even when routine
    # management affordability overrides are disabled. This does not waive KYC,
    # sanctions, identity, payroll or other statutory safeguards.
    owner_risk_acceptance = context.role == UserRole.COMPANY_OWNER and payload.decision in {"eligible", "conditionally_eligible"}
    if not policy.manager_override_enabled and not owner_risk_acceptance:
        raise HTTPException(status_code=403, detail="Affordability overrides are disabled by company policy")
    assessment.overridden = True
    assessment.override_decision = payload.decision
    assessment.override_reason = payload.reason
    assessment.overridden_by_user_id = context.user.id
    assessment.overridden_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assessment)
    return serialize(assessment)


@router.post("/applications/{application_id}/top-up-exception/approve")
def approve_top_up_exception(
    application_id: UUID,
    payload: TopUpExceptionApproveRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, {UserRole.COMPANY_OWNER})
    application = _application(db, context=context, application_id=application_id, lock=True)
    if application.application_type != "top_up" or not application.top_up_exception_requested:
        raise HTTPException(status_code=409, detail="This application does not require a top-up exception")
    if application.status not in {"draft", "submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="This top-up application can no longer receive an exception decision")
    policy = get_or_create_policy(db, context.company_id, context.user.id)
    if not policy.top_up_owner_exception_enabled:
        raise HTTPException(status_code=403, detail="Owner top-up exceptions are disabled by company policy")
    application.top_up_exception_approved = True
    application.top_up_exception_approved_at = datetime.now(timezone.utc)
    application.top_up_exception_approved_by_user_id = context.user.id
    application.top_up_exception_reason = f"{application.top_up_exception_reason or ''}\nOwner approval: {payload.reason.strip()}".strip()
    db.commit()
    db.refresh(application)
    return _application_payload(db, application)


@router.post("/applications/{application_id}/submit")
def submit_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    application = _application(db, context=context, application_id=application_id, lock=True)
    if application.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft application can be submitted")
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
    profile = financial_profile_payload(db, company_id=context.company_id, borrower_id=application.borrower_id)
    if policy.require_kyc_verified and (not profile["kyc"] or profile["kyc"]["status"] != "verified"):
        raise HTTPException(status_code=409, detail="KYC must be verified before the application is submitted")
    assessment = db.get(AffordabilityAssessment, application.affordability_assessment_id) if application.affordability_assessment_id else None
    decision = assessment_effective_decision(assessment)
    if decision not in {"eligible", "conditionally_eligible"}:
        raise HTTPException(status_code=409, detail="A positive affordability assessment is required before submission")
    if application.cdas_collection_enabled:
        _require_cdas_payroll_profile(
            db,
            company_id=context.company_id,
            borrower_id=application.borrower_id,
        )
    application.status = "submitted"
    application.submitted_at = datetime.now(timezone.utc)
    application.application_step = 10
    db.commit()
    db.refresh(application)
    return _application_payload(db, application)


@router.post("/loans/{loan_id}/contract", status_code=status.HTTP_201_CREATED)
def create_contract(
    loan_id: UUID,
    payload: ContractGenerateRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONTRACT_SIGN_ROLES | {UserRole.LOAN_OFFICER})
    loan = (
        db.query(ClientCompanyLoan)
        .options(joinedload(ClientCompanyLoan.installments), joinedload(ClientCompanyLoan.borrower))
        .filter(ClientCompanyLoan.id == loan_id, ClientCompanyLoan.company_id == context.company_id)
        .first()
    )
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    assert_branch_scope(context, loan.branch_id)

    if loan.status == LoanStatus.PENDING and loan.loan_request_id and loan.loan_offer_id:
        online_request = db.get(LoanRequest, loan.loan_request_id)
        accepted_offer = db.get(LoanOffer, loan.loan_offer_id)
        if (
            online_request
            and accepted_offer
            and online_request.status == LoanRequestStatus.ACCEPTED
            and accepted_offer.status == OfferStatus.ACCEPTED
        ):
            loan.status = LoanStatus.APPROVED
            loan.approved_at = loan.approved_at or online_request.accepted_at or accepted_offer.accepted_at
            db.flush()

    if loan.disbursed_at is not None or loan.status in {
        LoanStatus.ACTIVE,
        LoanStatus.DEFAULTED,
        LoanStatus.COMPLETED,
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "This loan has already been disbursed. A pre-disbursement contract cannot "
                "be generated retrospectively; review the account and legal audit trail."
            ),
        )
    if loan.status != LoanStatus.APPROVED:
        raise HTTPException(
            status_code=409,
            detail=f"Loan must be approved before contract generation; current status is {loan.status.value}",
        )

    contract = generate_contract(
        db,
        loan=loan,
        requested_by_user_id=context.user.id,
        witness_name=payload.witness_name,
        template_style=payload.template_style,
        include_mandate=payload.include_mandate,
    )
    db.add(AuditLog(
        user_id=context.user.id,
        company_id=loan.company_id,
        branch_id=loan.branch_id,
        action="loan.contract_generated",
        table_name="client_company_loan",
        entity_type="loan",
        record_id=loan.id,
        description="Loan contract generated by authenticated staff.",
        actor_role=context.role.value,
        status="success",
        event_data={"loan_reference": loan.loan_reference, "contract_id": str(contract.id)},
    ))
    db.commit()
    return _contract_payload(contract)


@router.get("/contracts")
def list_contracts(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    query = db.query(LoanContract).filter(LoanContract.company_id == context.company_id)
    return [_contract_payload(item) for item in query.order_by(LoanContract.created_at.desc()).limit(500)]


@router.get("/contracts/{contract_id}/pdf")
def get_contract_pdf(
    contract_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_VIEW_ROLES)
    contract = (
        db.query(LoanContract)
        .options(joinedload(LoanContract.loan))
        .filter(LoanContract.id == contract_id, LoanContract.company_id == context.company_id)
        .first()
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    assert_branch_scope(context, contract.loan.branch_id if contract.loan else None)
    content = contract_pdf_bytes(
        db,
        contract=contract,
        requested_by_user_id=context.user.id,
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{contract.contract_number}.pdf"',
            "Cache-Control": "private, no-store, max-age=0",
        },
    )


@router.post("/contracts/{contract_id}/regenerate-pdf")
def regenerate_contract_document(
    contract_id: UUID,
    payload: ContractRegenerateRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONTRACT_SIGN_ROLES | {UserRole.LOAN_OFFICER})
    contract = (
        db.query(LoanContract)
        .options(joinedload(LoanContract.loan))
        .filter(LoanContract.id == contract_id, LoanContract.company_id == context.company_id)
        .first()
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    assert_branch_scope(context, contract.loan.branch_id if contract.loan else None)
    return _contract_payload(
        regenerate_contract_pdf(
            db,
            contract=contract,
            requested_by_user_id=context.user.id,
            template_style=payload.template_style,
        )
    )


@router.post("/contracts/{contract_id}/borrower-sign")
def borrower_sign_contract(
    contract_id: UUID,
    payload: ContractBorrowerSignRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_EDIT_ROLES | CONTRACT_SIGN_ROLES)
    contract = (
        db.query(LoanContract)
        .filter(LoanContract.id == contract_id, LoanContract.company_id == context.company_id)
        .with_for_update()
        .first()
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract.locked_at:
        raise HTTPException(status_code=409, detail="The signed contract is locked")
    contract.borrower_signature_name = payload.signature_name.strip()
    contract.borrower_signature_method = payload.signature_method
    contract.borrower_signed_at = datetime.now(timezone.utc)
    contract.witness_name = payload.witness_name or contract.witness_name
    update_contract_status(contract)
    refresh_contract_pdf_after_signature(
        db,
        contract=contract,
        requested_by_user_id=context.user.id,
    )
    db.commit()
    db.refresh(contract)
    return _contract_payload(contract)


@router.post("/contracts/{contract_id}/company-sign")
def company_sign_contract(
    contract_id: UUID,
    payload: ContractCompanySignRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONTRACT_SIGN_ROLES)
    contract = (
        db.query(LoanContract)
        .filter(LoanContract.id == contract_id, LoanContract.company_id == context.company_id)
        .with_for_update()
        .first()
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract.locked_at:
        raise HTTPException(status_code=409, detail="The signed contract is locked")
    contract.company_signer_user_id = context.user.id
    contract.company_signature_method = payload.signature_method
    contract.company_signed_at = datetime.now(timezone.utc)
    update_contract_status(contract)
    refresh_contract_pdf_after_signature(
        db,
        contract=contract,
        requested_by_user_id=context.user.id,
    )
    db.commit()
    db.refresh(contract)
    return _contract_payload(contract)


@router.get("/integrations")
def list_integrations(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_POLICY_ROLES | {UserRole.COMPLIANCE_OFFICER, UserRole.IT_SUPPORT})
    rows = db.query(OriginationIntegrationConfiguration).filter(OriginationIntegrationConfiguration.company_id == context.company_id).all()
    return [
        {
            **serialize(item),
            "encrypted_credentials": None,
            "has_credentials": bool(item.encrypted_credentials),
        }
        for item in rows
    ]


@router.put("/integrations/{provider}")
def put_integration(
    provider: str,
    payload: IntegrationConfigurationUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ORIGINATION_POLICY_ROLES)
    provider = provider.strip().lower()
    if provider not in {"experian", "mpesa", "debicheck", "sms", "email", "manual_bureau"}:
        raise HTTPException(status_code=422, detail="Unsupported origination integration provider")
    row = db.query(OriginationIntegrationConfiguration).filter_by(company_id=context.company_id, provider=provider).first()
    if not row:
        row = OriginationIntegrationConfiguration(company_id=context.company_id, provider=provider)
        db.add(row)
    row.environment = payload.environment
    row.is_enabled = payload.is_enabled
    row.configuration = payload.configuration
    row.configured_by_user_id = context.user.id
    if payload.credentials:
        row.encrypted_credentials = encrypt_credential(payload.credentials)
    db.commit()
    db.refresh(row)
    data = serialize(row)
    data["encrypted_credentials"] = None
    data["has_credentials"] = bool(row.encrypted_credentials)
    return data
