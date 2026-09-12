from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    PLATFORM_FINANCE_ROLES,
    get_current_active_user,
    is_platform_role,
    resolve_tenant_context,
)
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import UserRole
from database.models.payment import PaymentTransaction
from database.models.user import User
from database.schemas.payment import PaymentTransactionRead
from database.session import get_db


router = APIRouter(prefix="/payments", tags=["Platform Payment Register"])


def _payment_query(db: Session):
    return db.query(PaymentTransaction).options(joinedload(PaymentTransaction.cash_transaction))


@router.get("/", response_model=list[PaymentTransactionRead])
def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = _payment_query(db)
    if is_platform_role(current_user.role):
        if current_user.role not in PLATFORM_FINANCE_ROLES:
            raise HTTPException(status_code=403, detail="Platform finance permission is required")
    elif current_user.role == UserRole.BORROWER:
        if not current_user.borrower_profile:
            return []
        query = query.filter(PaymentTransaction.borrower_id == current_user.borrower_profile.id)
    else:
        context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
        query = query.filter(PaymentTransaction.company_id == context.company_id)
        if context.branch_id and context.role not in {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}:
            query = query.join(ClientCompanyLoan, ClientCompanyLoan.id == PaymentTransaction.loan_id).filter(
                ClientCompanyLoan.branch_id == context.branch_id
            )
    return query.order_by(PaymentTransaction.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{payment_id}", response_model=PaymentTransactionRead)
def get_payment(
    payment_id: UUID,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    payment = _payment_query(db).filter(PaymentTransaction.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment transaction not found")
    if is_platform_role(current_user.role):
        if current_user.role not in PLATFORM_FINANCE_ROLES:
            raise HTTPException(status_code=403, detail="Platform finance permission is required")
        return payment
    if current_user.role == UserRole.BORROWER:
        if not current_user.borrower_profile or payment.borrower_id != current_user.borrower_profile.id:
            raise HTTPException(status_code=403, detail="Payment transaction is not available to you")
        return payment
    context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
    if payment.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    return payment
