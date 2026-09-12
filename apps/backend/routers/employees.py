from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    HR_ROLES,
    PERFORMANCE_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.company_staff import CompanyStaff
from database.models.employee import EmployeeProfile, PerformanceGoal, PerformanceReview
from database.models.enums import UserRole
from database.models.user import User
from database.schemas.employee import (
    EmployeeProfileRead,
    EmployeeProfileUpdate,
    EmployeeRead,
    EmployeeUserRead,
    PerformanceGoalCreate,
    PerformanceGoalRead,
    PerformanceGoalUpdate,
    PerformanceReviewCreate,
    PerformanceReviewRead,
)
from database.session import get_db


router = APIRouter(prefix="/employees", tags=["Employee Management"])


def staff_query(db: Session):
    return db.query(CompanyStaff).options(
        joinedload(CompanyStaff.user).joinedload(User.person),
        joinedload(CompanyStaff.employee_profile),
        joinedload(CompanyStaff.branch),
    )


def staff_or_404(db: Session, staff_id: UUID) -> CompanyStaff:
    staff = staff_query(db).filter(CompanyStaff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Employee staff membership not found")
    return staff


def employee_read(
    staff: CompanyStaff,
    *,
    include_sensitive: bool,
) -> EmployeeRead:
    profile_read = None
    if staff.employee_profile:
        profile_read = EmployeeProfileRead.model_validate(staff.employee_profile)
        if not include_sensitive:
            profile_read = profile_read.model_copy(
                update={
                    "base_salary": None,
                    "bank_name": None,
                    "bank_account_name": None,
                    "bank_account_number": None,
                    "tax_number": None,
                    "pension_number": None,
                    "notes": None,
                }
            )

    return EmployeeRead(
        staff_id=staff.id,
        company_id=staff.company_id,
        branch_id=staff.branch_id,
        role=staff.role,
        is_active=staff.is_active,
        user=EmployeeUserRead.model_validate(staff.user),
        profile=profile_read,
    )


def can_view_sensitive_employee_data(context: TenantContext) -> bool:
    return context.is_platform_admin or context.role in HR_ROLES


def assert_employee_scope(context: TenantContext, staff: CompanyStaff) -> None:
    if context.is_platform_admin:
        return
    if staff.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company employee access is not allowed")
    assert_branch_scope(context, staff.branch_id)


@router.get("", response_model=list[EmployeeRead])
def list_employees(
    search: str | None = None,
    branch_id: UUID | None = None,
    department: str | None = None,
    active_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    if not context.is_platform_admin:
        require_tenant_roles(context, PERFORMANCE_ROLES)
    if not context.is_platform_admin and not context.company_id:
        raise HTTPException(status_code=400, detail="Company context is required")

    query = staff_query(db)
    if not context.is_platform_admin:
        query = query.filter(CompanyStaff.company_id == context.company_id)
        if context.branch_id and context.role not in {
            UserRole.COMPANY_OWNER,
            UserRole.COMPANY_ADMIN,
        }:
            query = query.filter(CompanyStaff.branch_id == context.branch_id)

    if branch_id:
        query = query.filter(CompanyStaff.branch_id == branch_id)
    if active_only:
        query = query.filter(CompanyStaff.is_active.is_(True))
    if department:
        query = query.join(EmployeeProfile, EmployeeProfile.staff_id == CompanyStaff.id).filter(
            EmployeeProfile.department == department
        )
    if search:
        token = f"%{search.strip()}%"
        query = query.join(User, User.id == CompanyStaff.user_id).outerjoin(
            EmployeeProfile, EmployeeProfile.staff_id == CompanyStaff.id
        ).filter(
            or_(
                User.email.ilike(token),
                User.phone.ilike(token),
                EmployeeProfile.employee_number.ilike(token),
                EmployeeProfile.job_title.ilike(token),
                EmployeeProfile.department.ilike(token),
            )
        )

    staff_items = query.order_by(CompanyStaff.created_at.desc()).offset(skip).limit(limit).all()
    include_sensitive = can_view_sensitive_employee_data(context)
    return [
        employee_read(staff, include_sensitive=include_sensitive)
        for staff in staff_items
    ]


@router.get("/{staff_id}", response_model=EmployeeRead)
def get_employee(
    staff_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    if not context.is_platform_admin:
        require_tenant_roles(context, PERFORMANCE_ROLES)
    staff = staff_or_404(db, staff_id)
    assert_employee_scope(context, staff)
    return employee_read(
        staff,
        include_sensitive=can_view_sensitive_employee_data(context),
    )


@router.put("/{staff_id}/profile", response_model=EmployeeRead)
def upsert_employee_profile(
    staff_id: UUID,
    payload: EmployeeProfileUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    staff = staff_or_404(db, staff_id)
    assert_employee_scope(context, staff)

    if payload.reports_to_staff_id:
        manager = staff_or_404(db, payload.reports_to_staff_id)
        if manager.company_id != staff.company_id:
            raise HTTPException(status_code=400, detail="Manager must belong to the same company")

    profile = staff.employee_profile
    # PUT remains compatible with the existing full-profile editor, but when an
    # older or narrower client omits sensitive payroll fields we preserve them
    # instead of replacing them with schema defaults such as None.
    data = payload.model_dump(exclude_unset=profile is not None)
    data["branch_id"] = staff.branch_id

    try:
        if profile:
            for field, value in data.items():
                setattr(profile, field, value)
        else:
            profile = EmployeeProfile(
                staff_id=staff.id,
                company_id=staff.company_id,
                **data,
            )
            db.add(profile)
        db.commit()
        return employee_read(
            staff_or_404(db, staff.id),
            include_sensitive=True,
        )
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Employee number already exists in this company") from error


@router.get("/{staff_id}/goals", response_model=list[PerformanceGoalRead])
def list_employee_goals(
    staff_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    if not context.is_platform_admin:
        require_tenant_roles(context, PERFORMANCE_ROLES)
    if not context.is_platform_admin:
        require_tenant_roles(context, PERFORMANCE_ROLES)
    staff = staff_or_404(db, staff_id)
    assert_employee_scope(context, staff)
    if not staff.employee_profile:
        return []
    return (
        db.query(PerformanceGoal)
        .filter(PerformanceGoal.employee_id == staff.employee_profile.id)
        .order_by(PerformanceGoal.period_end.desc())
        .all()
    )


@router.post("/{staff_id}/goals", response_model=PerformanceGoalRead, status_code=status.HTTP_201_CREATED)
def create_employee_goal(
    staff_id: UUID,
    payload: PerformanceGoalCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, PERFORMANCE_ROLES)
    staff = staff_or_404(db, staff_id)
    assert_employee_scope(context, staff)
    if not staff.employee_profile:
        raise HTTPException(status_code=409, detail="Create the employee profile before assigning goals")

    goal = PerformanceGoal(
        employee_id=staff.employee_profile.id,
        company_id=staff.company_id,
        branch_id=staff.branch_id,
        created_by_user_id=context.user.id,
        **payload.model_dump(),
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/goals/{goal_id}", response_model=PerformanceGoalRead)
def update_goal(
    goal_id: UUID,
    payload: PerformanceGoalUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, PERFORMANCE_ROLES)
    goal = db.query(PerformanceGoal).filter(PerformanceGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Performance goal not found")
    if not context.is_platform_admin and goal.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company goal access is not allowed")
    assert_branch_scope(context, goal.branch_id)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(goal, field, value)

    if goal.current_value >= goal.target_value and goal.status == "active":
        goal.status = "completed"
        goal.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(goal)
    return goal


@router.get("/{staff_id}/reviews", response_model=list[PerformanceReviewRead])
def list_employee_reviews(
    staff_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    staff = staff_or_404(db, staff_id)
    assert_employee_scope(context, staff)
    if not staff.employee_profile:
        return []
    return (
        db.query(PerformanceReview)
        .filter(PerformanceReview.employee_id == staff.employee_profile.id)
        .order_by(PerformanceReview.period_end.desc())
        .all()
    )


@router.post("/{staff_id}/reviews", response_model=PerformanceReviewRead, status_code=status.HTTP_201_CREATED)
def create_employee_review(
    staff_id: UUID,
    payload: PerformanceReviewCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, PERFORMANCE_ROLES)
    staff = staff_or_404(db, staff_id)
    assert_employee_scope(context, staff)
    if not staff.employee_profile:
        raise HTTPException(status_code=409, detail="Create the employee profile before reviewing performance")

    review = PerformanceReview(
        employee_id=staff.employee_profile.id,
        reviewer_staff_id=context.staff.id if context.staff else None,
        company_id=staff.company_id,
        branch_id=staff.branch_id,
        **payload.model_dump(),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
