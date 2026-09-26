from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class EmployerPayrollAccount(Base):
    """Company-specific operating configuration for one central work group."""

    __tablename__ = "employer_payroll_accounts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "employer_group_id",
            name="uq_employer_payroll_account_company_group",
        ),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    employer_group_id = Column(UUID(as_uuid=True), ForeignKey("employer_groups.id", ondelete="RESTRICT"), nullable=False, index=True)
    payroll_reference = Column(String(100), nullable=True, index=True)
    payroll_day = Column(Integer, nullable=True)
    collection_channel = Column(String(40), nullable=False, default="employer_payroll", index=True)
    reconciliation_tolerance = Column(Numeric(12, 2), nullable=False, default=0)
    payroll_contact_name = Column(String(200), nullable=True)
    payroll_contact_email = Column(String(255), nullable=True)
    payroll_contact_phone = Column(String(60), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    employer_group = relationship("EmployerGroup")
    employees = relationship("EmployerPayrollEmployee", back_populates="account", cascade="all, delete-orphan")
    cycles = relationship("EmployerPayrollCycle", back_populates="account", cascade="all, delete-orphan")


class EmployerPayrollEmployee(Base):
    """Tenant-owned payroll identity and employment state for a borrower."""

    __tablename__ = "employer_payroll_employees"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "employer_account_id",
            "borrower_id",
            name="uq_employer_payroll_employee_company_account_borrower",
        ),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employer_account_id = Column(UUID(as_uuid=True), ForeignKey("employer_payroll_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    employee_number = Column(String(100), nullable=True, index=True)
    employment_state = Column(String(30), nullable=False, default="active", index=True)
    effective_date = Column(Date, nullable=True)
    termination_date = Column(Date, nullable=True, index=True)
    termination_reason = Column(Text, nullable=True)
    last_verified_at = Column(DateTime, nullable=True)
    metadata_snapshot = Column(JSONB, nullable=False, default=dict)

    account = relationship("EmployerPayrollAccount", back_populates="employees")
    borrower = relationship("Borrower")


class EmployerPayrollCycle(Base):
    """One employer payroll/deduction reconciliation period."""

    __tablename__ = "employer_payroll_cycles"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "employer_account_id",
            "period_key",
            name="uq_employer_payroll_cycle_company_account_period",
        ),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employer_account_id = Column(UUID(as_uuid=True), ForeignKey("employer_payroll_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    period_key = Column(String(7), nullable=False, index=True)
    scheduled_pay_date = Column(Date, nullable=False, index=True)
    expected_amount = Column(Numeric(15, 2), nullable=False, default=0)
    actual_amount = Column(Numeric(15, 2), nullable=False, default=0)
    shortage_amount = Column(Numeric(15, 2), nullable=False, default=0)
    excess_amount = Column(Numeric(15, 2), nullable=False, default=0)
    rejected_amount = Column(Numeric(15, 2), nullable=False, default=0)
    expected_line_count = Column(Integer, nullable=False, default=0)
    matched_line_count = Column(Integer, nullable=False, default=0)
    exception_line_count = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="draft", index=True)
    source = Column(String(40), nullable=False, default="loanhub")
    generated_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    reconciled_at = Column(DateTime, nullable=True)
    reconciled_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    account = relationship("EmployerPayrollAccount", back_populates="cycles")
    deductions = relationship("EmployerPayrollDeduction", back_populates="cycle", cascade="all, delete-orphan")
    reconciled_by = relationship("User", foreign_keys=[reconciled_by_user_id])


class EmployerPayrollDeduction(Base):
    """Expected-vs-actual payroll line, normally tied to one immutable loan folio."""

    __tablename__ = "employer_payroll_deductions"
    __table_args__ = (
        UniqueConstraint("cycle_id", "source_line_key", name="uq_employer_payroll_deduction_cycle_source_key"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id = Column(UUID(as_uuid=True), ForeignKey("employer_payroll_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    folio_number = Column(String(40), nullable=True, index=True)
    employee_number = Column(String(100), nullable=True, index=True)
    source_line_key = Column(String(160), nullable=False)
    expected_amount = Column(Numeric(15, 2), nullable=False, default=0)
    actual_amount = Column(Numeric(15, 2), nullable=False, default=0)
    variance_amount = Column(Numeric(15, 2), nullable=False, default=0)
    status = Column(String(30), nullable=False, default="pending", index=True)
    rejection_code = Column(String(80), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    employer_reference = Column(String(180), nullable=True)
    source_row = Column(JSONB, nullable=False, default=dict)
    imported_at = Column(DateTime, nullable=True)

    cycle = relationship("EmployerPayrollCycle", back_populates="deductions")
    borrower = relationship("Borrower")
    loan = relationship("ClientCompanyLoan")
