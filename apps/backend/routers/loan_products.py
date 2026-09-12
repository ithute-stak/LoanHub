from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    assert_company_scope,
    get_current_active_user,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.company import LoanCompany
from database.models.enums import CompanyStatus
from database.models.loan_product import LoanProduct
from database.models.user import User
from database.schemas.loan_product import LoanProductCreate, LoanProductRead, LoanProductUpdate
from database.session import get_db
from services.billing_service import enforce_company_limit


router = APIRouter(prefix="/loan-products", tags=["Loan Products"])


def product_or_404(db: Session, product_id: UUID) -> LoanProduct:
    product = db.query(LoanProduct).filter(LoanProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Loan product not found")
    return product


def validate_values(
    *,
    min_amount,
    max_amount,
    min_term_months: int,
    max_term_months: int,
) -> None:
    if max_amount < min_amount:
        raise HTTPException(status_code=400, detail="Maximum amount cannot be below minimum amount")
    if max_term_months < min_term_months:
        raise HTTPException(status_code=400, detail="Maximum term cannot be below minimum term")


@router.get("/public", response_model=list[LoanProductRead])
def list_public_products(
    company_id: UUID | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    query = (
        db.query(LoanProduct)
        .join(LoanCompany, LoanCompany.id == LoanProduct.company_id)
        .filter(
            LoanProduct.is_active.is_(True),
            LoanCompany.status == CompanyStatus.APPROVED,
            LoanCompany.is_active.is_(True),
        )
    )
    if company_id:
        query = query.filter(LoanProduct.company_id == company_id)
    return query.order_by(LoanProduct.name.asc()).offset(skip).limit(limit).all()


@router.get("/", response_model=list[LoanProductRead])
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    query = db.query(LoanProduct)
    if not context.is_platform_admin:
        query = query.filter(LoanProduct.company_id == context.company_id)
    return query.order_by(LoanProduct.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{product_id}", response_model=LoanProductRead)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    product = product_or_404(db, product_id)
    assert_company_scope(context, product.company_id)
    return product


@router.post("/", response_model=LoanProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: LoanProductCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    company_id = payload.company_id if context.is_platform_admin else context.company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="A company context is required")

    enforce_company_limit(
        db,
        company_id=company_id,
        resource="products",
        current_count=db.query(LoanProduct).filter(LoanProduct.company_id == company_id).count(),
        fallback=3,
    )

    duplicate = (
        db.query(LoanProduct)
        .filter(
            LoanProduct.company_id == company_id,
            LoanProduct.name.ilike(payload.name.strip()),
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A loan product with this name already exists")

    values = payload.model_dump(exclude={"company_id"})
    values["name"] = payload.name.strip()
    values["description"] = (payload.description or "").strip() or None
    validate_values(
        min_amount=values["min_amount"],
        max_amount=values["max_amount"],
        min_term_months=values["min_term_months"],
        max_term_months=values["max_term_months"],
    )

    product = LoanProduct(**values, company_id=company_id)
    try:
        db.add(product)
        db.commit()
        db.refresh(product)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The loan product conflicts with an existing company record",
        ) from exc
    return product


@router.put("/{product_id}", response_model=LoanProductRead)
def update_product(
    product_id: UUID,
    payload: LoanProductUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    product = product_or_404(db, product_id)
    assert_company_scope(context, product.company_id)

    changes = payload.model_dump(exclude_unset=True)
    min_amount = changes.get("min_amount", product.min_amount)
    max_amount = changes.get("max_amount", product.max_amount)
    min_term = changes.get("min_term_months", product.min_term_months)
    max_term = changes.get("max_term_months", product.max_term_months)
    validate_values(
        min_amount=min_amount,
        max_amount=max_amount,
        min_term_months=min_term,
        max_term_months=max_term,
    )

    if "name" in changes:
        changes["name"] = changes["name"].strip()
        duplicate = (
            db.query(LoanProduct)
            .filter(
                LoanProduct.company_id == product.company_id,
                LoanProduct.id != product.id,
                LoanProduct.name.ilike(changes["name"]),
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="A loan product with this name already exists")

    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/activate", response_model=LoanProductRead)
def activate_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    product = product_or_404(db, product_id)
    assert_company_scope(context, product.company_id)
    product.is_active = True
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}/deactivate", response_model=LoanProductRead)
def deactivate_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    product = product_or_404(db, product_id)
    assert_company_scope(context, product.company_id)
    product.is_active = False
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    product = product_or_404(db, product_id)
    assert_company_scope(context, product.company_id)
    db.delete(product)
    db.commit()
