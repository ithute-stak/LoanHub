from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from database.models.enums import UserRole


PLATFORM_EMPLOYEE_ROLES = {
    UserRole.PLATFORM_ADMIN,
    UserRole.PLATFORM_FINANCE,
    UserRole.PLATFORM_SUPPORT,
    UserRole.PLATFORM_AUDITOR,
    UserRole.PLATFORM_OPERATIONS,
    UserRole.PLATFORM_COMPLIANCE,
}


class PlatformStaffAccountCreate(BaseModel):
    email: EmailStr | None = None
    phone: str = Field(min_length=8, max_length=30)
    password: str = Field(min_length=10, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: UserRole
    job_title: str = Field(min_length=2, max_length=160)
    department: str | None = Field(default=None, max_length=120)
    permissions: list[str] = Field(default_factory=list)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_platform_role(self):
        if self.role not in PLATFORM_EMPLOYEE_ROLES:
            raise ValueError("Select a platform staff role")
        return self


class PlatformStaffAccountUpdate(BaseModel):
    email: EmailStr | None = None
    phone: str = Field(min_length=8, max_length=30)
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: UserRole
    job_title: str = Field(min_length=2, max_length=160)
    department: str | None = Field(default=None, max_length=120)
    permissions: list[str] = Field(default_factory=list)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_platform_role(self):
        if self.role not in PLATFORM_EMPLOYEE_ROLES:
            raise ValueError("Select a platform staff role")
        return self


class PlatformStaffAccountRead(BaseModel):
    id: UUID
    user_id: UUID
    email: EmailStr | None
    phone: str
    first_name: str
    middle_name: str | None
    last_name: str
    full_name: str
    role: UserRole
    job_title: str
    department: str | None
    permissions: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
