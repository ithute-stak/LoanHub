from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from core.access_control import get_current_active_user, require_platform_admin
from database.models.audit_log import AuditLog
from database.models.borrower import Borrower
from database.models.enums import UserRole
from database.models.user import User
from database.schemas.borrower import BorrowerCreate, BorrowerRead, BorrowerUpdate
from database.schemas.origination import FinancialProfileUpdate
from database.session import get_db
from services.origination_service import financial_profile_payload, save_financial_profile


router = APIRouter(prefix="/borrowers", tags=["Borrowers"])


def borrower_or_404(db: Session, borrower_id: UUID) -> Borrower:
    borrower = db.query(Borrower).filter(Borrower.id == borrower_id).first()
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    return borrower


@router.get("/", response_model=list[BorrowerRead])
def list_borrowers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    return db.query(Borrower).order_by(Borrower.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/me", response_model=BorrowerRead)
def get_my_borrower_profile(
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.BORROWER or not current_user.borrower_profile:
        raise HTTPException(status_code=404, detail="Borrower profile not found")
    return current_user.borrower_profile


@router.get("/{borrower_id}", response_model=BorrowerRead)
def get_borrower(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = borrower_or_404(db, borrower_id)
    if current_user.role == UserRole.SUPERADMIN:
        return borrower
    if current_user.role == UserRole.BORROWER and borrower.user_id == current_user.id:
        return borrower
    raise HTTPException(status_code=403, detail="Use the marketplace unlock flow to access borrower details")


@router.post("/", response_model=BorrowerRead, status_code=status.HTTP_201_CREATED)
def create_borrower(
    payload: BorrowerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    if db.query(Borrower).filter(Borrower.user_id == payload.user_id).first():
        raise HTTPException(status_code=409, detail="User already has a borrower profile")
    borrower = Borrower(**payload.model_dump())
    db.add(borrower)
    db.commit()
    db.refresh(borrower)
    return borrower


@router.put("/{borrower_id}", response_model=BorrowerRead)
def update_borrower(
    borrower_id: UUID,
    payload: BorrowerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = borrower_or_404(db, borrower_id)
    if current_user.role != UserRole.SUPERADMIN and borrower.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot update another borrower profile")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(borrower, field, value)
    db.commit()
    db.refresh(borrower)
    return borrower


@router.delete("/{borrower_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_borrower(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    borrower = borrower_or_404(db, borrower_id)
    db.delete(borrower)
    db.commit()

def _current_borrower_or_404(db: Session, user: User) -> Borrower:
    borrower = db.query(Borrower).filter(Borrower.user_id == user.id).first()
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower profile not found")
    return borrower


def _borrower_safe_financial_payload(
    db: Session,
    *,
    borrower: Borrower,
    payload: FinancialProfileUpdate,
) -> FinancialProfileUpdate:
    """Prevent a borrower from self-verifying regulated assessment fields."""
    safe = payload.model_copy(deep=True)
    existing = financial_profile_payload(
        db,
        company_id=None,
        borrower_id=borrower.id,
    )

    existing_kyc = existing.get("kyc") or {}
    for field in (
        "identity_verified",
        "address_verified",
        "phone_verified",
        "sanctions_hit",
        "politically_exposed",
        "adverse_media_hit",
        "fraud_flag",
        "verification_notes",
        "expires_at",
    ):
        setattr(safe.kyc, field, existing_kyc.get(field, getattr(safe.kyc, field)))
    current_status = existing_kyc.get("status")
    safe.kyc.status = (
        current_status
        if current_status in {"verified", "enhanced_due_diligence", "failed"}
        else ("documents_pending" if safe.kyc.document_file_ids else "not_started")
    )

    existing_employment = existing.get("employment") or {}
    for field in (
        "verified_net_income",
        "verification_method",
        "verification_status",
        "payslip_count",
        "bank_statement_months",
    ):
        setattr(
            safe.employment,
            field,
            existing_employment.get(field, getattr(safe.employment, field)),
        )

    verified_incomes = {
        (row.get("source_type"), row.get("description")): row
        for row in existing.get("income_sources", [])
    }
    for row in safe.income_sources:
        previous = verified_incomes.get((row.source_type, row.description))
        unchanged = previous and Decimal(previous.get("declared_amount") or 0) == Decimal(
            row.declared_amount or 0
        )
        row.is_verified = bool(unchanged and previous.get("is_verified"))
        row.verified_amount = (
            Decimal(previous.get("verified_amount") or 0)
            if row.is_verified
            else Decimal("0")
        )
        row.verification_method = (
            previous.get("verification_method") if row.is_verified else None
        )

    for row in safe.expenses:
        row.is_verified = False
        row.verification_notes = None

    for row in safe.debts:
        row.is_verified = False
        row.source = "declared"

    existing_banks = {
        str(row.get("id")): row for row in existing.get("bank_accounts", [])
    }
    for row in safe.bank_accounts:
        previous = existing_banks.get(str(row.id)) if row.id else None
        if previous and not row.account_number:
            row.verification_status = previous.get("verification_status", "unverified")
            row.verification_reference = previous.get("verification_reference")
        else:
            row.verification_status = "unverified"
            row.verification_reference = None
    safe.bank_account = None
    return safe


@router.get("/me/financial-profile")
def get_my_financial_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = _current_borrower_or_404(db, current_user)
    return financial_profile_payload(
        db,
        company_id=None,
        borrower_id=borrower.id,
    )


@router.put("/me/financial-profile")
def put_my_financial_profile(
    payload: FinancialProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = _current_borrower_or_404(db, current_user)
    safe_payload = _borrower_safe_financial_payload(
        db,
        borrower=borrower,
        payload=payload,
    )
    return save_financial_profile(
        db,
        company_id=None,
        borrower_id=borrower.id,
        user_id=current_user.id,
        payload=safe_payload,
        actor_role=UserRole.BORROWER.value,
    )


@router.get("/me/profile-activity")
def get_my_profile_activity(
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    borrower = _current_borrower_or_404(db, current_user)
    rows = (
        db.query(AuditLog)
        .options(
            joinedload(AuditLog.user).joinedload(User.person),
            joinedload(AuditLog.company),
        )
        .filter(
            or_(
                AuditLog.record_id == borrower.id,
                AuditLog.event_data.op("->>")("borrower_id") == str(borrower.id),
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "action": row.action,
            "description": row.description,
            "actor_type": (
                "borrower"
                if row.actor_role == UserRole.BORROWER.value
                else ("company" if row.company_id else "system")
            ),
            "actor_name": (
                row.user.person.full_name
                if row.user and row.user.person
                else (
                    (row.user.email or row.user.phone)
                    if row.user
                    else "LoanHub system"
                )
            ),
            "company_name": row.company.name if row.company else None,
            "changed_fields": row.changed_fields or [],
            "created_at": row.created_at,
        }
        for row in rows
    ]

