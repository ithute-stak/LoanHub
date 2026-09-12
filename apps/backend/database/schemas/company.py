from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from database.models.enums import CompanyStatus, InstitutionType
from database.schemas.file_management import ManagedFileRead


def _normalize_mpesa_shortcode(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if not normalized.isdigit() or not 4 <= len(normalized) <= 12:
        raise ValueError("M-Pesa shortcode must contain 4 to 12 digits")
    return normalized


class LoanCompanyBase(BaseModel):
    name: str
    institution_type: InstitutionType = InstitutionType.LOAN_COMPANY
    registration_number: Optional[str] = None
    license_number: Optional[str] = None
    phone: str
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    mpesa_shortcode: Optional[str] = Field(default=None, min_length=4, max_length=12, pattern=r"^[0-9]{4,12}$")
    status: CompanyStatus = CompanyStatus.PENDING
    is_active: bool = True

    @field_validator("mpesa_shortcode", mode="before")
    @classmethod
    def normalize_mpesa_shortcode(cls, value):
        return _normalize_mpesa_shortcode(value)


class LoanCompanyCreate(LoanCompanyBase):
    pass


class LoanCompanyUpdate(BaseModel):
    name: Optional[str] = None
    institution_type: Optional[InstitutionType] = None
    registration_number: Optional[str] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    mpesa_shortcode: Optional[str] = Field(default=None, min_length=4, max_length=12, pattern=r"^[0-9]{4,12}$")
    status: Optional[CompanyStatus] = None
    is_active: Optional[bool] = None

    @field_validator("mpesa_shortcode", mode="before")
    @classmethod
    def normalize_mpesa_shortcode(cls, value):
        return _normalize_mpesa_shortcode(value)


class LoanCompanyRead(LoanCompanyBase):
    id: UUID
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class CompanyBrandingRead(BaseModel):
    company_id: UUID
    left_logo_file: ManagedFileRead | None = None
    right_logo_file: ManagedFileRead | None = None
    left_logo_download_url: str | None = None
    right_logo_download_url: str | None = None


class CompanyBrandingUploadRead(CompanyBrandingRead):
    message: str | None = None


class CompanyOwnerAccountRead(BaseModel):
    staff_id: UUID
    user_id: UUID
    full_name: str
    email: Optional[EmailStr] = None
    phone: str
    is_active: bool
    is_verified: bool
    must_change_password: bool


class CompanyOwnerAccountUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, min_length=8, max_length=30)
    is_active: Optional[bool] = None


class CompanyOwnerTemporaryPasswordRead(BaseModel):
    user_id: UUID
    temporary_password: str
    must_change_password: bool = True
    message: str
