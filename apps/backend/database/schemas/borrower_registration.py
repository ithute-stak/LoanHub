from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from database.schemas.employer_group import EmployerGroupCreate
from database.models.enums import (
    UserRole,
    Gender,
    MaritalStatus,
    EmploymentStatus,
)


class BorrowerRegistrationCreate(BaseModel):
    # User fields
    email: Optional[EmailStr] = None
    phone: str
    password_hash: str

    # Borrower fields
    first_name: str
    middle_name: Optional[str] = None
    last_name: str

    gender: Gender
    date_of_birth: date
    national_id: Optional[str] = None
    passport_number: Optional[str] = None

    marital_status: Optional[MaritalStatus] = None
    nationality: Optional[str] = "Mosotho"

    district: str
    town_or_village: Optional[str] = None
    physical_address: Optional[str] = None

    employment_status: EmploymentStatus
    employer_name: Optional[str] = None
    employer_group_id: Optional[UUID] = None
    new_employer_group: Optional[EmployerGroupCreate] = None
    income_day: Optional[int] = Field(default=None, ge=1, le=31)
    job_title: Optional[str] = None
    monthly_income: Optional[Decimal] = None
    salary_date: Optional[str] = None

    has_existing_loans: bool = False
    existing_loan_total: Decimal = Decimal("0.00")

    consent_to_share_profile: bool = False
    consent_to_credit_checks: bool = False


class BorrowerRegistrationResponse(BaseModel):
    user_id: UUID
    person_id: UUID
    borrower_id: UUID

    email: Optional[EmailStr] = None
    phone: str
    role: UserRole

    first_name: str
    last_name: str
    district: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }