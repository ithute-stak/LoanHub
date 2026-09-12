from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from database.models.enums import BillingCycle, PaymentMethod, PaymentProvider, SubscriptionStatus, UnlockStatus
from database.schemas.payment import PaymentTransactionRead


class SubscriptionPlanFeatures(BaseModel):
    """Known feature switches stored in the plan's JSON feature document.

    Extra keys are intentionally allowed so the platform owner can introduce
    new feature flags without requiring an immediate database migration.
    """

    marketplace_full_access: bool = False
    advanced_analytics: bool = False
    custom_branding: bool = False
    api_access: bool = False
    priority_support: bool = False
    audit_exports: bool = False

    model_config = ConfigDict(extra="allow")


class SubscriptionPlanLimits(BaseModel):
    """Tenant resource limits.

    A value of -1 means unlimited. Zero means the resource is disabled.
    Extra keys are allowed for future resources.
    """

    branches: int = Field(default=1, ge=-1)
    staff: int = Field(default=5, ge=-1)
    products: int = Field(default=3, ge=-1)

    model_config = ConfigDict(extra="allow")


class SubscriptionPlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=60, pattern=r"^[A-Z][A-Z0-9_]*$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    monthly_price: Decimal = Field(default=Decimal("0"), ge=0)
    annual_price: Decimal = Field(default=Decimal("0"), ge=0)
    marketplace_unlock_fee: Decimal = Field(default=Decimal("0"), ge=0)
    transaction_fee_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    features: SubscriptionPlanFeatures = Field(default_factory=SubscriptionPlanFeatures)
    limits: SubscriptionPlanLimits = Field(default_factory=SubscriptionPlanLimits)
    is_active: bool = True
    is_public: bool = True

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: Any) -> str:
        return str(value or "").strip().upper().replace(" ", "_")

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    monthly_price: Decimal | None = Field(default=None, ge=0)
    annual_price: Decimal | None = Field(default=None, ge=0)
    marketplace_unlock_fee: Decimal | None = Field(default=None, ge=0)
    transaction_fee_percent: Decimal | None = Field(default=None, ge=0, le=100)
    features: SubscriptionPlanFeatures | None = None
    limits: SubscriptionPlanLimits | None = None
    is_active: bool | None = None
    is_public: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class SubscriptionPlanRead(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    monthly_price: Decimal
    annual_price: Decimal
    marketplace_unlock_fee: Decimal
    transaction_fee_percent: Decimal
    features: SubscriptionPlanFeatures
    limits: SubscriptionPlanLimits
    is_active: bool
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionCheckoutCreate(BaseModel):
    plan_id: UUID
    billing_cycle: BillingCycle
    payment_method: PaymentMethod = PaymentMethod.CASH
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    # Retained for old clients. The active payment method controls posting.
    provider: PaymentProvider | None = None
    payer_phone: str | None = Field(default=None, max_length=30)
    auto_renew: bool = False


class CompanySubscriptionRead(BaseModel):
    id: UUID
    company_id: UUID
    plan_id: UUID | None
    plan_name: str
    amount: Decimal
    start_date: date
    end_date: date
    billing_cycle: BillingCycle
    status: SubscriptionStatus
    auto_renew: bool
    payment_provider: PaymentProvider | None
    external_reference: str | None
    created_at: datetime
    updated_at: datetime
    plan: SubscriptionPlanRead | None = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionCheckoutRead(BaseModel):
    subscription: CompanySubscriptionRead
    payment: PaymentTransactionRead | None = None


class MarketplaceUnlockCreate(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.CASH
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    provider: PaymentProvider | None = None
    payer_phone: str | None = Field(default=None, max_length=30)


class MarketplaceUnlockRead(BaseModel):
    id: UUID
    company_id: UUID
    loan_request_id: UUID
    payment_transaction_id: UUID | None
    unlocked_by_user_id: UUID | None
    price_paid: Decimal
    status: UnlockStatus
    unlocked_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
