from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_number", name="uq_employee_company_number"),
        UniqueConstraint("staff_id", name="uq_employee_staff"),
    )

    staff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_staff.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reports_to_staff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_staff.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    hr_department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hr_departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hr_position_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hr_positions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hr_shift_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hr_shifts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    employee_number = Column(String(80), nullable=False)
    national_id = Column(String(80), nullable=True, index=True)
    passport_number = Column(String(80), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    job_title = Column(String(150), nullable=True)
    department = Column(String(120), nullable=True, index=True)
    employment_type = Column(String(50), nullable=False, default="full_time")
    employment_status = Column(String(50), nullable=False, default="active", index=True)
    hire_date = Column(Date, nullable=True)
    probation_end_date = Column(Date, nullable=True)
    termination_date = Column(Date, nullable=True)
    contract_number = Column(String(100), nullable=True)
    contract_start_date = Column(Date, nullable=True)
    contract_end_date = Column(Date, nullable=True, index=True)
    base_salary = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(8), nullable=False, default="LSL")
    skills = Column(JSONB, nullable=False, default=list)
    target_config = Column(JSONB, nullable=False, default=dict)
    emergency_contacts = Column(JSONB, nullable=False, default=list)
    qualifications = Column(JSONB, nullable=False, default=list)
    certifications = Column(JSONB, nullable=False, default=list)
    employment_history = Column(JSONB, nullable=False, default=list)
    bank_name = Column(String(120), nullable=True)
    bank_account_name = Column(String(160), nullable=True)
    bank_account_number = Column(String(100), nullable=True)
    tax_number = Column(String(100), nullable=True)
    pension_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    is_manager = Column(Boolean, nullable=False, default=False)

    staff = relationship(
        "CompanyStaff",
        foreign_keys=[staff_id],
        back_populates="employee_profile",
    )
    reports_to = relationship("CompanyStaff", foreign_keys=[reports_to_staff_id])
    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    goals = relationship(
        "PerformanceGoal",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    reviews = relationship(
        "PerformanceReview",
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="PerformanceReview.employee_id",
    )


class PerformanceGoal(Base):
    __tablename__ = "performance_goals"

    employee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("employee_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, default="general", index=True)
    target_value = Column(Numeric(15, 3), nullable=False, default=100)
    current_value = Column(Numeric(15, 3), nullable=False, default=0)
    unit = Column(String(50), nullable=False, default="percent")
    weight = Column(Numeric(6, 3), nullable=False, default=1)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(String(40), nullable=False, default="active", index=True)
    completed_at = Column(DateTime, nullable=True)

    employee = relationship("EmployeeProfile", back_populates="goals")
    created_by_user = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"

    employee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("employee_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_staff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_staff.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    overall_score = Column(Numeric(6, 2), nullable=False)
    rating = Column(String(50), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="completed", index=True)
    strengths = Column(Text, nullable=True)
    improvements = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    metrics = Column(JSONB, nullable=False, default=dict)
    employee_acknowledged_at = Column(DateTime, nullable=True)

    employee = relationship(
        "EmployeeProfile",
        back_populates="reviews",
        foreign_keys=[employee_id],
    )
    reviewer = relationship("CompanyStaff", foreign_keys=[reviewer_staff_id])
