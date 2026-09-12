from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    COMPANY_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_current_active_user,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.accounting import JournalEntry
from database.models.audit_log import AuditLog
from database.models.company_client import CompanyBorrowerAccount
from database.models.client_loan_company import ClientCompanyLoan
from database.models.borrower import Borrower
from database.models.company import LoanCompany
from database.models.enums import UserRole
from database.models.governance_control import (
    AccountingPeriod,
    ApprovalRequest,
    BankStatementLine,
    ComplaintCase,
    DataRightsRequest,
    LoanCollateral,
    LoanGuarantor,
    PaymentAdjustment,
    WebhookOutboxEvent,
)
from database.models.payment import PaymentTransaction
from database.models.user import User
from database.schemas.governance_control import (
    AccountingPeriodAction,
    AccountingPeriodCreate,
    BankStatementLineCreate,
    BankStatementMatch,
    CollateralCreate,
    ComplaintCreate,
    ComplaintUpdate,
    DataRightsComplete,
    DataRightsCreate,
    DecisionRequest,
    GuarantorCreate,
    GuarantorVerify,
    PaymentAdjustmentCreate,
)
from database.session import get_db
from services.governance_control_service import (
    approve_payment_adjustment,
    bank_line_fingerprint,
    match_bank_line,
    new_case_reference,
    reject_payment_adjustment,
    request_payment_adjustment,
)
from services.webhook_outbox_service import enqueue_webhook, replay_outbox_event
from core.audit_integrity import audit_hash, verify_chain


router = APIRouter(prefix="/controls", tags=["Financial and Governance Controls"])
FINANCIAL_CONTROL_ROLES = FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES | {UserRole.AUDITOR}
CUSTOMER_CONTROL_ROLES = COMPANY_MANAGEMENT_ROLES | {UserRole.CUSTOMER_SUPPORT, UserRole.COMPLIANCE_OFFICER, UserRole.DATA_PROTECTION_OFFICER}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _branch(context: TenantContext):
    return context.branch_id if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES else None


def _loan(db: Session, context: TenantContext, loan_id: UUID) -> ClientCompanyLoan:
    query = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == context.company_id,
    )
    if _branch(context):
        query = query.filter(ClientCompanyLoan.branch_id == _branch(context))
    loan = query.first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan was not found in the active company/branch")
    return loan


@router.get("/summary")
def control_summary(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_ROLES)
    company_id = context.company_id
    return {
        "pending_approvals": db.query(ApprovalRequest).filter(ApprovalRequest.company_id == company_id, ApprovalRequest.status == "pending").count(),
        "payment_adjustments_attention": db.query(PaymentAdjustment).filter(PaymentAdjustment.company_id == company_id, PaymentAdjustment.status.in_(["pending_approval", "processing", "under_investigation"])).count(),
        "webhook_dead_letters": db.query(WebhookOutboxEvent).filter(WebhookOutboxEvent.company_id == company_id, WebhookOutboxEvent.status == "dead_letter").count(),
        "unmatched_bank_lines": db.query(BankStatementLine).filter(BankStatementLine.company_id == company_id, BankStatementLine.status == "unmatched").count(),
        "open_complaints": db.query(ComplaintCase).filter(ComplaintCase.company_id == company_id, ComplaintCase.status.notin_(["resolved", "closed"])).count(),
    }


@router.get("/audit-integrity")
def audit_integrity(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    if not context.is_platform_admin:
        require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.AUDITOR, UserRole.INFORMATION_SECURITY_OFFICER})
    query = db.query(AuditLog).filter(AuditLog.event_hash.isnot(None))
    if context.is_platform_admin:
        items = query.order_by(AuditLog.sealed_at.asc(), AuditLog.id.asc()).all()
        valid, broken_event_id = verify_chain(items)
    else:
        items = query.filter(AuditLog.company_id == context.company_id).order_by(AuditLog.sealed_at.asc()).all()
        broken = next((item for item in items if item.event_hash != audit_hash(item, item.previous_hash)), None)
        valid, broken_event_id = broken is None, str(broken.id) if broken else None
    return {"valid": valid, "sealed_events": len(items), "broken_event_id": broken_event_id}


@router.get("/payment-adjustments")
def list_payment_adjustments(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, FINANCIAL_CONTROL_ROLES)
    return db.query(PaymentAdjustment).filter(PaymentAdjustment.company_id == context.company_id).order_by(PaymentAdjustment.created_at.desc()).limit(500).all()


@router.post("/payment-adjustments", status_code=201)
def create_payment_adjustment(payload: PaymentAdjustmentCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, FINANCIAL_CONTROL_ROLES)
    payment = db.query(PaymentTransaction).filter(PaymentTransaction.id == payload.payment_id, PaymentTransaction.company_id == context.company_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    item = request_payment_adjustment(
        db,
        company_id=context.company_id,
        branch_id=_branch(context),
        payment=payment,
        adjustment_type=payload.adjustment_type,
        amount=payload.amount,
        reason=payload.reason,
        idempotency_key=payload.idempotency_key,
        requested_by_user_id=context.user.id,
    )
    db.commit()
    db.refresh(item)
    return item


@router.post("/payment-adjustments/{adjustment_id}/approve")
def approve_adjustment(adjustment_id: UUID, payload: DecisionRequest, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, FINANCIAL_CONTROL_ROLES)
    item = db.query(PaymentAdjustment).filter(PaymentAdjustment.id == adjustment_id, PaymentAdjustment.company_id == context.company_id).with_for_update().first()
    if not item:
        raise HTTPException(status_code=404, detail="Payment adjustment not found")
    approve_payment_adjustment(db, adjustment=item, checker_user_id=context.user.id, reason=payload.reason)
    db.commit()
    db.refresh(item)
    return item


@router.post("/payment-adjustments/{adjustment_id}/reject")
def reject_adjustment(adjustment_id: UUID, payload: DecisionRequest, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, FINANCIAL_CONTROL_ROLES)
    item = db.query(PaymentAdjustment).filter(PaymentAdjustment.id == adjustment_id, PaymentAdjustment.company_id == context.company_id).with_for_update().first()
    if not item:
        raise HTTPException(status_code=404, detail="Payment adjustment not found")
    reject_payment_adjustment(db, adjustment=item, checker_user_id=context.user.id, reason=payload.reason)
    db.commit()
    db.refresh(item)
    return item


@router.get("/accounting-periods")
def list_accounting_periods(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, FINANCIAL_CONTROL_ROLES)
    return db.query(AccountingPeriod).filter(AccountingPeriod.company_id == context.company_id).order_by(AccountingPeriod.period_start.desc()).all()


@router.post("/accounting-periods", status_code=201)
def create_accounting_period(payload: AccountingPeriodCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | FINANCE_ROLES)
    if payload.period_end < payload.period_start:
        raise HTTPException(status_code=422, detail="Period end must be on or after period start")
    overlap = db.query(AccountingPeriod.id).filter(
        AccountingPeriod.company_id == context.company_id,
        AccountingPeriod.period_start <= payload.period_end,
        AccountingPeriod.period_end >= payload.period_start,
    ).first()
    if overlap:
        raise HTTPException(status_code=409, detail="Accounting periods cannot overlap")
    item = AccountingPeriod(
        scope_key=f"company:{context.company_id}",
        company_id=context.company_id,
        branch_id=_branch(context),
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/accounting-periods/{period_id}/lock")
def lock_accounting_period(period_id: UUID, payload: AccountingPeriodAction, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | FINANCE_ROLES)
    item = db.query(AccountingPeriod).filter(AccountingPeriod.id == period_id, AccountingPeriod.company_id == context.company_id).with_for_update().first()
    if not item or item.status != "open":
        raise HTTPException(status_code=409, detail="Only an open company period can be locked")
    drafts = db.query(JournalEntry.id).filter(JournalEntry.company_id == context.company_id, JournalEntry.entry_date.between(item.period_start, item.period_end), JournalEntry.status == "draft").count()
    if drafts:
        raise HTTPException(status_code=409, detail=f"Resolve {drafts} draft journal entries before locking the period")
    item.status = "locked"
    item.locked_by_user_id = context.user.id
    item.locked_at = _now()
    item.close_note = payload.note
    db.commit()
    db.refresh(item)
    return item


@router.post("/accounting-periods/{period_id}/close")
def close_accounting_period(period_id: UUID, payload: AccountingPeriodAction, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    item = db.query(AccountingPeriod).filter(AccountingPeriod.id == period_id, AccountingPeriod.company_id == context.company_id).with_for_update().first()
    if not item or item.status != "locked":
        raise HTTPException(status_code=409, detail="Only a locked period can be closed")
    if item.locked_by_user_id == context.user.id:
        raise HTTPException(status_code=409, detail="Maker/checker control: the period locker cannot close it")
    item.status = "closed"
    item.closed_by_user_id = context.user.id
    item.closed_at = _now()
    item.close_note = payload.note
    db.commit()
    db.refresh(item)
    return item


@router.get("/bank-statement-lines")
def list_bank_lines(status: str | None = None, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, FINANCIAL_CONTROL_ROLES)
    query = db.query(BankStatementLine).filter(BankStatementLine.company_id == context.company_id)
    if status:
        query = query.filter(BankStatementLine.status == status)
    return query.order_by(BankStatementLine.transaction_date.desc()).limit(1000).all()


@router.post("/bank-statement-lines", status_code=201)
def create_bank_line(payload: BankStatementLineCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, FINANCIAL_CONTROL_ROLES)
    fingerprint = bank_line_fingerprint(company_id=context.company_id, account_reference=payload.account_reference, transaction_date=payload.transaction_date, description=payload.description, reference=payload.reference, amount=payload.amount)
    existing = db.query(BankStatementLine).filter(BankStatementLine.company_id == context.company_id, BankStatementLine.source_fingerprint == fingerprint).first()
    if existing:
        return existing
    item = BankStatementLine(
        company_id=context.company_id,
        branch_id=_branch(context),
        account_reference=(payload.account_reference or "").strip() or None,
        transaction_date=payload.transaction_date,
        description=payload.description.strip(),
        reference=(payload.reference or "").strip() or None,
        amount=payload.amount,
        currency=payload.currency.upper(),
        source_fingerprint=fingerprint,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/bank-statement-lines/{line_id}/match")
def reconcile_bank_line(line_id: UUID, payload: BankStatementMatch, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, FINANCIAL_CONTROL_ROLES)
    line = db.query(BankStatementLine).filter(BankStatementLine.id == line_id, BankStatementLine.company_id == context.company_id).with_for_update().first()
    payment = db.query(PaymentTransaction).filter(PaymentTransaction.id == payload.payment_id, PaymentTransaction.company_id == context.company_id).first()
    if not line or not payment:
        raise HTTPException(status_code=404, detail="Statement line or payment not found")
    match_bank_line(db, line=line, payment=payment, user_id=context.user.id)
    db.commit()
    db.refresh(line)
    return line


@router.get("/loan-security/{loan_id}")
def list_loan_security(loan_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER})
    _loan(db, context, loan_id)
    return {
        "guarantors": db.query(LoanGuarantor).filter(LoanGuarantor.company_id == context.company_id, LoanGuarantor.loan_id == loan_id).all(),
        "collateral": db.query(LoanCollateral).filter(LoanCollateral.company_id == context.company_id, LoanCollateral.loan_id == loan_id).all(),
    }


@router.post("/guarantors", status_code=201)
def create_guarantor(payload: GuarantorCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER})
    loan = _loan(db, context, payload.loan_id)
    if payload.guarantor_borrower_id == loan.borrower_id:
        raise HTTPException(status_code=422, detail="A borrower cannot guarantee their own loan")
    if payload.guarantor_borrower_id and not db.get(Borrower, payload.guarantor_borrower_id):
        raise HTTPException(status_code=404, detail="Linked guarantor borrower profile not found")
    item = LoanGuarantor(company_id=context.company_id, loan_id=loan.id, **payload.model_dump(exclude={"loan_id"}))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/guarantors/{guarantor_id}/verify")
def verify_guarantor(guarantor_id: UUID, payload: GuarantorVerify, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER, UserRole.COMPLIANCE_OFFICER})
    item = db.query(LoanGuarantor).filter(LoanGuarantor.id == guarantor_id, LoanGuarantor.company_id == context.company_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Guarantor not found")
    if not item.consent_obtained and payload.verification_status == "verified":
        raise HTTPException(status_code=409, detail="Guarantor consent must be recorded before verification")
    item.verification_status = payload.verification_status
    item.verified_by_user_id = context.user.id
    item.verified_at = _now()
    db.commit()
    db.refresh(item)
    return item


@router.post("/collateral", status_code=201)
def create_collateral(payload: CollateralCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER})
    loan = _loan(db, context, payload.loan_id)
    if payload.forced_sale_value is not None and payload.forced_sale_value > payload.estimated_value:
        raise HTTPException(status_code=422, detail="Forced-sale value cannot exceed estimated value")
    item = LoanCollateral(company_id=context.company_id, loan_id=loan.id, **payload.model_dump(exclude={"loan_id"}))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/complaints")
def list_complaints(status: str | None = None, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, CUSTOMER_CONTROL_ROLES)
    query = db.query(ComplaintCase).filter(ComplaintCase.company_id == context.company_id)
    if status:
        query = query.filter(ComplaintCase.status == status)
    return query.order_by(ComplaintCase.created_at.desc()).limit(1000).all()


@router.post("/complaints", status_code=201)
def create_staff_complaint(payload: ComplaintCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, CUSTOMER_CONTROL_ROLES)
    borrower_id = None
    if payload.loan_id:
        borrower_id = _loan(db, context, payload.loan_id).borrower_id
    item = ComplaintCase(
        reference=new_case_reference("CMP"), company_id=context.company_id, borrower_id=borrower_id,
        loan_id=payload.loan_id, category=payload.category, subject=payload.subject, description=payload.description,
        priority=payload.priority, submitted_by_user_id=context.user.id, due_at=_now() + timedelta(days=10),
    )
    db.add(item)
    db.flush()
    enqueue_webhook(db, company_id=context.company_id, event_type="complaint.created", aggregate_type="complaint", aggregate_id=str(item.id), idempotency_key=f"complaint:{item.id}:created", payload={"id": str(item.id), "reference": item.reference, "status": item.status, "priority": item.priority})
    db.commit()
    db.refresh(item)
    return item


@router.patch("/complaints/{complaint_id}")
def update_complaint(complaint_id: UUID, payload: ComplaintUpdate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, CUSTOMER_CONTROL_ROLES)
    item = db.query(ComplaintCase).filter(ComplaintCase.id == complaint_id, ComplaintCase.company_id == context.company_id).with_for_update().first()
    if not item:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if payload.status in {"resolved", "closed"} and not (payload.resolution or item.resolution):
        raise HTTPException(status_code=422, detail="A resolution is required to resolve or close a complaint")
    item.status = payload.status
    item.resolution = payload.resolution
    item.assigned_to_user_id = payload.assigned_to_user_id
    if payload.status in {"resolved", "closed"}:
        item.resolved_by_user_id = context.user.id
        item.resolved_at = _now()
    db.commit()
    db.refresh(item)
    return item


@router.post("/my-complaints", status_code=201)
def create_my_complaint(payload: ComplaintCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not current_user.borrower_profile:
        raise HTTPException(status_code=403, detail="A borrower profile is required")
    company_id = payload.company_id
    if payload.loan_id:
        loan = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.id == payload.loan_id, ClientCompanyLoan.borrower_id == current_user.borrower_profile.id).first()
        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found")
        company_id = loan.company_id
    if company_id and not db.get(LoanCompany, company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    item = ComplaintCase(
        reference=new_case_reference("CMP"), company_id=company_id, borrower_id=current_user.borrower_profile.id,
        loan_id=payload.loan_id, category=payload.category, subject=payload.subject, description=payload.description,
        priority=payload.priority, submitted_by_user_id=current_user.id, due_at=_now() + timedelta(days=10),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/my-complaints")
def list_my_complaints(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not current_user.borrower_profile:
        return []
    return db.query(ComplaintCase).filter(ComplaintCase.borrower_id == current_user.borrower_profile.id).order_by(ComplaintCase.created_at.desc()).all()


@router.post("/data-rights", status_code=201)
def create_data_rights_request(payload: DataRightsCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    active = db.query(DataRightsRequest).filter(DataRightsRequest.user_id == current_user.id, DataRightsRequest.request_type == payload.request_type, DataRightsRequest.status.notin_(["completed", "rejected"])).first()
    if active:
        raise HTTPException(status_code=409, detail="An active request of this type already exists")
    item = DataRightsRequest(
        reference=new_case_reference("DSR"), user_id=current_user.id,
        borrower_id=current_user.borrower_profile.id if current_user.borrower_profile else None,
        request_type=payload.request_type, description=payload.description, due_at=_now() + timedelta(days=30),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/data-rights/mine")
def list_my_data_rights(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return db.query(DataRightsRequest).filter(DataRightsRequest.user_id == current_user.id).order_by(DataRightsRequest.created_at.desc()).all()


@router.get("/data-rights")
def list_data_rights(status: str | None = None, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    if not context.is_platform_admin:
        require_tenant_roles(context, {UserRole.DATA_PROTECTION_OFFICER})
    query = db.query(DataRightsRequest)
    if not context.is_platform_admin:
        borrower_ids = db.query(CompanyBorrowerAccount.borrower_id).filter(CompanyBorrowerAccount.company_id == context.company_id)
        query = query.filter(DataRightsRequest.borrower_id.in_(borrower_ids))
    if status:
        query = query.filter(DataRightsRequest.status == status)
    return query.order_by(DataRightsRequest.created_at.desc()).limit(1000).all()


@router.post("/data-rights/{request_id}/complete")
def complete_data_rights(request_id: UUID, payload: DataRightsComplete, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    if not context.is_platform_admin:
        require_tenant_roles(context, {UserRole.DATA_PROTECTION_OFFICER})
    item = db.get(DataRightsRequest, request_id)
    if not item or item.status in {"completed", "rejected"}:
        raise HTTPException(status_code=409, detail="Active data-rights request not found")
    if not context.is_platform_admin:
        related = db.query(CompanyBorrowerAccount.id).filter(
            CompanyBorrowerAccount.company_id == context.company_id,
            CompanyBorrowerAccount.borrower_id == item.borrower_id,
        ).first()
        if not related:
            raise HTTPException(status_code=404, detail="Data-rights request is outside the active company")
    item.status = "completed"
    item.decision = payload.decision
    item.assigned_to_user_id = context.user.id
    item.completed_at = _now()
    db.commit()
    db.refresh(item)
    return item


@router.get("/webhook-outbox")
def list_webhook_outbox(status: str | None = None, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.IT_SUPPORT, UserRole.INFORMATION_SECURITY_OFFICER})
    query = db.query(WebhookOutboxEvent).filter(WebhookOutboxEvent.company_id == context.company_id)
    if status:
        query = query.filter(WebhookOutboxEvent.status == status)
    return query.order_by(WebhookOutboxEvent.created_at.desc()).limit(1000).all()


@router.post("/webhook-outbox/{event_id}/replay")
def replay_webhook(event_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.IT_SUPPORT, UserRole.INFORMATION_SECURITY_OFFICER})
    item = db.query(WebhookOutboxEvent).filter(WebhookOutboxEvent.id == event_id, WebhookOutboxEvent.company_id == context.company_id).with_for_update().first()
    if not item:
        raise HTTPException(status_code=404, detail="Webhook outbox event not found")
    replay_outbox_event(db, event=item)
    db.commit()
    db.refresh(item)
    return item
