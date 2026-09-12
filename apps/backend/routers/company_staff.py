from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import distinct, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    PLATFORM_ROLES,
    TenantContext,
    assert_branch_scope,
    assert_company_scope,
    get_tenant_context,
    require_tenant_roles,
)
from core.security import hash_password
from database.models.branch import CompanyBranch
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.models.person import Person
from database.models.user import User
from database.schemas.company_staff import (
    CompanyStaffAccountCreate,
    CompanyStaffCreate,
    CompanyStaffRead,
    CompanyStaffUpdate,
    CompanyStaffUserStatusUpdate,
)
from database.session import get_db
from services.billing_service import enforce_company_limit


router = APIRouter(prefix="/company-staff", tags=["Company Staff"])

ALLOWED_STAFF_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.LOAN_OFFICER,
    UserRole.FINANCE_OFFICER,
    UserRole.COLLECTIONS_OFFICER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.CUSTOMER_SUPPORT,
    UserRole.HR_MANAGER,
    UserRole.PERFORMANCE_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.IT_SUPPORT,
    UserRole.CREDIT_ANALYST,
    UserRole.AML_CFT_OFFICER,
    UserRole.TREASURY_OFFICER,
    UserRole.DATA_PROTECTION_OFFICER,
    UserRole.REGULATORY_REPORTING_OFFICER,
    UserRole.OPERATIONS_OFFICER,
    UserRole.INFORMATION_SECURITY_OFFICER,
}


def staff_query(db: Session):
    return db.query(CompanyStaff).options(
        joinedload(CompanyStaff.user).joinedload(User.person),
        joinedload(CompanyStaff.company),
        joinedload(CompanyStaff.branch),
    )


def staff_or_404(db: Session, staff_id: UUID) -> CompanyStaff:
    staff = staff_query(db).filter(CompanyStaff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Company staff member not found")
    return staff


def validate_branch(db: Session, company_id: UUID, branch_id: UUID | None) -> None:
    if not branch_id:
        return
    branch = (
        db.query(CompanyBranch)
        .filter(
            CompanyBranch.id == branch_id,
            CompanyBranch.company_id == company_id,
        )
        .first()
    )
    if not branch:
        raise HTTPException(status_code=400, detail="Branch does not belong to the selected company")


def ensure_manageable_target(context: TenantContext, target: CompanyStaff) -> None:
    assert_company_scope(context, target.company_id)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if (
        not context.is_platform_admin
        and target.role == UserRole.COMPANY_OWNER
        and target.user_id != context.user.id
    ):
        raise HTTPException(status_code=403, detail="Only the platform owner can modify another company owner")


@router.get("/", response_model=list[CompanyStaffRead])
def list_company_staff(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    query = staff_query(db)
    if not context.is_platform_admin:
        query = query.filter(CompanyStaff.company_id == context.company_id)
        if context.staff and context.staff.role == UserRole.BRANCH_MANAGER:
            query = query.filter(CompanyStaff.branch_id == context.branch_id)
    return query.order_by(CompanyStaff.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{staff_id}", response_model=CompanyStaffRead)
def get_company_staff_member(
    staff_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    staff = staff_or_404(db, staff_id)
    assert_company_scope(context, staff.company_id)
    assert_branch_scope(context, staff.branch_id)
    return staff


@router.post("/", response_model=CompanyStaffRead, status_code=status.HTTP_201_CREATED)
def assign_existing_user(
    payload: CompanyStaffCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    company_id = payload.company_id if context.is_platform_admin else context.company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Company is required")
    if payload.role not in ALLOWED_STAFF_ROLES:
        raise HTTPException(status_code=400, detail="Invalid company staff role")
    if payload.role == UserRole.COMPANY_OWNER and not context.is_platform_admin:
        raise HTTPException(status_code=403, detail="Only the platform administrator can assign another owner")
    validate_branch(db, company_id, payload.branch_id)

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role in PLATFORM_ROLES | {UserRole.BORROWER}:
        raise HTTPException(
            status_code=409,
            detail="Platform administrators and borrower accounts cannot be assigned as company staff",
        )

    existing = (
        db.query(CompanyStaff)
        .filter(
            CompanyStaff.user_id == user.id,
            CompanyStaff.company_id == company_id,
            CompanyStaff.role == payload.role,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="This role is already assigned to the user")

    has_membership = (
        db.query(CompanyStaff.id)
        .filter(CompanyStaff.user_id == user.id, CompanyStaff.company_id == company_id)
        .first()
        is not None
    )
    if not has_membership:
        enforce_company_limit(
            db,
            company_id=company_id,
            resource="staff",
            current_count=(
                db.query(func.count(distinct(CompanyStaff.user_id)))
                .filter(CompanyStaff.company_id == company_id)
                .scalar()
                or 0
            ),
            fallback=5,
        )

    is_primary = payload.is_primary or not has_membership
    if is_primary:
        db.query(CompanyStaff).filter(
            CompanyStaff.user_id == user.id,
            CompanyStaff.company_id == company_id,
        ).update({CompanyStaff.is_primary: False}, synchronize_session=False)
        user.role = payload.role
    staff = CompanyStaff(
        user_id=user.id,
        company_id=company_id,
        branch_id=payload.branch_id,
        role=payload.role,
        is_primary=is_primary,
        is_active=payload.is_active,
    )
    db.add(staff)
    db.commit()
    return staff_or_404(db, staff.id)


@router.post("/accounts", response_model=CompanyStaffRead, status_code=status.HTTP_201_CREATED)
def create_staff_account(
    payload: CompanyStaffAccountCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=400, detail="Select a company before creating staff")
    if payload.role not in ALLOWED_STAFF_ROLES:
        raise HTTPException(status_code=400, detail="Invalid company staff role")
    if payload.role == UserRole.COMPANY_OWNER and not context.is_platform_admin:
        raise HTTPException(status_code=403, detail="Only the platform administrator can create another owner")
    validate_branch(db, context.company_id, payload.branch_id)
    enforce_company_limit(
        db,
        company_id=context.company_id,
        resource="staff",
        current_count=(
            db.query(func.count(distinct(CompanyStaff.user_id)))
            .filter(CompanyStaff.company_id == context.company_id)
            .scalar()
            or 0
        ),
        fallback=5,
    )

    duplicate = (
        db.query(User)
        .filter(
            or_(
                User.phone == payload.phone.strip(),
                User.email == str(payload.email) if payload.email else False,
            )
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Phone or email already exists")

    try:
        user = User(
            email=str(payload.email) if payload.email else None,
            phone=payload.phone.strip(),
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=payload.is_active,
            is_verified=False,
        )
        db.add(user)
        db.flush()

        person = Person(
            user_id=user.id,
            first_name=payload.first_name.strip(),
            middle_name=payload.middle_name,
            last_name=payload.last_name.strip(),
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
            national_id=payload.national_id,
            passport_number=payload.passport_number,
            marital_status=payload.marital_status,
            nationality=payload.nationality,
            district=payload.district,
            town_or_village=payload.town_or_village,
            physical_address=payload.physical_address,
        )
        db.add(person)

        staff = CompanyStaff(
            user_id=user.id,
            company_id=context.company_id,
            branch_id=payload.branch_id,
            role=payload.role,
            is_primary=payload.is_primary,
            is_active=payload.is_active,
        )
        db.add(staff)
        db.commit()
        return staff_or_404(db, staff.id)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Staff account details already exist") from error
    except Exception:
        db.rollback()
        raise


@router.patch("/users/{user_id}/status", response_model=list[CompanyStaffRead])
def update_company_staff_user_status(
    user_id: UUID,
    payload: CompanyStaffUserStatusUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=400, detail="Select a company before updating staff access")

    query = staff_query(db).filter(
        CompanyStaff.user_id == user_id,
        CompanyStaff.company_id == context.company_id,
    )
    memberships = query.order_by(CompanyStaff.is_primary.desc(), CompanyStaff.created_at.asc()).all()
    if not memberships:
        raise HTTPException(status_code=404, detail="Company staff account not found")

    company_id = memberships[0].company_id
    for membership in memberships:
        assert_company_scope(context, membership.company_id)
        if (
            not context.is_platform_admin
            and membership.role == UserRole.COMPANY_OWNER
            and membership.user_id != context.user.id
        ):
            raise HTTPException(
                status_code=403,
                detail="Only the platform owner can suspend another company owner",
            )

    if not payload.is_active and user_id == context.user.id:
        raise HTTPException(status_code=400, detail="You cannot suspend your own company access")

    for membership in memberships:
        membership.is_active = payload.is_active

    if payload.is_active and not any(membership.is_primary for membership in memberships):
        memberships[0].is_primary = True
        memberships[0].user.role = memberships[0].role

    db.commit()
    return (
        staff_query(db)
        .filter(
            CompanyStaff.user_id == user_id,
            CompanyStaff.company_id == company_id,
        )
        .order_by(CompanyStaff.is_primary.desc(), CompanyStaff.created_at.asc())
        .all()
    )


@router.put("/{staff_id}", response_model=CompanyStaffRead)
def update_company_staff(
    staff_id: UUID,
    payload: CompanyStaffUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    staff = staff_or_404(db, staff_id)
    ensure_manageable_target(context, staff)

    changes = payload.model_dump(exclude_unset=True)
    new_role = changes.get("role")
    if new_role:
        if new_role not in ALLOWED_STAFF_ROLES:
            raise HTTPException(status_code=400, detail="Invalid company staff role")
        if new_role == UserRole.COMPANY_OWNER and not context.is_platform_admin:
            raise HTTPException(status_code=403, detail="Only the platform administrator can assign owner role")

    branch_id = changes.get("branch_id", staff.branch_id)
    validate_branch(db, staff.company_id, branch_id)

    make_primary = changes.get("is_primary") is True
    if make_primary:
        db.query(CompanyStaff).filter(
            CompanyStaff.user_id == staff.user_id,
            CompanyStaff.company_id == staff.company_id,
            CompanyStaff.id != staff.id,
        ).update({CompanyStaff.is_primary: False}, synchronize_session=False)

    for field, value in changes.items():
        setattr(staff, field, value)
    if new_role and (staff.is_primary or make_primary):
        staff.user.role = new_role
    elif make_primary:
        staff.user.role = staff.role

    db.commit()
    return staff_or_404(db, staff.id)


@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_company_staff(
    staff_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    staff = staff_or_404(db, staff_id)
    ensure_manageable_target(context, staff)
    if staff.user_id == context.user.id:
        raise HTTPException(status_code=400, detail="You cannot remove your own active membership")
    db.delete(staff)
    db.commit()
