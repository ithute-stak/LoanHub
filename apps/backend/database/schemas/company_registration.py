from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from database.models.enums import Gender, InstitutionType, MaritalStatus


class CompanyOwnerRegistrationCreate(BaseModel):
    institution_type: InstitutionType = InstitutionType.LOAN_COMPANY
    company_name: str = Field(min_length=2, max_length=200)
    registration_number: Optional[str] = Field(default=None, max_length=100)
    license_number: Optional[str] = Field(default=None, max_length=100)
    company_phone: str = Field(min_length=8, max_length=30)
    company_email: Optional[EmailStr] = None
    website: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = None
    district: Optional[str] = Field(default=None, max_length=100)

    owner_email: Optional[EmailStr] = None
    owner_phone: str = Field(min_length=8, max_length=30)
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
    town_or_village: Optional[str] = None
    physical_address: Optional[str] = None


class CompanyOwnerRegistrationRead(BaseModel):
    company_id: UUID
    institution_type: InstitutionType
    owner_user_id: UUID
    staff_membership_id: UUID
    status: str
    message: str
