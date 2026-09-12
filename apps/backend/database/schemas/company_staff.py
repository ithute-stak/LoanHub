from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from database.models.enums import Gender, MaritalStatus, UserRole
from database.schemas.person_schema import PersonRead


class StaffUserRead(BaseModel):
    id: UUID
    email: Optional[EmailStr] = None
    phone: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    person: Optional[PersonRead] = None

    model_config = {"from_attributes": True}


class CompanyStaffBase(BaseModel):
    user_id: UUID
    company_id: UUID
    branch_id: Optional[UUID] = None
    role: UserRole
    is_primary: bool = False
    is_active: bool = True


class CompanyStaffCreate(CompanyStaffBase):
    pass


class CompanyStaffAccountCreate(BaseModel):
    email: Optional[EmailStr] = None
    phone: str = Field(min_length=8, max_length=30)
    password: str = Field(min_length=8, max_length=128)

    first_name: str = Field(min_length=1, max_length=100)
    middle_name: Optional[str] = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None
    national_id: Optional[str] = Field(default=None, max_length=50)
    passport_number: Optional[str] = Field(default=None, max_length=50)
    marital_status: Optional[MaritalStatus] = None
    nationality: Optional[str] = "Mosotho"
    district: Optional[str] = None
    town_or_village: Optional[str] = None
    physical_address: Optional[str] = None

    branch_id: Optional[UUID] = None
    role: UserRole
    is_primary: bool = True
    is_active: bool = True

    @model_validator(mode="after")
    def validate_role_scope(self):
        company_wide = {
            UserRole.COMPANY_OWNER,
            UserRole.COMPANY_ADMIN,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.AUDITOR,
            UserRole.RISK_MANAGER,
            UserRole.HR_MANAGER,
            UserRole.PERFORMANCE_MANAGER,
            UserRole.IT_SUPPORT,
            UserRole.AML_CFT_OFFICER,
            UserRole.TREASURY_OFFICER,
            UserRole.DATA_PROTECTION_OFFICER,
            UserRole.REGULATORY_REPORTING_OFFICER,
            UserRole.INFORMATION_SECURITY_OFFICER,
        }
        if self.role not in company_wide and self.branch_id is None:
            raise ValueError("A branch must be selected for this staff role")
        return self


class CompanyStaffUserStatusUpdate(BaseModel):
    is_active: bool


class CompanyStaffUpdate(BaseModel):
    branch_id: Optional[UUID] = None
    role: Optional[UserRole] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None


class CompanyStaffRead(CompanyStaffBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    user: StaffUserRead

    model_config = {"from_attributes": True}
