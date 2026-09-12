from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TRANSPARENCY_ROLES,
    TenantContext,
    get_user_context,
)
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import UserRole
from database.models.lending_operations import (
    CDASDeductionMandate,
    CDASPayrollProfile,
    CDASRemittanceBatch,
    CDASRemittanceLine,
    CollectionActivity,
    CollectionCase,
    ComplianceCase,
    ComplianceScreening,
    CreditBureauEnquiry,
    CreditDecision,
    CreditDecisionPolicy,
    ReconciliationException,
    ReconciliationRun,
    RegulatorySubmission,
    WorkflowInstance,
    WorkflowTemplate,
)
from database.schemas.lending_operations import (
    CDASAffordabilityRead,
    CDASAffordabilityRequest,
    CDASMandateCreate,
    CDASMandateRead,
    CDASMandateStatusUpdate,
    CDASPayrollProfileCreate,
    CDASPayrollProfileRead,
    CDASRemittanceBatchCreate,
    CDASRemittanceBatchRead,
    CDASRemittanceLineCreate,
    CDASRemittanceLineRead,
    CollectionActivityCreate,
    CollectionActivityRead,
    CollectionCaseCreate,
    CollectionCaseRead,
    CollectionCaseUpdate,
    ComplianceCaseCreate,
    ComplianceCaseRead,
    ComplianceCaseUpdate,
    ComplianceScreeningCreate,
    ComplianceScreeningRead,
    CreditBureauEnquiryComplete,
    CreditBureauEnquiryCreate,
    CreditBureauEnquiryRead,
    CreditDecisionEvaluateRequest,
    CreditDecisionPolicyCreate,
    CreditDecisionPolicyRead,
    CreditDecisionRead,
    DashboardMetric,
    LendingOperationsDashboard,
    ReconciliationExceptionRead,
    ReconciliationExceptionUpdate,
    ReconciliationRunCreate,
    ReconciliationRunRead,
    RegulatorySubmissionCreate,
    RegulatorySubmissionRead,
    RegulatorySubmissionUpdate,
    WorkflowAdvanceRequest,
    WorkflowInstanceCreate,
    WorkflowInstanceRead,
    WorkflowTemplateCreate,
    WorkflowTemplateRead,
)
from database.session import get_db
from services.lending_operations_service import (
    calculate_cdas_affordability,
    evaluate_credit_decision,
    generate_regulatory_payload,
    make_reference,
    money,
    reconcile_cdas_batch,
    run_reconciliation,
    start_workflow_instance,
    advance_workflow_instance,
    sync_overdue_collection_cases,
)

router = APIRouter(prefix="/lending-operations", tags=["Lending Operations"])

RISK_COMPLIANCE_ROLES = COMPANY_MANAGEMENT_ROLES | {
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
}
CDAS_ROLES = COMPANY_MANAGEMENT_ROLES | LENDING_ROLES | FINANCE_ROLES | COLLECTIONS_ROLES | RISK_COMPLIANCE_ROLES
RECONCILIATION_ROLES = COMPANY_MANAGEMENT_ROLES | FINANCE_ROLES | {
    UserRole.AUDITOR,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.RISK_MANAGER,
}
CREDIT_ROLES = COMPANY_MANAGEMENT_ROLES | LENDING_ROLES | RISK_COMPLIANCE_ROLES
COLLECTION_ROLES = COMPANY_MANAGEMENT_ROLES | COLLECTIONS_ROLES | {UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER}
REGULATORY_ROLES = COMPANY_MANAGEMENT_ROLES | FINANCE_ROLES | RISK_COMPLIANCE_ROLES
DECISION_ROLES = COMPANY_MANAGEMENT_ROLES | LENDING_ROLES | RISK_COMPLIANCE_ROLES


def require_company(context: TenantContext) -> UUID:
    if context.is_platform_admin:
        raise HTTPException(status_code=400, detail="Select a company-scoped role for this module")
    if not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company membership is required")
    return context.company_id


def require_roles(context: TenantContext, roles: set[UserRole]) -> UUID:
    company_id = require_company(context)
    if context.role not in roles:
        raise HTTPException(status_code=403, detail="The active role is not assigned to this operation")
    return company_id


def apply_branch_scope(query, model, context: TenantContext):
    if context.branch_id and hasattr(model, "branch_id"):
        return query.filter(model.branch_id == context.branch_id)
    return query


def borrower_or_404(db: Session, borrower_id: UUID, company_id: UUID) -> Borrower:
    borrower = db.get(Borrower, borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    # Company borrower relationship can be indirect through applications/loans; avoid cross-company creation.
    linked = db.query(ClientCompanyLoan.id).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.borrower_id == borrower_id,
    ).first()
    if not linked:
        from database.models.company_client import CompanyBorrowerAccount
        linked = db.query(CompanyBorrowerAccount.id).filter(
            CompanyBorrowerAccount.company_id == company_id,
            CompanyBorrowerAccount.borrower_id == borrower_id,
        ).first()
    if not linked:
        raise HTTPException(status_code=403, detail="Borrower is not linked to the selected company")
    return borrower


def loan_or_404(db: Session, loan_id: UUID, company_id: UUID, branch_id: UUID | None = None) -> ClientCompanyLoan:
    loan = db.get(ClientCompanyLoan, loan_id)
    if not loan or loan.company_id != company_id:
        raise HTTPException(status_code=404, detail="Loan not found")
    if branch_id and loan.branch_id != branch_id:
        raise HTTPException(status_code=403, detail="Loan is outside the active branch")
    return loan


@router.get("/dashboard", response_model=LendingOperationsDashboard)
def dashboard(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_company(context)
    def count(model, *criteria):
        query = db.query(func.count(model.id)).filter(model.company_id == company_id, *criteria)
        query = apply_branch_scope(query, model, context)
        return int(query.scalar() or 0)

    open_exceptions = count(ReconciliationException, ReconciliationException.status.in_(["open", "investigating"]))
    open_compliance = count(ComplianceCase, ComplianceCase.status.notin_(["cleared", "closed"]))
    open_collections = count(CollectionCase, CollectionCase.status.notin_(["closed", "recovered"]))
    active_mandates = count(CDASDeductionMandate, CDASDeductionMandate.status.in_(["accepted", "active", "rescheduled"]))
    pending_bureau = count(CreditBureauEnquiry, CreditBureauEnquiry.status.in_(["requested", "processing"]))
    pending_regulatory = count(RegulatorySubmission, RegulatorySubmission.status.notin_(["submitted", "rejected"]))
    active_workflows = count(WorkflowInstance, WorkflowInstance.status == "active")
    critical_cases = count(ComplianceCase, ComplianceCase.severity == "critical", ComplianceCase.status.notin_(["cleared", "closed"]))
    return LendingOperationsDashboard(
        metrics=[
            DashboardMetric(key="active_cdas_mandates", label="Active CDAS mandates", value=active_mandates, tone="positive"),
            DashboardMetric(key="reconciliation_exceptions", label="Open reconciliation exceptions", value=open_exceptions, tone="danger" if open_exceptions else "positive"),
            DashboardMetric(key="compliance_cases", label="Open compliance cases", value=open_compliance, tone="warning" if open_compliance else "positive"),
            DashboardMetric(key="collection_cases", label="Open collection cases", value=open_collections, tone="warning" if open_collections else "positive"),
            DashboardMetric(key="credit_enquiries", label="Pending credit enquiries", value=pending_bureau),
            DashboardMetric(key="regulatory_returns", label="Regulatory returns in progress", value=pending_regulatory),
            DashboardMetric(key="active_workflows", label="Active approval workflows", value=active_workflows),
        ],
        alerts=[
            {"severity": "critical", "message": f"{critical_cases} critical compliance case(s) require attention."}
        ] if critical_cases else [],
        module_counts={
            "cdas": active_mandates,
            "reconciliation": open_exceptions,
            "credit_bureau": pending_bureau,
            "compliance": open_compliance,
            "collections": open_collections,
            "regulatory": pending_regulatory,
            "decisions_workflows": active_workflows,
        },
    )


# CDAS payroll deductions
@router.get("/cdas/payroll-profiles", response_model=list[CDASPayrollProfileRead])
def list_payroll_profiles(
    borrower_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    query = db.query(CDASPayrollProfile).filter(CDASPayrollProfile.company_id == company_id)
    query = apply_branch_scope(query, CDASPayrollProfile, context)
    if borrower_id:
        query = query.filter(CDASPayrollProfile.borrower_id == borrower_id)
    return query.order_by(CDASPayrollProfile.updated_at.desc()).all()


@router.post("/cdas/payroll-profiles", response_model=CDASPayrollProfileRead, status_code=201)
def upsert_payroll_profile(
    payload: CDASPayrollProfileCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    borrower_or_404(db, payload.borrower_id, company_id)
    row = db.query(CDASPayrollProfile).filter(
        CDASPayrollProfile.company_id == company_id,
        CDASPayrollProfile.borrower_id == payload.borrower_id,
    ).first()
    values = payload.model_dump()
    if context.branch_id:
        values["branch_id"] = context.branch_id
    if row:
        for field, value in values.items():
            setattr(row, field, value)
    else:
        row = CDASPayrollProfile(company_id=company_id, **values)
        db.add(row)
    if payload.verified:
        row.verified_at = datetime.now(timezone.utc)
        row.verified_by_user_id = context.user.id
    db.commit()
    db.refresh(row)
    return row


@router.post("/cdas/affordability", response_model=CDASAffordabilityRead)
def cdas_affordability(
    payload: CDASAffordabilityRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    profile = None
    if payload.payroll_profile_id:
        profile = db.get(CDASPayrollProfile, payload.payroll_profile_id)
        if not profile or profile.company_id != company_id:
            raise HTTPException(status_code=404, detail="CDAS payroll profile not found")
    return calculate_cdas_affordability(
        net_salary=payload.net_salary if payload.net_salary is not None else Decimal(profile.net_salary if profile else 0),
        existing_deductions=payload.existing_deductions if payload.existing_deductions is not None else Decimal(profile.existing_deductions if profile else 0),
        proposed_deduction=payload.proposed_deduction,
        maximum_deduction_percent=payload.maximum_deduction_percent if payload.maximum_deduction_percent is not None else Decimal(profile.maximum_deduction_percent if profile else 40),
        minimum_take_home=payload.minimum_take_home,
    )


@router.get("/cdas/mandates", response_model=list[CDASMandateRead])
def list_cdas_mandates(
    status: str | None = None,
    borrower_id: UUID | None = None,
    loan_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    query = db.query(CDASDeductionMandate).filter(CDASDeductionMandate.company_id == company_id)
    query = apply_branch_scope(query, CDASDeductionMandate, context)
    if status:
        query = query.filter(CDASDeductionMandate.status == status)
    if borrower_id:
        query = query.filter(CDASDeductionMandate.borrower_id == borrower_id)
    if loan_id:
        query = query.filter(CDASDeductionMandate.loan_id == loan_id)
    return query.order_by(CDASDeductionMandate.created_at.desc()).all()


@router.post("/cdas/mandates", response_model=CDASMandateRead, status_code=201)
def create_cdas_mandate(
    payload: CDASMandateCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    loan = loan_or_404(db, payload.loan_id, company_id, context.branch_id)
    if loan.borrower_id != payload.borrower_id:
        raise HTTPException(status_code=422, detail="The selected loan does not belong to the borrower")
    profile = db.get(CDASPayrollProfile, payload.payroll_profile_id)
    if not profile or profile.company_id != company_id or profile.borrower_id != payload.borrower_id:
        raise HTTPException(status_code=422, detail="The selected CDAS payroll profile is not valid for the borrower")
    affordability = calculate_cdas_affordability(
        net_salary=Decimal(profile.net_salary),
        existing_deductions=Decimal(profile.existing_deductions),
        proposed_deduction=payload.monthly_deduction,
        maximum_deduction_percent=Decimal(profile.maximum_deduction_percent),
    )
    if not affordability["affordable"]:
        raise HTTPException(status_code=422, detail={"message": "CDAS deduction is not affordable", "reasons": affordability["reasons"]})
    if not payload.borrower_consent:
        raise HTTPException(status_code=422, detail="Borrower consent is required before creating a CDAS mandate")
    row = CDASDeductionMandate(
        company_id=company_id,
        branch_id=context.branch_id or loan.branch_id,
        borrower_id=payload.borrower_id,
        loan_id=payload.loan_id,
        payroll_profile_id=payload.payroll_profile_id,
        mandate_number=make_reference("CDAS-MND"),
        employee_number=profile.employee_number,
        monthly_deduction=money(payload.monthly_deduction),
        start_date=payload.start_date,
        end_date=payload.end_date,
        expected_installments=payload.expected_installments,
        total_expected=money(payload.monthly_deduction * payload.expected_installments),
        borrower_consent=True,
        consent_file_id=payload.consent_file_id,
        external_reference=payload.external_reference,
        created_by_user_id=context.user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/cdas/mandates/{mandate_id}/status", response_model=CDASMandateRead)
def update_cdas_mandate_status(
    mandate_id: UUID,
    payload: CDASMandateStatusUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    row = db.get(CDASDeductionMandate, mandate_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="CDAS mandate not found")
    if context.branch_id and row.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="Mandate is outside the active branch")
    row.status = payload.status
    row.external_reference = payload.external_reference or row.external_reference
    row.rejection_reason = payload.rejection_reason
    now = datetime.now(timezone.utc)
    if payload.status in {"submitted", "pending_verification"}:
        row.submitted_at = row.submitted_at or now
    if payload.status in {"accepted", "active"}:
        row.activated_at = row.activated_at or now
    if payload.status == "completed":
        row.completed_at = now
    db.commit()
    db.refresh(row)
    return row


@router.get("/cdas/remittance-batches", response_model=list[CDASRemittanceBatchRead])
def list_cdas_batches(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    return db.query(CDASRemittanceBatch).filter(CDASRemittanceBatch.company_id == company_id).order_by(CDASRemittanceBatch.payroll_month.desc()).all()


@router.post("/cdas/remittance-batches", response_model=CDASRemittanceBatchRead, status_code=201)
def create_cdas_batch(
    payload: CDASRemittanceBatchCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    row = CDASRemittanceBatch(company_id=company_id, imported_by_user_id=context.user.id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/cdas/remittance-batches/{batch_id}/lines", response_model=list[CDASRemittanceLineRead])
def list_cdas_batch_lines(
    batch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    batch = db.get(CDASRemittanceBatch, batch_id)
    if not batch or batch.company_id != company_id:
        raise HTTPException(status_code=404, detail="CDAS remittance batch not found")
    return db.query(CDASRemittanceLine).filter(CDASRemittanceLine.batch_id == batch_id).order_by(CDASRemittanceLine.created_at.asc()).all()


@router.post("/cdas/remittance-batches/{batch_id}/lines", response_model=CDASRemittanceLineRead, status_code=201)
def create_cdas_batch_line(
    batch_id: UUID,
    payload: CDASRemittanceLineCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CDAS_ROLES)
    batch = db.get(CDASRemittanceBatch, batch_id)
    if not batch or batch.company_id != company_id:
        raise HTTPException(status_code=404, detail="CDAS remittance batch not found")
    row = CDASRemittanceLine(
        batch_id=batch_id,
        company_id=company_id,
        employee_number=payload.employee_number,
        line_reference=payload.line_reference,
        deducted_amount=money(payload.deducted_amount),
        expected_amount=money(payload.expected_amount or 0),
        raw_payload=payload.raw_payload,
    )
    db.add(row)
    batch.line_count = int(batch.line_count or 0) + 1
    batch.received_amount = money(Decimal(batch.received_amount or 0) + payload.deducted_amount)
    db.commit()
    db.refresh(row)
    return row


@router.post("/cdas/remittance-batches/{batch_id}/reconcile", response_model=ReconciliationRunRead)
def reconcile_cdas_remittance(
    batch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RECONCILIATION_ROLES | CDAS_ROLES)
    batch = db.get(CDASRemittanceBatch, batch_id)
    if not batch or batch.company_id != company_id:
        raise HTTPException(status_code=404, detail="CDAS remittance batch not found")
    return reconcile_cdas_batch(db, batch, context.user.id)


# Automated reconciliation
@router.get("/reconciliation/runs", response_model=list[ReconciliationRunRead])
def list_reconciliation_runs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RECONCILIATION_ROLES)
    query = db.query(ReconciliationRun).filter(ReconciliationRun.company_id == company_id)
    query = apply_branch_scope(query, ReconciliationRun, context)
    return query.order_by(ReconciliationRun.created_at.desc()).limit(limit).all()


@router.post("/reconciliation/run", response_model=ReconciliationRunRead, status_code=201)
def create_reconciliation_run(
    payload: ReconciliationRunCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RECONCILIATION_ROLES)
    branch_id = context.branch_id or payload.branch_id
    if context.branch_id and payload.branch_id and payload.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="Cannot reconcile another branch")
    return run_reconciliation(
        db,
        company_id=company_id,
        branch_id=branch_id,
        run_type=payload.run_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        user_id=context.user.id,
    )


@router.get("/reconciliation/exceptions", response_model=list[ReconciliationExceptionRead])
def list_reconciliation_exceptions(
    status: str | None = None,
    severity: str | None = None,
    run_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RECONCILIATION_ROLES)
    query = db.query(ReconciliationException).filter(ReconciliationException.company_id == company_id)
    query = apply_branch_scope(query, ReconciliationException, context)
    if status:
        query = query.filter(ReconciliationException.status == status)
    if severity:
        query = query.filter(ReconciliationException.severity == severity)
    if run_id:
        query = query.filter(ReconciliationException.run_id == run_id)
    return query.order_by(ReconciliationException.created_at.desc()).limit(500).all()


@router.patch("/reconciliation/exceptions/{exception_id}", response_model=ReconciliationExceptionRead)
def resolve_reconciliation_exception(
    exception_id: UUID,
    payload: ReconciliationExceptionUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RECONCILIATION_ROLES)
    row = db.get(ReconciliationException, exception_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found")
    if context.branch_id and row.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="Exception is outside the active branch")
    row.status = payload.status
    row.resolution_notes = payload.resolution_notes
    if payload.status in {"resolved", "accepted_variance", "dismissed"}:
        row.resolved_by_user_id = context.user.id
        row.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


# Credit bureau
@router.get("/credit-bureau/enquiries", response_model=list[CreditBureauEnquiryRead])
def list_credit_enquiries(
    borrower_id: UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CREDIT_ROLES)
    query = db.query(CreditBureauEnquiry).filter(CreditBureauEnquiry.company_id == company_id)
    query = apply_branch_scope(query, CreditBureauEnquiry, context)
    if borrower_id:
        query = query.filter(CreditBureauEnquiry.borrower_id == borrower_id)
    if status:
        query = query.filter(CreditBureauEnquiry.status == status)
    return query.order_by(CreditBureauEnquiry.requested_at.desc()).limit(500).all()


@router.post("/credit-bureau/enquiries", response_model=CreditBureauEnquiryRead, status_code=201)
def create_credit_enquiry(
    payload: CreditBureauEnquiryCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CREDIT_ROLES)
    borrower = borrower_or_404(db, payload.borrower_id, company_id)
    if not payload.consent_confirmed or not borrower.consent_to_credit_checks:
        raise HTTPException(status_code=422, detail="Borrower credit-check consent must be recorded before an enquiry")
    row = CreditBureauEnquiry(
        company_id=company_id,
        branch_id=context.branch_id,
        borrower_id=payload.borrower_id,
        application_id=payload.application_id,
        provider=payload.provider,
        enquiry_reference=make_reference("CBQ"),
        purpose=payload.purpose,
        consent_confirmed=True,
        enquiry_data=payload.enquiry_data,
        requested_by_user_id=context.user.id,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/credit-bureau/enquiries/{enquiry_id}/complete", response_model=CreditBureauEnquiryRead)
def complete_credit_enquiry(
    enquiry_id: UUID,
    payload: CreditBureauEnquiryComplete,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, CREDIT_ROLES)
    row = db.get(CreditBureauEnquiry, enquiry_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Credit-bureau enquiry not found")
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    row.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


# KYC, AML and fraud
@router.get("/compliance/cases", response_model=list[ComplianceCaseRead])
def list_compliance_cases(
    case_type: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    borrower_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RISK_COMPLIANCE_ROLES | LENDING_ROLES)
    query = db.query(ComplianceCase).filter(ComplianceCase.company_id == company_id)
    query = apply_branch_scope(query, ComplianceCase, context)
    if case_type:
        query = query.filter(ComplianceCase.case_type == case_type)
    if status:
        query = query.filter(ComplianceCase.status == status)
    if severity:
        query = query.filter(ComplianceCase.severity == severity)
    if borrower_id:
        query = query.filter(ComplianceCase.borrower_id == borrower_id)
    return query.order_by(ComplianceCase.created_at.desc()).limit(500).all()


@router.post("/compliance/cases", response_model=ComplianceCaseRead, status_code=201)
def create_compliance_case(
    payload: ComplianceCaseCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RISK_COMPLIANCE_ROLES | LENDING_ROLES)
    if payload.borrower_id:
        borrower_or_404(db, payload.borrower_id, company_id)
    if payload.loan_id:
        loan_or_404(db, payload.loan_id, company_id, context.branch_id)
    row = ComplianceCase(
        company_id=company_id,
        branch_id=context.branch_id,
        case_reference=make_reference("CMP"),
        opened_by_user_id=context.user.id,
        **payload.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/compliance/cases/{case_id}", response_model=ComplianceCaseRead)
def update_compliance_case(
    case_id: UUID,
    payload: ComplianceCaseUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RISK_COMPLIANCE_ROLES)
    row = db.get(ComplianceCase, case_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Compliance case not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    if row.status in {"cleared", "closed"}:
        row.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@router.get("/compliance/cases/{case_id}/screenings", response_model=list[ComplianceScreeningRead])
def list_compliance_screenings(
    case_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RISK_COMPLIANCE_ROLES | LENDING_ROLES)
    case = db.get(ComplianceCase, case_id)
    if not case or case.company_id != company_id:
        raise HTTPException(status_code=404, detail="Compliance case not found")
    return db.query(ComplianceScreening).filter(ComplianceScreening.case_id == case_id).order_by(ComplianceScreening.screened_at.desc()).all()


@router.post("/compliance/cases/{case_id}/screenings", response_model=ComplianceScreeningRead, status_code=201)
def create_compliance_screening(
    case_id: UUID,
    payload: ComplianceScreeningCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, RISK_COMPLIANCE_ROLES)
    case = db.get(ComplianceCase, case_id)
    if not case or case.company_id != company_id:
        raise HTTPException(status_code=404, detail="Compliance case not found")
    row = ComplianceScreening(
        case_id=case_id,
        company_id=company_id,
        screened_by_user_id=context.user.id,
        screened_at=datetime.now(timezone.utc),
        **payload.model_dump(),
    )
    db.add(row)
    if payload.matched:
        case.status = "escalated"
        case.risk_score = max(Decimal(case.risk_score or 0), payload.match_score)
        flags = list(case.flags or [])
        if payload.screening_type not in flags:
            flags.append(payload.screening_type)
        case.flags = flags
    db.commit()
    db.refresh(row)
    return row


# Collections and recoveries
@router.get("/collections/cases", response_model=list[CollectionCaseRead])
def list_collection_cases(
    status: str | None = None,
    stage: str | None = None,
    priority: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, COLLECTION_ROLES)
    query = db.query(CollectionCase).filter(CollectionCase.company_id == company_id)
    query = apply_branch_scope(query, CollectionCase, context)
    if status:
        query = query.filter(CollectionCase.status == status)
    if stage:
        query = query.filter(CollectionCase.stage == stage)
    if priority:
        query = query.filter(CollectionCase.priority == priority)
    return query.order_by(CollectionCase.days_past_due.desc(), CollectionCase.created_at.desc()).limit(500).all()


@router.post("/collections/sync-overdue")
def sync_overdue_cases(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, COLLECTION_ROLES)
    created = sync_overdue_collection_cases(db, company_id)
    return {"created": created, "message": f"Created {created} new collection case(s)."}


@router.post("/collections/cases", response_model=CollectionCaseRead, status_code=201)
def create_collection_case(
    payload: CollectionCaseCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, COLLECTION_ROLES)
    loan = loan_or_404(db, payload.loan_id, company_id, context.branch_id)
    existing = db.query(CollectionCase).filter(CollectionCase.company_id == company_id, CollectionCase.loan_id == loan.id).first()
    if existing:
        return existing
    row = CollectionCase(
        company_id=company_id,
        branch_id=loan.branch_id,
        borrower_id=loan.borrower_id,
        loan_id=loan.id,
        case_reference=make_reference("COL"),
        outstanding_balance=money(loan.balance),
        priority=payload.priority,
        assigned_to_user_id=payload.assigned_to_user_id,
        next_action_at=payload.next_action_at,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/collections/cases/{case_id}", response_model=CollectionCaseRead)
def update_collection_case(
    case_id: UUID,
    payload: CollectionCaseUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, COLLECTION_ROLES)
    row = db.get(CollectionCase, case_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Collection case not found")
    if context.branch_id and row.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="Collection case is outside the active branch")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    if row.status == "legal" and not row.legal_handover_at:
        row.legal_handover_at = datetime.now(timezone.utc)
    if row.status == "written_off" and not row.write_off_at:
        row.write_off_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@router.get("/collections/cases/{case_id}/activities", response_model=list[CollectionActivityRead])
def list_collection_activities(
    case_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, COLLECTION_ROLES)
    case = db.get(CollectionCase, case_id)
    if not case or case.company_id != company_id:
        raise HTTPException(status_code=404, detail="Collection case not found")
    return db.query(CollectionActivity).filter(CollectionActivity.case_id == case_id).order_by(CollectionActivity.performed_at.desc()).all()


@router.post("/collections/cases/{case_id}/activities", response_model=CollectionActivityRead, status_code=201)
def create_collection_activity(
    case_id: UUID,
    payload: CollectionActivityCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, COLLECTION_ROLES)
    case = db.get(CollectionCase, case_id)
    if not case or case.company_id != company_id:
        raise HTTPException(status_code=404, detail="Collection case not found")
    row = CollectionActivity(
        case_id=case_id,
        company_id=company_id,
        performed_by_user_id=context.user.id,
        performed_at=datetime.now(timezone.utc),
        **payload.model_dump(),
    )
    db.add(row)
    case.last_contact_at = row.performed_at
    case.next_action_at = payload.follow_up_at
    if payload.activity_type == "promise":
        case.status = "promise_to_pay"
        case.promise_amount = payload.amount
        case.promise_date = payload.follow_up_at.date() if payload.follow_up_at else None
        case.promise_status = "open"
    if payload.activity_type == "payment" and payload.amount:
        case.recovered_amount = money(Decimal(case.recovered_amount or 0) + payload.amount)
    db.commit()
    db.refresh(row)
    return row


# Regulatory reporting
@router.get("/regulatory/submissions", response_model=list[RegulatorySubmissionRead])
def list_regulatory_submissions(
    report_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, REGULATORY_ROLES)
    query = db.query(RegulatorySubmission).filter(RegulatorySubmission.company_id == company_id)
    if report_type:
        query = query.filter(RegulatorySubmission.report_type == report_type)
    if status:
        query = query.filter(RegulatorySubmission.status == status)
    return query.order_by(RegulatorySubmission.period_end.desc(), RegulatorySubmission.created_at.desc()).all()


@router.post("/regulatory/submissions", response_model=RegulatorySubmissionRead, status_code=201)
def create_regulatory_submission(
    payload: RegulatorySubmissionCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, REGULATORY_ROLES)
    row = RegulatorySubmission(
        company_id=company_id,
        report_type=payload.report_type,
        submission_reference=make_reference("REG"),
        period_start=payload.period_start,
        period_end=payload.period_end,
        prepared_by_user_id=context.user.id,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/regulatory/submissions/{submission_id}/generate", response_model=RegulatorySubmissionRead)
def generate_regulatory_submission(
    submission_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, REGULATORY_ROLES)
    row = db.get(RegulatorySubmission, submission_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Regulatory submission not found")
    row.payload = generate_regulatory_payload(db, row)
    row.validation_errors = []
    row.status = "generated"
    row.generated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/regulatory/submissions/{submission_id}", response_model=RegulatorySubmissionRead)
def update_regulatory_submission(
    submission_id: UUID,
    payload: RegulatorySubmissionUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, REGULATORY_ROLES)
    row = db.get(RegulatorySubmission, submission_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Regulatory submission not found")
    row.status = payload.status
    row.regulator_reference = payload.regulator_reference or row.regulator_reference
    row.notes = payload.notes if payload.notes is not None else row.notes
    now = datetime.now(timezone.utc)
    if payload.status == "approved":
        row.approved_by_user_id = context.user.id
        row.approved_at = now
    if payload.status == "submitted":
        row.submitted_by_user_id = context.user.id
        row.submitted_at = now
    db.commit()
    db.refresh(row)
    return row


# Decision engine and workflows
@router.get("/decisions/policies", response_model=list[CreditDecisionPolicyRead])
def list_decision_policies(
    status: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, DECISION_ROLES)
    query = db.query(CreditDecisionPolicy).filter(CreditDecisionPolicy.company_id == company_id)
    if status:
        query = query.filter(CreditDecisionPolicy.status == status)
    return query.order_by(CreditDecisionPolicy.name, CreditDecisionPolicy.version.desc()).all()


@router.post("/decisions/policies", response_model=CreditDecisionPolicyRead, status_code=201)
def create_decision_policy(
    payload: CreditDecisionPolicyCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER})
    if payload.status == "active":
        db.query(CreditDecisionPolicy).filter(
            CreditDecisionPolicy.company_id == company_id,
            CreditDecisionPolicy.name == payload.name,
            CreditDecisionPolicy.status == "active",
        ).update({CreditDecisionPolicy.status: "retired"}, synchronize_session=False)
    row = CreditDecisionPolicy(company_id=company_id, configured_by_user_id=context.user.id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/decisions", response_model=list[CreditDecisionRead])
def list_credit_decisions(
    borrower_id: UUID | None = None,
    application_id: UUID | None = None,
    decision: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, DECISION_ROLES)
    query = db.query(CreditDecision).filter(CreditDecision.company_id == company_id)
    if borrower_id:
        query = query.filter(CreditDecision.borrower_id == borrower_id)
    if application_id:
        query = query.filter(CreditDecision.application_id == application_id)
    if decision:
        query = query.filter(CreditDecision.decision == decision)
    return query.order_by(CreditDecision.created_at.desc()).limit(500).all()


@router.post("/decisions/evaluate", response_model=CreditDecisionRead, status_code=201)
def evaluate_decision(
    payload: CreditDecisionEvaluateRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, DECISION_ROLES)
    borrower_or_404(db, payload.borrower_id, company_id)
    policy = db.get(CreditDecisionPolicy, payload.policy_id)
    if not policy or policy.company_id != company_id:
        raise HTTPException(status_code=404, detail="Credit decision policy not found")
    if policy.status != "active":
        raise HTTPException(status_code=422, detail="Only an active policy can evaluate an application")
    return evaluate_credit_decision(
        db,
        company_id=company_id,
        borrower_id=payload.borrower_id,
        application_id=payload.application_id,
        policy=policy,
        requested_amount=payload.requested_amount,
        proposed_installment=payload.proposed_installment,
        additional_inputs=payload.additional_inputs,
    )


@router.get("/workflows/templates", response_model=list[WorkflowTemplateRead])
def list_workflow_templates(
    workflow_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, DECISION_ROLES)
    query = db.query(WorkflowTemplate).filter(WorkflowTemplate.company_id == company_id)
    if workflow_type:
        query = query.filter(WorkflowTemplate.workflow_type == workflow_type)
    if status:
        query = query.filter(WorkflowTemplate.status == status)
    return query.order_by(WorkflowTemplate.name, WorkflowTemplate.version.desc()).all()


@router.post("/workflows/templates", response_model=WorkflowTemplateRead, status_code=201)
def create_workflow_template(
    payload: WorkflowTemplateCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER})
    if not payload.steps:
        raise HTTPException(status_code=422, detail="A workflow must contain at least one step")
    for index, step in enumerate(payload.steps):
        if not step.get("key") and not step.get("name"):
            raise HTTPException(status_code=422, detail=f"Workflow step {index + 1} requires a key or name")
        if not step.get("role"):
            raise HTTPException(status_code=422, detail=f"Workflow step {index + 1} requires a role")
    row = WorkflowTemplate(company_id=company_id, configured_by_user_id=context.user.id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/workflows/instances", response_model=list[WorkflowInstanceRead])
def list_workflow_instances(
    status: str | None = None,
    application_id: UUID | None = None,
    loan_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, DECISION_ROLES)
    query = db.query(WorkflowInstance).filter(WorkflowInstance.company_id == company_id)
    if status:
        query = query.filter(WorkflowInstance.status == status)
    if application_id:
        query = query.filter(WorkflowInstance.application_id == application_id)
    if loan_id:
        query = query.filter(WorkflowInstance.loan_id == loan_id)
    return query.order_by(WorkflowInstance.started_at.desc()).limit(500).all()


@router.post("/workflows/instances", response_model=WorkflowInstanceRead, status_code=201)
def create_workflow_instance(
    payload: WorkflowInstanceCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, DECISION_ROLES)
    template = db.get(WorkflowTemplate, payload.template_id)
    if not template or template.company_id != company_id:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    if template.status != "active":
        raise HTTPException(status_code=422, detail="Only active workflow templates can be started")
    if payload.loan_id:
        loan_or_404(db, payload.loan_id, company_id, context.branch_id)
    if payload.borrower_id:
        borrower_or_404(db, payload.borrower_id, company_id)
    return start_workflow_instance(
        db,
        company_id=company_id,
        template=template,
        application_id=payload.application_id,
        loan_id=payload.loan_id,
        borrower_id=payload.borrower_id,
        assigned_user_id=payload.assigned_user_id,
        context_snapshot=payload.context_snapshot,
        due_at=payload.due_at,
    )


@router.post("/workflows/instances/{instance_id}/advance", response_model=WorkflowInstanceRead)
def advance_workflow(
    instance_id: UUID,
    payload: WorkflowAdvanceRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = require_roles(context, DECISION_ROLES)
    instance = db.get(WorkflowInstance, instance_id)
    if not instance or instance.company_id != company_id:
        raise HTTPException(status_code=404, detail="Workflow instance not found")
    if instance.status != "active":
        raise HTTPException(status_code=422, detail="Workflow instance is not active")
    if instance.assigned_role and context.role.value != instance.assigned_role and context.role not in COMPANY_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="The active role is not assigned to the current workflow step")
    template = db.get(WorkflowTemplate, instance.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return advance_workflow_instance(
        db,
        instance=instance,
        template=template,
        action=payload.action,
        notes=payload.notes,
        user_id=context.user.id,
        assigned_user_id=payload.assigned_user_id,
    )
