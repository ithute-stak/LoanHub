from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class EmployeePerformanceRead(BaseModel):
    staff_id: UUID
    employee_id: UUID | None = None
    user_id: UUID
    branch_id: UUID | None = None
    employee_name: str
    role: str
    job_title: str | None = None
    department: str | None = None
    offers_created: int
    offers_accepted: int
    loans_approved: int
    loans_disbursed: int
    payment_transactions: int
    successful_payment_amount: Decimal
    active_goals: int
    completed_goals: int
    goal_completion_percent: float
    average_review_score: float
    performance_score: float


class BranchPerformanceRead(BaseModel):
    branch_id: UUID | None = None
    branch_name: str
    employee_count: int
    active_loans: int
    overdue_loans: int
    loan_principal: Decimal
    payments_received: Decimal
    average_employee_score: float


class CompanyPerformanceRead(BaseModel):
    company_id: UUID
    company_name: str
    employee_count: int
    branch_count: int
    active_loans: int
    overdue_loans: int
    outstanding_balance: Decimal
    successful_payments: Decimal
    employee_average_score: float
    operational_score: float


class PerformanceOverviewRead(BaseModel):
    scope: str
    employee_count: int
    branch_count: int
    company_count: int
    active_loans: int
    overdue_loans: int
    total_outstanding: Decimal
    successful_payments: Decimal
    average_employee_score: float
    employees: list[EmployeePerformanceRead] = Field(default_factory=list)
    branches: list[BranchPerformanceRead] = Field(default_factory=list)
    companies: list[CompanyPerformanceRead] = Field(default_factory=list)
