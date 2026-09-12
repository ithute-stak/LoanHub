from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from database.config.config import settings
from database.models.enums import (
    BillingCycle,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
    SubscriptionStatus,
    UnlockStatus,
)
from database.models.marketplace_access import MarketplaceUnlock
from database.models.payment import PaymentTransaction
from database.models.subscription import CompanySubscription, SubscriptionPlan
from services.payment_service import build_idempotency_key, initiate_payment


def active_subscription(
    db: Session,
    company_id: UUID,
) -> CompanySubscription | None:
    today = date.today()
    return (
        db.query(CompanySubscription)
        .options(joinedload(CompanySubscription.plan))
        .filter(
            CompanySubscription.company_id == company_id,
            CompanySubscription.status == SubscriptionStatus.ACTIVE,
            CompanySubscription.start_date <= today,
            CompanySubscription.end_date >= today,
        )
        .order_by(CompanySubscription.end_date.desc())
        .first()
    )


def subscription_includes_marketplace_access(
    subscription: CompanySubscription | None,
) -> bool:
    if not subscription or not subscription.plan:
        return False
    features = subscription.plan.features or {}
    return bool(features.get("marketplace_full_access", False))


def unlock_price(
    db: Session,
    company_id: UUID,
) -> Decimal:
    subscription = active_subscription(db, company_id)
    if subscription and subscription.plan:
        return Decimal(subscription.plan.marketplace_unlock_fee or 0)
    return Decimal(str(settings.MARKETPLACE_DEFAULT_UNLOCK_FEE))


def company_has_request_access(
    db: Session,
    *,
    company_id: UUID,
    loan_request_id: UUID,
) -> bool:
    subscription = active_subscription(db, company_id)
    if subscription_includes_marketplace_access(subscription):
        return True

    unlock = (
        db.query(MarketplaceUnlock)
        .filter(
            MarketplaceUnlock.company_id == company_id,
            MarketplaceUnlock.loan_request_id == loan_request_id,
            MarketplaceUnlock.status == UnlockStatus.UNLOCKED,
        )
        .first()
    )
    if not unlock:
        return False
    if unlock.expires_at and unlock.expires_at < datetime.now(timezone.utc):
        return False
    return True


def _subscription_amount(plan: SubscriptionPlan, cycle: BillingCycle) -> Decimal:
    if cycle == BillingCycle.MONTHLY:
        return Decimal(plan.monthly_price or 0)
    if cycle == BillingCycle.ANNUAL:
        return Decimal(plan.annual_price or 0)
    return Decimal("0")


def _subscription_end(start: date, cycle: BillingCycle) -> date:
    if cycle == BillingCycle.ANNUAL:
        return start + timedelta(days=365)
    if cycle == BillingCycle.MONTHLY:
        return start + timedelta(days=30)
    return start + timedelta(days=3650)


def _cancel_other_active_subscriptions(
    db: Session,
    *,
    company_id: UUID,
    keep_subscription_id: UUID,
) -> None:
    """Cancel older subscriptions through ORM mutations.

    Using mapped objects instead of a bulk UPDATE ensures the transparency
    listeners capture every subscription status change.
    """

    subscriptions = (
        db.query(CompanySubscription)
        .filter(
            CompanySubscription.company_id == company_id,
            CompanySubscription.id != keep_subscription_id,
            CompanySubscription.status == SubscriptionStatus.ACTIVE,
        )
        .with_for_update()
        .all()
    )

    for subscription in subscriptions:
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.auto_renew = False


def checkout_subscription(
    db: Session,
    *,
    company_id: UUID,
    plan: SubscriptionPlan,
    billing_cycle: BillingCycle,
    provider: PaymentProvider,
    payer_phone: str | None,
    auto_renew: bool,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
    initiated_by_user_id: UUID,
) -> tuple[CompanySubscription, PaymentTransaction | None]:
    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This subscription plan is inactive",
        )

    amount = max(
        _subscription_amount(plan, billing_cycle),
        Decimal("0"),
    )
    if billing_cycle == BillingCycle.PAY_PER_TRANSACTION:
        amount = Decimal("0")

    start = date.today()
    subscription = CompanySubscription(
        company_id=company_id,
        plan_id=plan.id,
        plan_name=plan.name,
        amount=amount,
        start_date=start,
        end_date=_subscription_end(start, billing_cycle),
        billing_cycle=billing_cycle,
        status=SubscriptionStatus.PENDING,
        auto_renew=auto_renew,
        payment_provider=None,
        external_reference=None,
    )

    if amount <= Decimal("0"):
        subscription.status = SubscriptionStatus.ACTIVE
        db.add(subscription)
        db.flush()

        _cancel_other_active_subscriptions(
            db,
            company_id=company_id,
            keep_subscription_id=subscription.id,
        )

        db.commit()
        db.refresh(subscription)
        return subscription, None

    payment = initiate_payment(
        db,
        provider=provider,
        purpose=PaymentPurpose.SUBSCRIPTION,
        amount=amount,
        idempotency_key=build_idempotency_key(
            "subscription",
            company_id,
            plan.id,
            billing_cycle.value,
            uuid4().hex,
        ),
        initiated_by_user_id=initiated_by_user_id,
        company_id=company_id,
        payer_phone=payer_phone,
        payment_method=payment_method,
        proof_reference=proof_reference,
        proof_url=proof_url,
        proof_notes=proof_notes,
    )

    subscription.payment_provider = payment.provider
    subscription.external_reference = payment.provider_reference
    subscription.status = (
        SubscriptionStatus.ACTIVE
        if payment.status == PaymentStatus.SUCCEEDED
        else SubscriptionStatus.PENDING
    )
    db.add(subscription)
    db.flush()

    if subscription.status == SubscriptionStatus.ACTIVE:
        _cancel_other_active_subscriptions(
            db,
            company_id=company_id,
            keep_subscription_id=subscription.id,
        )

    db.commit()
    db.refresh(subscription)
    return subscription, payment


def unlock_marketplace_request(
    db: Session,
    *,
    company_id: UUID,
    loan_request_id: UUID,
    provider: PaymentProvider,
    payer_phone: str | None,
    initiated_by_user_id: UUID,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
) -> tuple[MarketplaceUnlock, PaymentTransaction | None]:
    existing = (
        db.query(MarketplaceUnlock)
        .filter(
            MarketplaceUnlock.company_id == company_id,
            MarketplaceUnlock.loan_request_id == loan_request_id,
        )
        .first()
    )
    if existing and existing.status == UnlockStatus.UNLOCKED:
        return existing, existing.payment_transaction
    if existing and existing.status == UnlockStatus.PENDING and existing.payment_transaction:
        return existing, existing.payment_transaction

    subscription = active_subscription(db, company_id)
    included = subscription_includes_marketplace_access(subscription)
    price = Decimal("0") if included else unlock_price(db, company_id)

    if included or price <= 0:
        unlock = existing or MarketplaceUnlock(
            company_id=company_id,
            loan_request_id=loan_request_id,
            unlocked_by_user_id=initiated_by_user_id,
            price_paid=0,
        )
        unlock.status = UnlockStatus.UNLOCKED
        unlock.unlocked_at = datetime.now(timezone.utc)
        unlock.expires_at = None
        db.add(unlock)
        db.commit()
        db.refresh(unlock)
        return unlock, None

    payment = initiate_payment(
        db,
        provider=provider,
        purpose=PaymentPurpose.MARKETPLACE_UNLOCK,
        amount=price,
        idempotency_key=(
            f"unlock:{company_id}:{loan_request_id}"
            if existing is None
            else f"unlock:{company_id}:{loan_request_id}:{uuid4().hex}"
        ),
        initiated_by_user_id=initiated_by_user_id,
        company_id=company_id,
        loan_request_id=loan_request_id,
        payer_phone=payer_phone,
        payment_method=payment_method,
        proof_reference=proof_reference,
        proof_url=proof_url,
        proof_notes=proof_notes,
    )

    unlock = existing or MarketplaceUnlock(
        company_id=company_id,
        loan_request_id=loan_request_id,
        unlocked_by_user_id=initiated_by_user_id,
        price_paid=price,
    )
    unlock.payment_transaction_id = payment.id
    unlock.status = (
        UnlockStatus.UNLOCKED
        if payment.status == PaymentStatus.SUCCEEDED
        else UnlockStatus.PENDING
    )
    if unlock.status == UnlockStatus.UNLOCKED:
        unlock.unlocked_at = datetime.now(timezone.utc)

    db.add(unlock)
    db.commit()
    db.refresh(unlock)
    return unlock, payment


def finalize_billing_payment(
    db: Session,
    payment: PaymentTransaction,
) -> None:
    if payment.status != PaymentStatus.SUCCEEDED:
        return

    if payment.purpose == PaymentPurpose.MARKETPLACE_UNLOCK:
        unlock = (
            db.query(MarketplaceUnlock)
            .filter(MarketplaceUnlock.payment_transaction_id == payment.id)
            .first()
        )
        if unlock:
            unlock.status = UnlockStatus.UNLOCKED
            unlock.unlocked_at = datetime.now(timezone.utc)

    if payment.purpose == PaymentPurpose.SUBSCRIPTION:
        subscription = (
            db.query(CompanySubscription)
            .filter(CompanySubscription.external_reference == payment.provider_reference)
            .first()
        )
        if subscription:
            _cancel_other_active_subscriptions(
                db,
                company_id=subscription.company_id,
                keep_subscription_id=subscription.id,
            )
            subscription.status = SubscriptionStatus.ACTIVE

    db.commit()


def get_plan_or_404(db: Session, plan_id: UUID) -> SubscriptionPlan:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


def company_plan_limit(
    db: Session,
    *,
    company_id: UUID,
    resource: str,
    fallback: int,
) -> int:
    """Return the configured tenant limit without breaking core lending setup.

    Older installations may have the loan-product table before the optional
    subscription tables. Product creation must still work in that state, using
    the conservative fallback limit, while Alembic is brought to the latest
    revision. Once the billing tables exist, the active plan is authoritative.
    """
    bind = db.get_bind()
    inspector = sa_inspect(bind)
    if not (
        inspector.has_table("company_subscriptions")
        and inspector.has_table("subscription_plans")
    ):
        return fallback

    try:
        # Isolate optional billing lookups in a savepoint. A partially upgraded
        # billing schema must not abort the loan-product transaction.
        with db.begin_nested():
            subscription = active_subscription(db, company_id)
            plan = subscription.plan if subscription and subscription.plan else None
            if plan is None:
                plan = (
                    db.query(SubscriptionPlan)
                    .filter(
                        SubscriptionPlan.code == "STARTER",
                        SubscriptionPlan.is_active.is_(True),
                    )
                    .first()
                )
    except SQLAlchemyError:
        return fallback
    if not plan:
        return fallback
    value = (plan.limits or {}).get(resource, fallback)
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def enforce_company_limit(
    db: Session,
    *,
    company_id: UUID,
    resource: str,
    current_count: int,
    fallback: int,
) -> None:
    limit = company_plan_limit(
        db,
        company_id=company_id,
        resource=resource,
        fallback=fallback,
    )
    if limit >= 0 and current_count >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Your current subscription allows {limit} {resource}. "
                "Upgrade the company plan to add more."
            ),
        )
