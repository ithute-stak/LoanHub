from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_tenant_context,
    require_platform_admin,
    require_tenant_roles,
)
from database.models.enums import PaymentProvider, SubscriptionStatus
from database.models.subscription import CompanySubscription, SubscriptionPlan
from database.models.user import User
from database.schemas.billing import (
    CompanySubscriptionRead,
    SubscriptionCheckoutCreate,
    SubscriptionCheckoutRead,
    SubscriptionPlanCreate,
    SubscriptionPlanRead,
    SubscriptionPlanUpdate,
)
from database.schemas.payment import PaymentTransactionRead
from database.session import get_db
from services.billing_service import checkout_subscription, get_plan_or_404


router = APIRouter(prefix="/billing", tags=["Billing and Subscriptions"])


@router.get("/plans", response_model=list[SubscriptionPlanRead])
def list_public_plans(db: Session = Depends(get_db)):
    """Return active public plans visible to loan companies."""
    return (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.is_active.is_(True),
            SubscriptionPlan.is_public.is_(True),
        )
        .order_by(SubscriptionPlan.monthly_price.asc(), SubscriptionPlan.name.asc())
        .all()
    )


@router.get("/plans/admin", response_model=list[SubscriptionPlanRead])
def list_all_plans_for_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    """Return every pricing plan, including private and inactive plans."""
    return (
        db.query(SubscriptionPlan)
        .order_by(SubscriptionPlan.monthly_price.asc(), SubscriptionPlan.name.asc())
        .all()
    )


@router.post("/plans", response_model=SubscriptionPlanRead, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    normalized_code = payload.code.upper()
    existing = (
        db.query(SubscriptionPlan)
        .filter(func.upper(SubscriptionPlan.code) == normalized_code)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Plan code already exists")

    plan_data = payload.model_dump()
    plan_data["features"] = payload.features.model_dump()
    plan_data["limits"] = payload.limits.model_dump()
    plan = SubscriptionPlan(**plan_data)

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanRead)
def update_plan(
    plan_id: UUID,
    payload: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    plan = get_plan_or_404(db, plan_id)
    update_data = payload.model_dump(exclude_unset=True)

    if plan.code == "STARTER" and update_data.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The STARTER fallback plan cannot be deactivated",
        )

    if payload.features is not None:
        update_data["features"] = payload.features.model_dump()
    if payload.limits is not None:
        update_data["limits"] = payload.limits.model_dump()

    for field, value in update_data.items():
        setattr(plan, field, value)

    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    plan = get_plan_or_404(db, plan_id)

    if plan.code == "STARTER":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The STARTER fallback plan cannot be deleted",
        )

    subscription_count = (
        db.query(func.count(CompanySubscription.id))
        .filter(CompanySubscription.plan_id == plan.id)
        .scalar()
        or 0
    )
    if subscription_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This plan is referenced by {subscription_count} subscription record(s). "
                "Make it inactive and private instead of deleting it."
            ),
        )

    db.delete(plan)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/subscriptions", response_model=list[CompanySubscriptionRead])
def list_subscriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    query = db.query(CompanySubscription).options(joinedload(CompanySubscription.plan))
    if not context.is_platform_admin:
        query = query.filter(CompanySubscription.company_id == context.company_id)
    return query.order_by(CompanySubscription.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/subscriptions/current", response_model=CompanySubscriptionRead | None)
def current_subscription(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    if context.is_platform_admin:
        raise HTTPException(status_code=400, detail="Select a company subscription from the platform list")
    return (
        db.query(CompanySubscription)
        .options(joinedload(CompanySubscription.plan))
        .filter(
            CompanySubscription.company_id == context.company_id,
            CompanySubscription.status == SubscriptionStatus.ACTIVE,
            CompanySubscription.start_date <= date.today(),
            CompanySubscription.end_date >= date.today(),
        )
        .order_by(CompanySubscription.end_date.desc())
        .first()
    )


@router.post("/subscriptions/checkout", response_model=SubscriptionCheckoutRead)
def subscription_checkout(
    payload: SubscriptionCheckoutCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=400, detail="A company context is required")

    plan = get_plan_or_404(db, payload.plan_id)
    if not plan.is_active or not plan.is_public:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This subscription plan is not currently available for checkout",
        )

    subscription, payment = checkout_subscription(
        db,
        company_id=context.company_id,
        plan=plan,
        billing_cycle=payload.billing_cycle,
        provider=payload.provider or (PaymentProvider.CASH if payload.payment_method.value == "cash" else PaymentProvider.MANUAL),
        payer_phone=payload.payer_phone,
        auto_renew=payload.auto_renew,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes,
        initiated_by_user_id=context.user.id,
    )
    return {
        "subscription": CompanySubscriptionRead.model_validate(subscription),
        "payment": (
            PaymentTransactionRead.model_validate(payment)
            if payment
            else None
        ),
    }


@router.post("/subscriptions/{subscription_id}/cancel", response_model=CompanySubscriptionRead)
def cancel_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    subscription = (
        db.query(CompanySubscription)
        .options(joinedload(CompanySubscription.plan))
        .filter(CompanySubscription.id == subscription_id)
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if not context.is_platform_admin and subscription.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.auto_renew = False
    db.commit()
    db.refresh(subscription)
    return subscription
