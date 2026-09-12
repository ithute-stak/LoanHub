from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HRDashboardSummary(BaseModel):
    total_employees: int
    active_employees: int
    employees_present_today: int
    employees_absent_today: int
    employees_on_leave_today: int
    pending_leave_requests: int
    open_vacancies: int
    active_training_programs: int
    assigned_assets: int
    payroll_status: str | None = None
    payroll_net_total: Decimal = Decimal("0")
    departments: int
    branches: int


class HRDepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=40)
    branch_id: UUID | None = None
    parent_id: UUID | None = None
    manager_employee_id: UUID | None = None
    cost_centre: str | None = Field(default=None, max_length=80)
    description: str | None = None
    is_active: bool = True


class HRDepartmentRead(ORMRead):
    id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    parent_id: UUID | None = None
    manager_employee_id: UUID | None = None
    name: str
    code: str
    cost_centre: str | None = None
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HRPositionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=40)
    department_id: UUID | None = None
    reports_to_position_id: UUID | None = None
    grade: str | None = Field(default=None, max_length=60)
    description: str | None = None
    minimum_salary: Decimal | None = Field(default=None, ge=0)
    maximum_salary: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="LSL", min_length=3, max_length=8)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_salary_band(self):
        if (
            self.minimum_salary is not None
            and self.maximum_salary is not None
            and self.maximum_salary < self.minimum_salary
        ):
            raise ValueError("maximum_salary must be greater than or equal to minimum_salary")
        return self


class HRPositionRead(ORMRead):
    id: UUID
    company_id: UUID
    department_id: UUID | None = None
    reports_to_position_id: UUID | None = None
    title: str
    code: str
    grade: str | None = None
    description: str | None = None
    minimum_salary: Decimal | None = None
    maximum_salary: Decimal | None = None
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HRShiftCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=40)
    branch_id: UUID | None = None
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    break_minutes: int = Field(default=0, ge=0, le=720)
    late_grace_minutes: int = Field(default=0, ge=0, le=240)
    work_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    is_active: bool = True


class HRShiftRead(ORMRead):
    id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    name: str
    code: str
    start_time: str
    end_time: str
    break_minutes: Decimal
    late_grace_minutes: Decimal
    work_days: list[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HRAttendanceEventCreate(BaseModel):
    employee_id: UUID
    shift_id: UUID | None = None
    event_type: Literal["clock_in", "clock_out", "break_start", "break_end"]
    occurred_at: datetime | None = None
    source: Literal["manual", "fingerprint", "rfid", "face", "qr", "mobile_gps", "offline_sync"] = "manual"
    device_identifier: str | None = Field(default=None, max_length=120)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    notes: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class HRAttendanceEventRead(ORMRead):
    id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    employee_id: UUID
    shift_id: UUID | None = None
    event_type: str
    occurred_at: datetime
    source: str
    device_identifier: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    status: str
    notes: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class HRLeaveTypeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=40)
    paid: bool = True
    annual_days: Decimal = Field(default=0, ge=0, le=365)
    requires_attachment: bool = False
    approval_levels: int = Field(default=1, ge=1, le=5)
    is_active: bool = True


class HRLeaveTypeRead(ORMRead):
    id: UUID
    company_id: UUID
    name: str
    code: str
    paid: bool
    annual_days: Decimal
    requires_attachment: bool
    approval_levels: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HRLeaveRequestCreate(BaseModel):
    employee_id: UUID
    leave_type_id: UUID
    start_date: date
    end_date: date
    reason: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class HRLeaveDecision(BaseModel):
    decision: Literal["approved", "declined", "cancelled"]
    comment: str | None = None


class HRLeaveRequestRead(ORMRead):
    id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    employee_id: UUID
    leave_type_id: UUID
    start_date: date
    end_date: date
    days_requested: Decimal
    reason: str | None = None
    status: str
    manager_comment: str | None = None
    decided_by_user_id: UUID | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HRPayrollRunCreate(BaseModel):
    period_key: str = Field(min_length=4, max_length=20)
    period_start: date
    period_end: date
    pay_date: date
    branch_id: UUID | None = None
    currency: str = Field(default="LSL", min_length=3, max_length=8)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class HRPayrollStatusUpdate(BaseModel):
    status: Literal["draft", "calculated", "under_review", "approved", "paid", "locked"]


class HRPayrollRunRead(ORMRead):
    id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    period_key: str
    period_start: date
    period_end: date
    pay_date: date
    status: str
    currency: str
    gross_total: Decimal
    deduction_total: Decimal
    net_total: Decimal
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    locked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HRPayrollEntryRead(ORMRead):
    id: UUID
    payroll_run_id: UUID
    company_id: UUID
    employee_id: UUID
    basic_salary: Decimal
    allowances: Decimal
    overtime: Decimal
    deductions: Decimal
    tax: Decimal
    pension: Decimal
    gross_salary: Decimal
    net_salary: Decimal
    components: dict[str, Any]


class HRVacancyCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    reference: str = Field(min_length=2, max_length=60)
    branch_id: UUID | None = None
    department_id: UUID | None = None
    position_id: UUID | None = None
    description: str | None = None
    openings: int = Field(default=1, ge=1, le=1000)
    status: Literal["draft", "published", "closed", "cancelled"] = "draft"
    closing_date: date | None = None


class HRVacancyRead(ORMRead):
    id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    department_id: UUID | None = None
    position_id: UUID | None = None
    title: str
    reference: str
    description: str | None = None
    openings: Decimal
    status: str
    closing_date: date | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HRCandidateCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    vacancy_id: UUID | None = None
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    national_id: str | None = Field(default=None, max_length=80)
    stage: str = Field(default="applied", max_length=40)
    score: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    application_data: dict[str, Any] = Field(default_factory=dict)


class HRCandidateRead(ORMRead):
    id: UUID
    company_id: UUID
    vacancy_id: UUID | None = None
    full_name: str
    email: str | None = None
    phone: str | None = None
    national_id: str | None = None
    stage: str
    score: Decimal | None = None
    notes: str | None = None
    application_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class HRTrainingProgramCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    provider: str | None = Field(default=None, max_length=160)
    branch_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    capacity: int | None = Field(default=None, ge=1, le=100000)
    status: str = Field(default="planned", max_length=30)
    skills: list[str] = Field(default_factory=list)
    cost: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="LSL", min_length=3, max_length=8)


class HRTrainingProgramRead(ORMRead):
    id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    title: str
    provider: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    capacity: Decimal | None = None
    status: str
    skills: list[str]
    cost: Decimal | None = None
    currency: str
    created_at: datetime
    updated_at: datetime


class HRTrainingEnrollmentCreate(BaseModel):
    employee_id: UUID


class HRTrainingEnrollmentRead(ORMRead):
    id: UUID
    program_id: UUID
    company_id: UUID
    employee_id: UUID
    status: str
    attendance_percent: Decimal
    result: str | None = None
    certificate_reference: str | None = None
    created_at: datetime
    updated_at: datetime


class HRAssetCreate(BaseModel):
    asset_tag: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=80)
    branch_id: UUID | None = None
    serial_number: str | None = Field(default=None, max_length=120)
    status: str = Field(default="available", max_length=30)
    condition: str = Field(default="good", max_length=40)
    purchase_date: date | None = None
    purchase_cost: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="LSL", min_length=3, max_length=8)
    notes: str | None = None


class HRAssetRead(ORMRead):
    id: UUID
    company_id: UUID
    branch_id: UUID | None = None
    asset_tag: str
    name: str
    category: str
    serial_number: str | None = None
    status: str
    condition: str
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
    currency: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class HRAssetAssignmentCreate(BaseModel):
    employee_id: UUID
    expected_return_date: date | None = None
    condition_out: str | None = Field(default=None, max_length=40)
    notes: str | None = None


class HRAssetAssignmentRead(ORMRead):
    id: UUID
    asset_id: UUID
    company_id: UUID
    employee_id: UUID
    assigned_at: datetime
    expected_return_date: date | None = None
    returned_at: datetime | None = None
    condition_out: str | None = None
    condition_in: str | None = None
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class HRSelfServiceSummary(BaseModel):
    employee_id: UUID | None
    employee_number: str | None
    employment_status: str | None
    job_title: str | None
    department: str | None
    pending_leave_requests: int
    current_assets: int
    upcoming_training: int
    latest_payroll_period: str | None
