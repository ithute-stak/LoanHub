from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from database.models.enums import UserRole
from database.schemas.person_schema import PersonRead
from utils.banking import standard_bank_fields, validate_account_number_for_bank


class EmployeeProfileUpdate(BaseModel):
    employee_number: str = Field(min_length=1, max_length=80)
    job_title: str | None = Field(default=None, max_length=150)
    department: str | None = Field(default=None, max_length=120)
    employment_type: str = Field(default="full_time", max_length=50)
    employment_status: str = Field(default="active", max_length=50)
    hire_date: date | None = None
    probation_end_date: date | None = None
    termination_date: date | None = None
    contract_number: str | None = Field(default=None, max_length=100)
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    reports_to_staff_id: UUID | None = None
    hr_department_id: UUID | None = None
    hr_position_id: UUID | None = None
    hr_shift_id: UUID | None = None
    national_id: str | None = Field(default=None, max_length=80)
    passport_number: str | None = Field(default=None, max_length=80)
    date_of_birth: date | None = None
    base_salary: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="LSL", min_length=3, max_length=8)
    skills: list[str] = Field(default_factory=list)
    target_config: dict[str, Any] = Field(default_factory=dict)
    emergency_contacts: list[dict[str, Any]] = Field(default_factory=list)
    qualifications: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    employment_history: list[dict[str, Any]] = Field(default_factory=list)
    bank_name: str | None = Field(default=None, max_length=120)
    bank_account_name: str | None = Field(default=None, max_length=160)
    bank_account_number: str | None = Field(default=None, max_length=100)
    tax_number: str | None = Field(default=None, max_length=100)
    pension_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    is_manager: bool = False

    @field_validator("employee_number", "job_title", "department", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def enforce_payroll_banking_policy(self):
        fields_set = self.model_fields_set
        bank_name_set = "bank_name" in fields_set
        account_number_set = "bank_account_number" in fields_set

        if "bank_account_name" in fields_set and self.bank_account_name is not None:
            self.bank_account_name = self.bank_account_name.strip() or None

        # Existing employee profiles are updated with exclude_unset=True. Do not
        # assign defaults to omitted bank fields here, because doing so would mark
        # them as explicitly set and could clear the stored payroll account.
        if not bank_name_set and not account_number_set:
            return self

        bank_name = str(self.bank_name or "").strip()
        account_number = str(self.bank_account_number or "").strip()

        # Explicitly clearing both fields is allowed. Supplying/changing only one
        # side is not: the policy must always validate a bank/account pair.
        if bank_name_set and account_number_set and not bank_name and not account_number:
            self.bank_name = None
            self.bank_account_number = None
            return self
        if not bank_name_set or not bank_name:
            raise ValueError("Select FNB, PB, STD or NB for the employee bank account")
        if not account_number_set or not account_number:
            raise ValueError("Enter the employee bank account number")

        normalized_bank, _, _ = standard_bank_fields(bank_name)
        self.bank_name = normalized_bank
        self.bank_account_number = validate_account_number_for_bank(normalized_bank, account_number)
        return self


class EmployeeUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None = None
    phone: str
    role: UserRole
    is_active: bool
    person: PersonRead | None = None


class EmployeeProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    staff_id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    reports_to_staff_id: UUID | None = None
    hr_department_id: UUID | None = None
    hr_position_id: UUID | None = None
    hr_shift_id: UUID | None = None
    employee_number: str
    national_id: str | None = None
    passport_number: str | None = None
    date_of_birth: date | None = None
    job_title: str | None = None
    department: str | None = None
    employment_type: str
    employment_status: str
    hire_date: date | None = None
    probation_end_date: date | None = None
    termination_date: date | None = None
    contract_number: str | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    base_salary: Decimal | None = None
    currency: str
    skills: list[str] = Field(default_factory=list)
    target_config: dict[str, Any] = Field(default_factory=dict)
    emergency_contacts: list[dict[str, Any]] = Field(default_factory=list)
    qualifications: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    employment_history: list[dict[str, Any]] = Field(default_factory=list)
    bank_name: str | None = None
    bank_account_name: str | None = None
    bank_account_number: str | None = None
    tax_number: str | None = None
    pension_number: str | None = None
    notes: str | None = None
    is_manager: bool
    created_at: datetime
    updated_at: datetime


class EmployeeRead(BaseModel):
    staff_id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    role: UserRole
    is_active: bool
    user: EmployeeUserRead
    profile: EmployeeProfileRead | None = None


class PerformanceGoalCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    category: str = Field(default="general", max_length=100)
    target_value: Decimal = Field(default=100, gt=0)
    current_value: Decimal = Field(default=0, ge=0)
    unit: str = Field(default="percent", max_length=50)
    weight: Decimal = Field(default=1, gt=0, le=100)
    period_start: date
    period_end: date
    status: str = Field(default="active", max_length=40)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class PerformanceGoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    target_value: Decimal | None = Field(default=None, gt=0)
    current_value: Decimal | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=50)
    weight: Decimal | None = Field(default=None, gt=0, le=100)
    period_start: date | None = None
    period_end: date | None = None
    status: str | None = Field(default=None, max_length=40)


class PerformanceGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    created_by_user_id: UUID | None = None
    title: str
    description: str | None = None
    category: str
    target_value: Decimal
    current_value: Decimal
    unit: str
    weight: Decimal
    period_start: date
    period_end: date
    status: str
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PerformanceReviewCreate(BaseModel):
    period_start: date
    period_end: date
    overall_score: Decimal = Field(ge=0, le=100)
    rating: str = Field(min_length=2, max_length=50)
    status: str = Field(default="completed", max_length=40)
    strengths: str | None = None
    improvements: str | None = None
    comments: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class PerformanceReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    reviewer_staff_id: UUID | None = None
    company_id: UUID
    branch_id: UUID | None = None
    period_start: date
    period_end: date
    overall_score: Decimal
    rating: str
    status: str
    strengths: str | None = None
    improvements: str | None = None
    comments: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    employee_acknowledged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
