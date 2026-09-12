from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from database.models.enums import EmploymentStatus


class BorrowerEvaluationFields(BaseModel):
    employment_type: Optional[str] = Field(default=None, max_length=50)
    employment_start_date: Optional[date] = None
    net_monthly_income: Optional[Decimal] = Field(default=None, ge=0)
    other_monthly_income: Decimal = Field(default=Decimal("0.00"), ge=0)
    other_income_source: Optional[str] = Field(default=None, max_length=200)
    monthly_living_expenses: Decimal = Field(default=Decimal("0.00"), ge=0)
    monthly_debt_repayments: Decimal = Field(default=Decimal("0.00"), ge=0)
    dependants: int = Field(default=0, ge=0, le=50)
    residential_status: Optional[str] = Field(default=None, max_length=40)
    years_at_address: Optional[int] = Field(default=None, ge=0, le=100)
    bank_name: Optional[str] = Field(default=None, max_length=120)
    account_holder_name: Optional[str] = Field(default=None, max_length=200)
    account_last_four: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}$",
        description="Only the final four account digits are stored.",
    )
    consent_to_share_documents: bool = False


class BorrowerBase(BorrowerEvaluationFields):
    user_id: UUID

    employment_status: EmploymentStatus
    employer_name: Optional[str] = None
    employer_group_id: Optional[UUID] = None
    income_day: Optional[int] = Field(default=None, ge=1, le=31)
    job_title: Optional[str] = None
    monthly_income: Optional[Decimal] = Field(default=None, ge=0)
    salary_date: Optional[str] = None

    has_existing_loans: bool = False
    existing_loan_total: Decimal = Field(default=Decimal("0.00"), ge=0)

    consent_to_share_profile: bool = False
    consent_to_credit_checks: bool = False


class BorrowerCreate(BorrowerBase):
    pass


class BorrowerUpdate(BaseModel):
    employment_status: Optional[EmploymentStatus] = None
    employment_type: Optional[str] = Field(default=None, max_length=50)
    employer_name: Optional[str] = None
    employer_group_id: Optional[UUID] = None
    income_day: Optional[int] = Field(default=None, ge=1, le=31)
    job_title: Optional[str] = None
    employment_start_date: Optional[date] = None
    monthly_income: Optional[Decimal] = Field(default=None, ge=0)
    net_monthly_income: Optional[Decimal] = Field(default=None, ge=0)
    other_monthly_income: Optional[Decimal] = Field(default=None, ge=0)
    other_income_source: Optional[str] = Field(default=None, max_length=200)
    salary_date: Optional[str] = None

    monthly_living_expenses: Optional[Decimal] = Field(default=None, ge=0)
    monthly_debt_repayments: Optional[Decimal] = Field(default=None, ge=0)
    dependants: Optional[int] = Field(default=None, ge=0, le=50)
    residential_status: Optional[str] = Field(default=None, max_length=40)
    years_at_address: Optional[int] = Field(default=None, ge=0, le=100)

    has_existing_loans: Optional[bool] = None
    existing_loan_total: Optional[Decimal] = Field(default=None, ge=0)

    bank_name: Optional[str] = Field(default=None, max_length=120)
    account_holder_name: Optional[str] = Field(default=None, max_length=200)
    account_last_four: Optional[str] = Field(default=None, pattern=r"^\d{4}$")

    consent_to_share_profile: Optional[bool] = None
    consent_to_share_documents: Optional[bool] = None
    consent_to_credit_checks: Optional[bool] = None


class BorrowerRead(BorrowerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }
