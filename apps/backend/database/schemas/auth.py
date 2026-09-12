from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from database.models.enums import UserRole
from database.schemas.person_schema import PersonRead


class LoginRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=30)
    password: str = Field(min_length=6, max_length=128)
    otp: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)
    device_name: str | None = Field(default=None, max_length=160)


class MFAConfirmRequest(BaseModel):
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MFADisableRequest(BaseModel):
    password: str = Field(min_length=6, max_length=128)
    otp: str | None = Field(default=None, min_length=6, max_length=6)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class MFAEnrollmentResponse(BaseModel):
    otpauth_uri: str
    recovery_codes: list[str]
    message: str


class SessionRead(BaseModel):
    jti: str
    device_name: str | None = None
    user_agent: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime
    current: bool = False


class PasswordResetRequestCreate(BaseModel):
    identifier: str = Field(min_length=5, max_length=255)


class PasswordResetRequestResponse(BaseModel):
    message: str
    request_reference: str


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class AuthMembershipRead(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID | None
    role: UserRole
    is_primary: bool = False
    is_active: bool

    model_config = {"from_attributes": True}


class AuthUserRead(BaseModel):
    id: UUID
    email: Optional[EmailStr] = None
    phone: str
    role: UserRole
    is_active: bool
    is_verified: bool
    must_change_password: bool = False
    created_at: datetime
    person: PersonRead | None = None
    memberships: list[AuthMembershipRead] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserRead



class WebSocketSessionRequest(BaseModel):
    company_id: UUID | None = None
    client_id: str | None = Field(default=None, min_length=1, max_length=128)


class WebSocketSessionResponse(BaseModel):
    websocket_token: str
    expires_in: int


class ImpersonationRequest(BaseModel):
    target_user_id: UUID
    company_id: UUID | None = None
    reason: str = Field(min_length=5, max_length=500)
    duration_minutes: int = Field(default=20, ge=5, le=60)


class ImpersonationTargetRead(BaseModel):
    id: UUID
    display_name: str
    email: Optional[EmailStr] = None
    phone: str
    role: UserRole
    company_id: UUID | None = None
    company_name: str | None = None
    branch_id: UUID | None = None
    branch_name: str | None = None


class ImpersonationResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_at: datetime
    user: AuthUserRead
    original_admin: AuthUserRead
    company_id: UUID | None = None
    reason: str
