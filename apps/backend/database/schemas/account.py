from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from database.models.enums import Gender, MaritalStatus, UserRole
from database.schemas.auth import AuthUserRead


class AccountMembershipRead(BaseModel):
    id: UUID
    company_id: UUID
    company_name: str
    branch_id: UUID | None = None
    branch_name: str | None = None
    role: UserRole
    is_primary: bool
    is_active: bool


class AccountSecurityRead(BaseModel):
    active_sessions: int
    last_seen_at: datetime | None = None
    account_created_at: datetime
    account_updated_at: datetime
    is_active: bool
    is_verified: bool
    is_impersonated: bool = False
    can_manage_security: bool = True


class AccountOverviewRead(BaseModel):
    user: AuthUserRead
    memberships: list[AccountMembershipRead] = Field(default_factory=list)
    security: AccountSecurityRead


class AccountContactUpdate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=30)
    current_password: str = Field(min_length=6, max_length=128)


class AccountPersonUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    gender: Gender | None = None
    date_of_birth: date | None = None
    national_id: str | None = Field(default=None, max_length=50)
    passport_number: str | None = Field(default=None, max_length=50)
    marital_status: MaritalStatus | None = None
    nationality: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    town_or_village: str | None = Field(default=None, max_length=150)
    physical_address: str | None = Field(default=None, max_length=1000)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)
    confirm_password: str = Field(min_length=10, max_length=128)


class ChangePasswordResponse(BaseModel):
    message: str
    requires_reauthentication: bool = True


class AccountSessionRead(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    is_current: bool
    is_active: bool
    status: str


class AccountSessionActionResponse(BaseModel):
    message: str
    revoked_count: int = 0


class AccountActivityRead(BaseModel):
    id: UUID
    action: str
    description: str | None = None
    status: str
    severity: str
    ip_address: str | None = None
    user_agent: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    event_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
