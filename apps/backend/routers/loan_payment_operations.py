from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.access_control import (
    COLLECTIONS_ROLES, COMPANY_MANAGEMENT_ROLES, FINANCE_ROLES, LENDING_ROLES,
    TenantContext, get_current_active_user, get_tenant_context, require_tenant_roles,
)
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import UserRole
from database.models.loan_payment_operations import (
    AccountingExport, BorrowerReminderPreference, LoanRestructureRequest,
    OnlineRepaymentMandate, RepaymentReminder,
)
from database.models.user import User
from database.schemas.loan_payment_operations import (
    AccountingExportCreate, BorrowerMandateCreate, ReminderPreferenceUpdate,
    RestructureApprovalCreate, RestructureRequestCreate,
)
from database.session import get_db
from services.loan_payment_operations_service import (
    approve_restructure, cancel_online_mandate, create_accounting_export,
    create_online_mandate, create_restructure_request, schedule_repayment_reminders,
    run_due_mandate_collections,
)


router = APIRouter(prefix="/loan-payment-operations", tags=["Loan payment operations"])
OPERATION_ROLES = set(COLLECTIONS_ROLES) | set(COMPANY_MANAGEMENT_ROLES) | set(FINANCE_ROLES) | set(LENDING_ROLES)


def serialize(row):
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    for key, value in list(data.items()):
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
        elif hasattr(value, "as_tuple"):
            data[key] = str(value)
    return data


def borrower_loan(db: Session, user: User, loan_id: UUID) -> ClientCompanyLoan:
    if user.role != UserRole.BORROWER or not user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access required")
    loan = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.id == loan_id, ClientCompanyLoan.borrower_id == user.borrower_profile.id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


@router.get("/summary")
def summary(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, OPERATION_ROLES)
    company_id = context.company_id
    def count(model, *filters):
        return int(db.query(func.count(model.id)).filter(model.company_id == company_id, *filters).scalar() or 0)
    return {
        "active_mandates": count(OnlineRepaymentMandate, OnlineRepaymentMandate.status.in_(["active", "approved", "processing"])),
        "mandates_due": count(OnlineRepaymentMandate, OnlineRepaymentMandate.status == "active", OnlineRepaymentMandate.next_debit_date <= func.current_date()),
        "reminders_attention": count(RepaymentReminder, RepaymentReminder.status.in_(["failed", "configuration_required"])),
        "restructures_pending": count(LoanRestructureRequest, LoanRestructureRequest.status == "requested"),
        "accounting_exports": count(AccountingExport),
    }


@router.get("/borrower/mandates")
def my_mandates(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    if user.role != UserRole.BORROWER or not user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access required")
    return [serialize(row) for row in db.query(OnlineRepaymentMandate).filter(OnlineRepaymentMandate.borrower_id == user.borrower_profile.id).order_by(OnlineRepaymentMandate.created_at.desc()).all()]


@router.post("/borrower/mandates", status_code=201)
def create_my_mandate(body: BorrowerMandateCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    loan = borrower_loan(db, user, body.loan_id)
    return serialize(create_online_mandate(db, loan=loan, user_id=user.id, payload=body))


@router.post("/borrower/mandates/{mandate_id}/cancel")
def cancel_my_mandate(mandate_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    if user.role != UserRole.BORROWER or not user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access required")
    row = db.query(OnlineRepaymentMandate).filter(OnlineRepaymentMandate.id == mandate_id, OnlineRepaymentMandate.borrower_id == user.borrower_profile.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Mandate not found")
    return serialize(cancel_online_mandate(db, row=row))


@router.get("/borrower/reminder-preferences")
def my_preferences(company_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    if user.role != UserRole.BORROWER or not user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access required")
    row = db.query(BorrowerReminderPreference).filter(BorrowerReminderPreference.company_id == company_id, BorrowerReminderPreference.borrower_id == user.borrower_profile.id).first()
    if not row:
        row = BorrowerReminderPreference(company_id=company_id, borrower_id=user.borrower_profile.id)
        db.add(row); db.commit(); db.refresh(row)
    return serialize(row)


@router.put("/borrower/reminder-preferences")
def save_my_preferences(company_id: UUID, body: ReminderPreferenceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    if user.role != UserRole.BORROWER or not user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access required")
    row = db.query(BorrowerReminderPreference).filter(BorrowerReminderPreference.company_id == company_id, BorrowerReminderPreference.borrower_id == user.borrower_profile.id).first() or BorrowerReminderPreference(company_id=company_id, borrower_id=user.borrower_profile.id)
    for key, value in body.model_dump().items(): setattr(row, key, value)
    db.add(row); db.commit(); db.refresh(row)
    return serialize(row)


@router.get("/borrower/restructures")
def my_restructures(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    if user.role != UserRole.BORROWER or not user.borrower_profile:
        raise HTTPException(status_code=403, detail="Borrower access required")
    return [serialize(row) for row in db.query(LoanRestructureRequest).filter(LoanRestructureRequest.borrower_id == user.borrower_profile.id).order_by(LoanRestructureRequest.created_at.desc()).all()]


@router.post("/borrower/restructures", status_code=201)
def create_my_restructure(body: RestructureRequestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    loan = borrower_loan(db, user, body.loan_id)
    return serialize(create_restructure_request(db, loan=loan, user_id=user.id, payload=body))


@router.get("/restructures")
def restructures(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, OPERATION_ROLES)
    return [serialize(row) for row in db.query(LoanRestructureRequest).filter(LoanRestructureRequest.company_id == context.company_id).order_by(LoanRestructureRequest.created_at.desc()).limit(500).all()]


@router.post("/restructures/{request_id}/approve")
def approve_request(request_id: UUID, body: RestructureApprovalCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, set(FINANCE_ROLES) | set(COMPANY_MANAGEMENT_ROLES))
    row = db.query(LoanRestructureRequest).filter(LoanRestructureRequest.id == request_id, LoanRestructureRequest.company_id == context.company_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Restructure request not found")
    return serialize(approve_restructure(db, row=row, user_id=context.user.id, approved_rate=body.approved_rate_percent, agreement_reference=body.agreement_reference))


@router.post("/reminders/run")
def run_reminders(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, OPERATION_ROLES)
    return schedule_repayment_reminders(db, company_id=context.company_id, run_by_user_id=context.user.id)


@router.post("/mandates/run-due")
def run_mandates(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, set(FINANCE_ROLES) | set(COMPANY_MANAGEMENT_ROLES))
    return run_due_mandate_collections(db, company_id=context.company_id, user_id=context.user.id)


@router.get("/reminders")
def reminders(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, OPERATION_ROLES)
    return [serialize(row) for row in db.query(RepaymentReminder).filter(RepaymentReminder.company_id == context.company_id).order_by(RepaymentReminder.created_at.desc()).limit(500).all()]


@router.post("/accounting-exports", status_code=201)
def generate_export(body: AccountingExportCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, set(FINANCE_ROLES) | set(COMPANY_MANAGEMENT_ROLES))
    return serialize(create_accounting_export(db, company_id=context.company_id, user_id=context.user.id, payload=body))


@router.get("/accounting-exports")
def accounting_exports(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, OPERATION_ROLES)
    return [serialize(row) for row in db.query(AccountingExport).filter(AccountingExport.company_id == context.company_id).order_by(AccountingExport.created_at.desc()).limit(500).all()]
