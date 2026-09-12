from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class HRDepartment(Base):
    __tablename__ = "hr_departments"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_hr_department_company_code"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("hr_departments.id", ondelete="SET NULL"), nullable=True, index=True)
    manager_employee_id = Column(UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(160), nullable=False)
    code = Column(String(40), nullable=False)
    cost_centre = Column(String(80), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)


class HRPosition(Base):
    __tablename__ = "hr_positions"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_hr_position_company_code"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("hr_departments.id", ondelete="SET NULL"), nullable=True, index=True)
    reports_to_position_id = Column(UUID(as_uuid=True), ForeignKey("hr_positions.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(160), nullable=False)
    code = Column(String(40), nullable=False)
    grade = Column(String(60), nullable=True)
    description = Column(Text, nullable=True)
    minimum_salary = Column(Numeric(15, 2), nullable=True)
    maximum_salary = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(8), nullable=False, default="LSL")
    is_active = Column(Boolean, nullable=False, default=True, index=True)


class HRShift(Base):
    __tablename__ = "hr_shifts"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_hr_shift_company_code"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(120), nullable=False)
    code = Column(String(40), nullable=False)
    start_time = Column(String(8), nullable=False)
    end_time = Column(String(8), nullable=False)
    break_minutes = Column(Numeric(6, 0), nullable=False, default=0)
    late_grace_minutes = Column(Numeric(6, 0), nullable=False, default=0)
    work_days = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)


class HRAttendanceEvent(Base):
    __tablename__ = "hr_attendance_events"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    shift_id = Column(UUID(as_uuid=True), ForeignKey("hr_shifts.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(30), nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(30), nullable=False, default="manual", index=True)
    device_identifier = Column(String(120), nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    status = Column(String(30), nullable=False, default="recorded", index=True)
    notes = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)


class HRLeaveType(Base):
    __tablename__ = "hr_leave_types"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_hr_leave_type_company_code"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    code = Column(String(40), nullable=False)
    paid = Column(Boolean, nullable=False, default=True)
    annual_days = Column(Numeric(6, 2), nullable=False, default=0)
    requires_attachment = Column(Boolean, nullable=False, default=False)
    approval_levels = Column(Numeric(3, 0), nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True, index=True)


class HRLeaveRequest(Base):
    __tablename__ = "hr_leave_requests"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id = Column(UUID(as_uuid=True), ForeignKey("hr_leave_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    days_requested = Column(Numeric(7, 2), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="pending", index=True)
    manager_comment = Column(Text, nullable=True)
    decided_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)


class HRPayrollRun(Base):
    __tablename__ = "hr_payroll_runs"
    __table_args__ = (
        UniqueConstraint("company_id", "period_key", name="uq_hr_payroll_company_period"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    period_key = Column(String(20), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    currency = Column(String(8), nullable=False, default="LSL")
    gross_total = Column(Numeric(17, 2), nullable=False, default=0)
    deduction_total = Column(Numeric(17, 2), nullable=False, default=0)
    net_total = Column(Numeric(17, 2), nullable=False, default=0)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)


class HRPayrollEntry(Base):
    __tablename__ = "hr_payroll_entries"
    __table_args__ = (
        UniqueConstraint("payroll_run_id", "employee_id", name="uq_hr_payroll_entry_employee"),
    )

    payroll_run_id = Column(UUID(as_uuid=True), ForeignKey("hr_payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    basic_salary = Column(Numeric(15, 2), nullable=False, default=0)
    allowances = Column(Numeric(15, 2), nullable=False, default=0)
    overtime = Column(Numeric(15, 2), nullable=False, default=0)
    deductions = Column(Numeric(15, 2), nullable=False, default=0)
    tax = Column(Numeric(15, 2), nullable=False, default=0)
    pension = Column(Numeric(15, 2), nullable=False, default=0)
    gross_salary = Column(Numeric(15, 2), nullable=False, default=0)
    net_salary = Column(Numeric(15, 2), nullable=False, default=0)
    components = Column(JSONB, nullable=False, default=dict)


class HRVacancy(Base):
    __tablename__ = "hr_vacancies"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("hr_departments.id", ondelete="SET NULL"), nullable=True, index=True)
    position_id = Column(UUID(as_uuid=True), ForeignKey("hr_positions.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(180), nullable=False)
    reference = Column(String(60), nullable=False, index=True)
    description = Column(Text, nullable=True)
    openings = Column(Numeric(6, 0), nullable=False, default=1)
    status = Column(String(30), nullable=False, default="draft", index=True)
    closing_date = Column(Date, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)


class HRCandidate(Base):
    __tablename__ = "hr_candidates"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    vacancy_id = Column(UUID(as_uuid=True), ForeignKey("hr_vacancies.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(180), nullable=False)
    email = Column(String(160), nullable=True)
    phone = Column(String(40), nullable=True)
    national_id = Column(String(80), nullable=True, index=True)
    stage = Column(String(40), nullable=False, default="applied", index=True)
    score = Column(Numeric(6, 2), nullable=True)
    notes = Column(Text, nullable=True)
    application_data = Column(JSONB, nullable=False, default=dict)


class HRTrainingProgram(Base):
    __tablename__ = "hr_training_programs"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(180), nullable=False)
    provider = Column(String(160), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    capacity = Column(Numeric(6, 0), nullable=True)
    status = Column(String(30), nullable=False, default="planned", index=True)
    skills = Column(JSONB, nullable=False, default=list)
    cost = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(8), nullable=False, default="LSL")


class HRTrainingEnrollment(Base):
    __tablename__ = "hr_training_enrollments"
    __table_args__ = (
        UniqueConstraint("program_id", "employee_id", name="uq_hr_training_employee"),
    )

    program_id = Column(UUID(as_uuid=True), ForeignKey("hr_training_programs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="registered", index=True)
    attendance_percent = Column(Numeric(6, 2), nullable=False, default=0)
    result = Column(String(80), nullable=True)
    certificate_reference = Column(String(160), nullable=True)


class HRAsset(Base):
    __tablename__ = "hr_assets"
    __table_args__ = (
        UniqueConstraint("company_id", "asset_tag", name="uq_hr_asset_company_tag"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_tag = Column(String(80), nullable=False)
    name = Column(String(180), nullable=False)
    category = Column(String(80), nullable=False, index=True)
    serial_number = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False, default="available", index=True)
    condition = Column(String(40), nullable=False, default="good")
    purchase_date = Column(Date, nullable=True)
    purchase_cost = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(8), nullable=False, default="LSL")
    notes = Column(Text, nullable=True)


class HRAssetAssignment(Base):
    __tablename__ = "hr_asset_assignments"

    asset_id = Column(UUID(as_uuid=True), ForeignKey("hr_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=False)
    expected_return_date = Column(Date, nullable=True)
    returned_at = Column(DateTime(timezone=True), nullable=True)
    condition_out = Column(String(40), nullable=True)
    condition_in = Column(String(40), nullable=True)
    status = Column(String(30), nullable=False, default="assigned", index=True)
    notes = Column(Text, nullable=True)
