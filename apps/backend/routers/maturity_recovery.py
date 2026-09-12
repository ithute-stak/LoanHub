from __future__ import annotations

from datetime import datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.config.config import settings
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus
from database.models.lending_operations import CollectionCase
from database.models.maturity_recovery import LoanRenewalCycle
from database.schemas.maturity_recovery import (
    MaturityRenewalPolicyRead,
    MaturityRenewalPolicyUpdate,
    StopLoanRenewalRequest,
)
from database.session import get_db
from services.maturity_recovery_service import (
    assert_or_claim_collection_case,
    effective_auto_renewal,
    ensure_collection_case_for_loan,
    get_or_create_maturity_policy,
    release_collection_case_claim,
    run_maturity_recovery_cycle,
)

router = APIRouter(prefix="/maturity-recovery", tags=["Maturity Renewal and Recovery"])


def _company_id(context: TenantContext) -> UUID:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    return context.company_id


def _management_company_id(context: TenantContext) -> UUID:
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    return _company_id(context)


def _loan_or_404(db: Session, context: TenantContext, loan_id: UUID) -> ClientCompanyLoan:
    company_id = _company_id(context)
    loan = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == company_id,
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    assert_branch_scope(context, loan.branch_id)
    return loan


def _borrower_name(loan: ClientCompanyLoan) -> str:
    borrower = getattr(loan, "borrower", None)
    user = getattr(borrower, "user", None) if borrower else None
    person = getattr(user, "person", None) if user else None
    if not person:
        return "Borrower"
    return " ".join(value for value in [person.first_name, person.middle_name, person.last_name] if value) or "Borrower"


@router.get("/policy", response_model=MaturityRenewalPolicyRead)
def read_policy(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    company_id = _management_company_id(context)
    policy = get_or_create_maturity_policy(db, company_id)
    db.commit()
    db.refresh(policy)
    return policy


@router.patch("/policy", response_model=MaturityRenewalPolicyRead)
def update_policy(
    payload: MaturityRenewalPolicyUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    company_id = _management_company_id(context)
    policy = get_or_create_maturity_policy(db, company_id)
    for key, value in payload.model_dump().items():
        setattr(policy, key, value)
    policy.configured_by_user_id = context.user.id
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    company_id = _management_company_id(context)
    policy = get_or_create_maturity_policy(db, company_id)
    now = datetime.now(ZoneInfo(settings.APP_TIMEZONE))
    query = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
        ClientCompanyLoan.balance > 0,
    )
    if context.branch_id:
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    loans = query.order_by(ClientCompanyLoan.maturity_date.asc().nullslast()).limit(1000).all()
    rows = []
    for loan in loans:
        cycle = db.query(LoanRenewalCycle).filter(
            LoanRenewalCycle.loan_id == loan.id,
        ).order_by(LoanRenewalCycle.cycle_number.desc()).first()
        rows.append({
            "id": str(loan.id),
            "loan_reference": loan.loan_reference,
            "borrower_name": _borrower_name(loan),
            "branch_id": str(loan.branch_id) if loan.branch_id else None,
            "balance": float(loan.balance or 0),
            "installment_amount": float(loan.installment_amount or 0),
            "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else None,
            "original_maturity_date": loan.original_maturity_date.isoformat() if loan.original_maturity_date else None,
            "renewal_cycle_count": int(loan.renewal_cycle_count or 0),
            "automatic_renewal_enabled": loan.automatic_renewal_enabled,
            "effective_auto_renewal": effective_auto_renewal(loan, policy),
            "renewal_stopped_at": loan.renewal_stopped_at.isoformat() if loan.renewal_stopped_at else None,
            "renewal_stop_reason": loan.renewal_stop_reason,
            "is_matured": bool(loan.maturity_date and loan.maturity_date < now.date()),
            "latest_cycle": ({
                "cycle_number": cycle.cycle_number,
                "opening_balance": float(cycle.opening_balance),
                "total_repayable": float(cycle.total_repayable),
                "installment_amount": float(cycle.installment_amount),
                "started_on": cycle.started_on.isoformat(),
                "maturity_date": cycle.maturity_date.isoformat(),
            } if cycle else None),
        })
    db.commit()
    return {
        "policy": MaturityRenewalPolicyRead.model_validate(policy).model_dump(mode="json"),
        "summary": {
            "active_facilities": len(rows),
            "matured_with_balance": sum(1 for item in rows if item["is_matured"]),
            "auto_renewing": sum(1 for item in rows if item["effective_auto_renewal"]),
            "renewal_stopped": sum(1 for item in rows if not item["effective_auto_renewal"]),
        },
        "loans": rows,
    }


@router.post("/run")
def run_now(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    company_id = _management_company_id(context)
    return run_maturity_recovery_cycle(db, company_id=company_id)


@router.post("/loans/{loan_id}/stop")
def stop_loan_renewal(
    loan_id: UUID,
    payload: StopLoanRenewalRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _management_company_id(context)
    loan = _loan_or_404(db, context, loan_id)
    now = datetime.now(ZoneInfo(settings.APP_TIMEZONE))
    loan.automatic_renewal_enabled = False
    loan.renewal_stopped_at = now
    loan.renewal_stopped_by_user_id = context.user.id
    loan.renewal_stop_reason = payload.reason.strip()
    collection_case_id = None
    if loan.balance > 0 and loan.maturity_date and loan.maturity_date < now.date():
        case = ensure_collection_case_for_loan(
            db,
            loan,
            today=now.date(),
            next_action_at=datetime.combine(now.date(), time(hour=7)),
        )
        collection_case_id = str(case.id)
    db.commit()
    return {
        "loan_id": str(loan.id),
        "automatic_renewal_enabled": False,
        "collection_case_id": collection_case_id,
        "message": "Automatic maturity renewal stopped. Mature unpaid balances are now routed to recovery.",
    }


@router.post("/loans/{loan_id}/resume")
def resume_loan_renewal(
    loan_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _management_company_id(context)
    loan = _loan_or_404(db, context, loan_id)
    case = db.query(CollectionCase).filter(
        CollectionCase.company_id == loan.company_id,
        CollectionCase.loan_id == loan.id,
    ).first()
    if case and (case.stage == "legal" or case.status in {"legal", "written_off"}):
        raise HTTPException(status_code=409, detail="A legal or written-off recovery case cannot return to automatic renewal")
    loan.automatic_renewal_enabled = True
    loan.renewal_stopped_at = None
    loan.renewal_stopped_by_user_id = None
    loan.renewal_stop_reason = None
    db.commit()
    return {
        "loan_id": str(loan.id),
        "automatic_renewal_enabled": True,
        "message": "Automatic maturity renewal resumed for this loan.",
    }


@router.post("/collections/cases/{case_id}/claim")
def claim_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COLLECTIONS_ROLES)
    company_id = _company_id(context)
    case = db.query(CollectionCase).filter(CollectionCase.id == case_id, CollectionCase.company_id == company_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Collection case not found")
    assert_branch_scope(context, case.branch_id)
    row = assert_or_claim_collection_case(db, case, context.user.id)
    db.commit()
    return {
        "case_id": str(row.id),
        "claimed_by_user_id": str(row.action_claimed_by_user_id),
        "claim_expires_at": row.action_claim_expires_at.isoformat() if row.action_claim_expires_at else None,
    }


@router.delete("/collections/cases/{case_id}/claim", status_code=status.HTTP_204_NO_CONTENT)
def release_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COLLECTIONS_ROLES)
    company_id = _company_id(context)
    case = db.query(CollectionCase).filter(CollectionCase.id == case_id, CollectionCase.company_id == company_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Collection case not found")
    assert_branch_scope(context, case.branch_id)
    release_collection_case_claim(db, case, context.user.id)
    db.commit()
    return None
