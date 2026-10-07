from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


CompanyModule = Literal[
    "crm", "credit_committee", "collateral", "legal_recovery", "complaints",
    "communications", "marketing", "agents", "employer_partnerships",
    "procurement", "assets", "internal_audit", "budgeting", "targets",
    "business_continuity", "integrations", "document_automation", "board_packs",
]


class OperatingRecordCreate(BaseModel):
    module: CompanyModule
    record_type: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    status: str = Field(default="open", min_length=2, max_length=40)
    priority: str = Field(default="normal", min_length=2, max_length=30)
    branch_id: UUID | None = None
    borrower_id: UUID | None = None
    loan_id: UUID | None = None
    assigned_user_id: UUID | None = None
    counterparty_name: str | None = Field(default=None, max_length=240)
    amount: Decimal | None = None
    currency: str = Field(default="LSL", min_length=3, max_length=3)
    due_at: datetime | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=30)


class OperatingRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, min_length=2, max_length=40)
    priority: str | None = Field(default=None, min_length=2, max_length=30)
    assigned_user_id: UUID | None = None
    counterparty_name: str | None = Field(default=None, max_length=240)
    amount: Decimal | None = None
    due_at: datetime | None = None
    data: dict[str, Any] | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    is_archived: bool | None = None


class OperatingRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    branch_id: UUID | None
    module: str
    record_type: str
    reference: str
    title: str
    description: str | None
    status: str
    priority: str
    borrower_id: UUID | None
    loan_id: UUID | None
    assigned_user_id: UUID | None
    counterparty_name: str | None
    amount: Decimal | None
    currency: str
    due_at: datetime | None
    data: dict[str, Any]
    tags: list[str]
    is_archived: bool
    created_at: datetime
    updated_at: datetime



class ManagementActionCreate(BaseModel):
    source_signal_id: str = Field(min_length=2, max_length=160)
    source: str = Field(default="management_command_intelligence", min_length=2, max_length=80)
    domain: str = Field(min_length=2, max_length=80)
    severity: Literal["low", "medium", "high", "critical"]
    title: str = Field(min_length=3, max_length=240)
    why_now: str = Field(min_length=3, max_length=3000)
    recommended_action: str = Field(min_length=3, max_length=3000)
    action_url: str = Field(min_length=1, max_length=500)
    evidence: dict[str, Any] = Field(default_factory=dict)
    branch_id: UUID | None = None
    assigned_user_id: UUID
    due_at: datetime


class ManagementDecisionCreate(BaseModel):
    decision: str = Field(min_length=2, max_length=120)
    note: str = Field(min_length=3, max_length=4000)
    evidence_references: list[str] = Field(default_factory=list, max_length=30)


class ManagementResolutionCreate(BaseModel):
    resolution: str = Field(min_length=3, max_length=4000)
    evidence_references: list[str] = Field(default_factory=list, max_length=30)


class ManagementVerificationCreate(BaseModel):
    outcome: Literal["verified", "reopened"]
    note: str = Field(min_length=3, max_length=4000)
    evidence_references: list[str] = Field(default_factory=list, max_length=30)

class APIKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    scopes: list[str] = Field(default_factory=lambda: ["read:portfolio"], max_length=30)
    allowed_ips: list[str] = Field(default_factory=list, max_length=30)
    expires_at: datetime | None = None


class APIKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    allowed_ips: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class APIKeyIssued(APIKeyRead):
    api_key: str


class WebhookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    endpoint_url: HttpUrl
    event_types: list[str] = Field(default_factory=lambda: ["loan.updated", "payment.succeeded"], max_length=30)


class WebhookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    endpoint_url: str
    secret_prefix: str
    event_types: list[str]
    is_active: bool
    failure_count: int
    last_delivery_at: datetime | None
    created_at: datetime


class WebhookIssued(WebhookRead):
    signing_secret: str


class PricingSimulationRequest(BaseModel):
    principal: Decimal = Field(gt=0)
    rate_percent: Decimal = Field(ge=0)
    term_months: int = Field(ge=1, le=120)
    processing_fee: Decimal = Field(default=Decimal("0"), ge=0)
    interest_method: str = "micro_loan"


class CompanyAssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
