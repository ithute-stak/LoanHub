from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.access_control import (
    BRANCH_MANAGEMENT_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    assert_branch_scope,
    assert_company_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.branch import CompanyBranch
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.schemas.branch import CompanyBranchCreate, CompanyBranchRead, CompanyBranchUpdate
from database.session import get_db
from services.billing_service import enforce_company_limit


router = APIRouter(prefix="/branches", tags=["Company Branches"])


def branch_or_404(db: Session, branch_id: UUID) -> CompanyBranch:
    branch = db.query(CompanyBranch).filter(CompanyBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


def company_exists(db: Session, company_id: UUID) -> bool:
    return db.query(LoanCompany.id).filter(LoanCompany.id == company_id).first() is not None


@router.get("/", response_model=list[CompanyBranchRead])
def list_branches(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    query = db.query(CompanyBranch)
    if not context.is_platform_admin:
        query = query.filter(CompanyBranch.company_id == context.company_id)
        if context.staff and context.staff.role == UserRole.BRANCH_MANAGER:
            query = query.filter(CompanyBranch.id == context.branch_id)
    return query.order_by(CompanyBranch.name.asc()).offset(skip).limit(limit).all()


@router.get("/company/{company_id}", response_model=list[CompanyBranchRead])
def list_company_branches(
    company_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    assert_company_scope(context, company_id)
    query = db.query(CompanyBranch).filter(CompanyBranch.company_id == company_id)
    if context.staff and context.staff.role == UserRole.BRANCH_MANAGER:
        query = query.filter(CompanyBranch.id == context.branch_id)
    return query.order_by(CompanyBranch.name.asc()).offset(skip).limit(limit).all()


@router.get("/{branch_id}", response_model=CompanyBranchRead)
def get_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    branch = branch_or_404(db, branch_id)
    assert_company_scope(context, branch.company_id)
    assert_branch_scope(context, branch.id)
    return branch


@router.post("/", response_model=CompanyBranchRead, status_code=status.HTTP_201_CREATED)
def create_branch(
    payload: CompanyBranchCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    company_id = payload.company_id if context.is_platform_admin else context.company_id
    if not company_id or not company_exists(db, company_id):
        raise HTTPException(status_code=404, detail="Company not found")

    enforce_company_limit(
        db,
        company_id=company_id,
        resource="branches",
        current_count=db.query(CompanyBranch).filter(CompanyBranch.company_id == company_id).count(),
        fallback=1,
    )

    duplicate = (
        db.query(CompanyBranch)
        .filter(
            CompanyBranch.company_id == company_id,
            CompanyBranch.name == payload.name.strip(),
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A branch with this name already exists")

    data = payload.model_dump()
    data["company_id"] = company_id
    branch = CompanyBranch(**data)
    db.add(branch)
    db.flush()
    if branch.is_headquarters:
        db.query(CompanyBranch).filter(
            CompanyBranch.company_id == company_id,
            CompanyBranch.id != branch.id,
        ).update({CompanyBranch.is_headquarters: False}, synchronize_session=False)
        from services.treasury_service import get_or_create_settings
        settings = get_or_create_settings(db, company_id)
        settings.headquarters_branch_id = branch.id
    db.commit()
    db.refresh(branch)
    return branch


@router.put("/{branch_id}", response_model=CompanyBranchRead)
def update_branch(
    branch_id: UUID,
    payload: CompanyBranchUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    branch = branch_or_404(db, branch_id)
    assert_company_scope(context, branch.company_id)
    assert_branch_scope(context, branch.id)
    require_tenant_roles(context, BRANCH_MANAGEMENT_ROLES)

    changes = payload.model_dump(exclude_unset=True)
    if not context.is_platform_admin:
        changes.pop("company_id", None)
    elif changes.get("company_id") and not company_exists(db, changes["company_id"]):
        raise HTTPException(status_code=404, detail="Company not found")

    for field, value in changes.items():
        setattr(branch, field, value)
    if changes.get("is_headquarters") is True:
        db.query(CompanyBranch).filter(
            CompanyBranch.company_id == branch.company_id,
            CompanyBranch.id != branch.id,
        ).update({CompanyBranch.is_headquarters: False}, synchronize_session=False)
        from services.treasury_service import get_or_create_settings
        settings = get_or_create_settings(db, branch.company_id)
        settings.headquarters_branch_id = branch.id
    elif changes.get("is_headquarters") is False:
        from services.treasury_service import get_or_create_settings
        settings = get_or_create_settings(db, branch.company_id)
        if settings.headquarters_branch_id == branch.id:
            settings.headquarters_branch_id = None
    db.commit()
    db.refresh(branch)
    return branch


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    branch = branch_or_404(db, branch_id)
    assert_company_scope(context, branch.company_id)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)

    assigned_staff = (
        db.query(CompanyStaff.id)
        .filter(CompanyStaff.branch_id == branch.id, CompanyStaff.is_active.is_(True))
        .first()
    )
    if assigned_staff:
        raise HTTPException(
            status_code=409,
            detail="Move or deactivate assigned staff before deleting this branch",
        )

    db.delete(branch)
    db.commit()


@router.patch("/{branch_id}/activate", response_model=CompanyBranchRead)
def activate_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    branch = branch_or_404(db, branch_id)
    assert_company_scope(context, branch.company_id)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    branch.is_active = True
    db.commit()
    db.refresh(branch)
    return branch


@router.patch("/{branch_id}/deactivate", response_model=CompanyBranchRead)
def deactivate_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    branch = branch_or_404(db, branch_id)
    assert_company_scope(context, branch.company_id)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if branch.is_headquarters:
        raise HTTPException(status_code=409, detail="Choose another headquarters branch before deactivating this branch")
    branch.is_active = False
    db.commit()
    db.refresh(branch)
    return branch
