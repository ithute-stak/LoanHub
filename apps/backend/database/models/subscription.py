from sqlalchemy import Boolean, Column, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import BillingCycle, PaymentProvider, SubscriptionStatus


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    code = Column(String(60), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)

    monthly_price = Column(Numeric(12, 2), nullable=False, default=0)
    annual_price = Column(Numeric(12, 2), nullable=False, default=0)
    marketplace_unlock_fee = Column(Numeric(12, 2), nullable=False, default=0)
    transaction_fee_percent = Column(Numeric(6, 3), nullable=False, default=0)

    features = Column(JSONB, nullable=False, default=dict)
    limits = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    is_public = Column(Boolean, nullable=False, default=True)

    subscriptions = relationship("CompanySubscription", back_populates="plan")


class CompanySubscription(Base):
    __tablename__ = "company_subscriptions"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Retained for backward compatibility with the existing schema.
    plan_name = Column(String(100), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    billing_cycle = Column(
        Enum(BillingCycle),
        nullable=False,
        default=BillingCycle.MONTHLY,
    )
    status = Column(
        Enum(SubscriptionStatus),
        nullable=False,
        default=SubscriptionStatus.PENDING,
    )
    auto_renew = Column(Boolean, nullable=False, default=False)
    payment_provider = Column(Enum(PaymentProvider), nullable=True)
    external_reference = Column(String(160), nullable=True, unique=True)

    company = relationship("LoanCompany", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
