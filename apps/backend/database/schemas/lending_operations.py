from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: Decimal | int | float
    tone: str = "neutral"


class LendingOperationsDashboard(BaseModel):
    metrics: list[DashboardMetric]
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    module_counts: dict[str, int] = Field(default_factory=dict)


class CDASPayrollProfileCreate(BaseModel):
    borrower_id: UUID
    branch_id: UUID | None = None
    employee_number: str = Field(min_length=1, max_length=100)
    ministry_department: str | None = None
    payroll_group: str | None = None
    employment_status: str = "active"
    gross_salary: Decimal = Decimal("0")
    net_salary: Decimal = Decimal("0")
    existing_deductions: Decimal = Decimal("0")
    maximum_deduction_percent: Decimal = Decimal("40")
    verification_reference: str | None = None
    verification_notes: str | None = None
    verified: bool = False


class CDASPayrollProfileRead(ORMModel):
    id: UUID
    company_id: UUID
    borrower_id: UUID
    branch_id: UUID | None
    employee_number: str
    ministry_department: str | None
    payroll_group: str | None
    employment_status: str
    gross_salary: Decimal
    net_salary: Decimal
    existing_deductions: Decimal
    maximum_deduction_percent: Decimal
    verified: bool
    verified_at: datetime | None
    verification_reference: str | None
    verification_notes: str | None
    created_at: datetime
    updated_at: datetime


class CDASAffordabilityRequest(BaseModel):
    payroll_profile_id: UUID | None = None
    net_salary: Decimal | None = None
    existing_deductions: Decimal | None = None
    proposed_deduction: Decimal = Field(gt=0)
    maximum_deduction_percent: Decimal | None = None
    minimum_take_home: Decimal = Decimal("0")


class CDASAffordabilityRead(BaseModel):
    affordable: bool
    net_salary: Decimal
    existing_deductions: Decimal
    proposed_deduction: Decimal
    maximum_total_deductions: Decimal
    total_deductions_after: Decimal
    take_home_after: Decimal
    available_deduction_capacity: Decimal
    deduction_ratio_percent: Decimal
    reasons: list[str]


class CDASMandateCreate(BaseModel):
    borrower_id: UUID
    loan_id: UUID
    payroll_profile_id: UUID
    monthly_deduction: Decimal = Field(gt=0)
    start_date: date
    end_date: date | None = None
    expected_installments: int = Field(default=1, ge=1, le=600)
    borrower_consent: bool = False
    consent_file_id: UUID | None = None
    external_reference: str | None = None


class CDASMandateStatusUpdate(BaseModel):
    status: Literal["draft", "submitted", "pending_verification", "accepted", "active", "suspended", "rescheduled", "completed", "cancelled", "rejected"]
    external_reference: str | None = None
    rejection_reason: str | None = None


class CDASMandateRead(ORMModel):
    id: UUID
    company_id: UUID
    branch_id: UUID | None
    borrower_id: UUID
    loan_id: UUID
    payroll_profile_id: UUID
    mandate_number: str
    employee_number: str
    monthly_deduction: Decimal
    start_date: date
    end_date: date | None
    expected_installments: int
    deductions_received: int
    total_expected: Decimal
    total_received: Decimal
    status: str
    borrower_consent: bool
    consent_file_id: UUID | None
    external_reference: str | None
    rejection_reason: str | None
    submitted_at: datetime | None
    activated_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class CDASRemittanceBatchCreate(BaseModel):
    payroll_month: date
    batch_reference: str = Field(min_length=1, max_length=100)
    source: str = "manual"
    expected_amount: Decimal = Decimal("0")
    received_amount: Decimal = Decimal("0")
    imported_file_id: UUID | None = None
    notes: str | None = None


class CDASRemittanceLineCreate(BaseModel):
    employee_number: str = Field(min_length=1, max_length=100)
    line_reference: str = Field(min_length=1, max_length=120)
    deducted_amount: Decimal = Field(ge=0)
    expected_amount: Decimal | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class CDASRemittanceLineRead(ORMModel):
    id: UUID
    batch_id: UUID
    company_id: UUID
    mandate_id: UUID | None
    borrower_id: UUID | None
    loan_id: UUID | None
    employee_number: str
    line_reference: str
    expected_amount: Decimal
    deducted_amount: Decimal
    variance_amount: Decimal
    status: str
    reason: str | None
    payment_transaction_id: UUID | None
    raw_payload: dict[str, Any]


class CDASRemittanceBatchRead(ORMModel):
    id: UUID
    company_id: UUID
    payroll_month: date
    batch_reference: str
    source: str
    status: str
    expected_amount: Decimal
    received_amount: Decimal
    matched_amount: Decimal
    exception_amount: Decimal
    line_count: int
    matched_count: int
    exception_count: int
    imported_file_id: UUID | None
    reconciled_at: datetime | None
    notes: str | None
    created_at: datetime


class ReconciliationRunCreate(BaseModel):
    run_type: Literal["full", "payments", "loans", "accounting", "cdas"] = "full"
    period_start: date
    period_end: date
    branch_id: UUID | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class ReconciliationRunRead(ORMModel):
    id: UUID
    company_id: UUID
    branch_id: UUID | None
    run_reference: str
    run_type: str
    period_start: date
    period_end: date
    status: str
    records_checked: int
    matched_records: int
    exception_records: int
    matched_amount: Decimal
    exception_amount: Decimal
    summary: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class ReconciliationExceptionRead(ORMModel):
    id: UUID
    run_id: UUID
    company_id: UUID
    branch_id: UUID | None
    exception_type: str
    severity: str
    source_entity_type: str | None
    source_entity_id: UUID | None
    reference: str | None
    expected_amount: Decimal
    actual_amount: Decimal
    variance_amount: Decimal
    status: str
    description: str
    resolution_notes: str | None
    resolved_at: datetime | None
    created_at: datetime


class ReconciliationExceptionUpdate(BaseModel):
    status: Literal["open", "investigating", "resolved", "accepted_variance", "dismissed"]
    resolution_notes: str | None = None


class CreditBureauEnquiryCreate(BaseModel):
    borrower_id: UUID
    application_id: UUID | None = None
    provider: str = "manual"
    purpose: str = "credit_assessment"
    consent_confirmed: bool
    enquiry_data: dict[str, Any] = Field(default_factory=dict)


class CreditBureauEnquiryComplete(BaseModel):
    status: Literal["completed", "failed"] = "completed"
    score: int | None = Field(default=None, ge=0, le=1000)
    risk_grade: str | None = None
    existing_accounts: int = Field(default=0, ge=0)
    current_exposure: Decimal = Decimal("0")
    monthly_obligations: Decimal = Decimal("0")
    adverse_records: int = Field(default=0, ge=0)
    response_data: dict[str, Any] = Field(default_factory=dict)
    report_file_id: UUID | None = None
    expires_at: datetime | None = None
    failure_reason: str | None = None


class CreditBureauEnquiryRead(ORMModel):
    id: UUID
    company_id: UUID
    branch_id: UUID | None
    borrower_id: UUID
    application_id: UUID | None
    provider: str
    enquiry_reference: str
    purpose: str
    consent_confirmed: bool
    status: str
    score: int | None
    risk_grade: str | None
    existing_accounts: int
    current_exposure: Decimal
    monthly_obligations: Decimal
    adverse_records: int
    enquiry_data: dict[str, Any]
    response_data: dict[str, Any]
    report_file_id: UUID | None
    requested_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    failure_reason: str | None


class ComplianceCaseCreate(BaseModel):
    borrower_id: UUID | None = None
    loan_id: UUID | None = None
    application_id: UUID | None = None
    case_type: Literal["kyc", "aml", "fraud", "sanctions", "pep", "adverse_media", "source_of_funds"] = "kyc"
    category: str | None = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    title: str = Field(min_length=1, max_length=220)
    description: str | None = None
    risk_score: Decimal = Decimal("0")
    flags: list[str] = Field(default_factory=list)
    assigned_to_user_id: UUID | None = None
    due_at: datetime | None = None


class ComplianceCaseUpdate(BaseModel):
    status: Literal["open", "under_review", "escalated", "cleared", "reported", "closed"] | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    assigned_to_user_id: UUID | None = None
    resolution: str | None = None
    risk_score: Decimal | None = None
    flags: list[str] | None = None


class ComplianceCaseRead(ORMModel):
    id: UUID
    company_id: UUID
    branch_id: UUID | None
    borrower_id: UUID | None
    loan_id: UUID | None
    application_id: UUID | None
    case_reference: str
    case_type: str
    category: str | None
    severity: str
    status: str
    title: str
    description: str | None
    risk_score: Decimal
    flags: list[Any]
    assigned_to_user_id: UUID | None
    resolution: str | None
    due_at: datetime | None
    closed_at: datetime | None
    created_at: datetime


class ComplianceScreeningCreate(BaseModel):
    screening_type: Literal["identity", "sanctions", "pep", "adverse_media", "fraud", "device", "document", "source_of_funds"]
    provider: str = "manual"
    status: str = "completed"
    matched: bool = False
    match_score: Decimal = Decimal("0")
    result: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class ComplianceScreeningRead(ORMModel):
    id: UUID
    case_id: UUID
    company_id: UUID
    screening_type: str
    provider: str
    status: str
    matched: bool
    match_score: Decimal
    result: dict[str, Any]
    notes: str | None
    screened_at: datetime


class CollectionCaseCreate(BaseModel):
    loan_id: UUID
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    assigned_to_user_id: UUID | None = None
    next_action_at: datetime | None = None
    notes: str | None = None


class CollectionCaseUpdate(BaseModel):
    status: Literal["open", "contacting", "promise_to_pay", "restructured", "legal", "written_off", "recovered", "closed"] | None = None
    stage: Literal["early_arrears", "late_arrears", "pre_legal", "legal", "recovery", "closed"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    assigned_to_user_id: UUID | None = None
    next_action_at: datetime | None = None
    promise_amount: Decimal | None = None
    promise_date: date | None = None
    promise_status: str | None = None
    notes: str | None = None


class CollectionCaseRead(ORMModel):
    id: UUID
    company_id: UUID
    branch_id: UUID | None
    borrower_id: UUID
    loan_id: UUID
    case_reference: str
    status: str
    stage: str
    days_past_due: int
    overdue_amount: Decimal
    outstanding_balance: Decimal
    priority: str
    assigned_to_user_id: UUID | None
    next_action_at: datetime | None
    promise_amount: Decimal | None
    promise_date: date | None
    promise_status: str | None
    last_contact_at: datetime | None
    legal_handover_at: datetime | None
    write_off_at: datetime | None
    recovered_amount: Decimal
    notes: str | None
    created_at: datetime


class CollectionActivityCreate(BaseModel):
    activity_type: Literal["call", "sms", "email", "visit", "letter", "promise", "payment", "restructure", "legal_handover", "note"]
    outcome: str | None = None
    notes: str | None = None
    amount: Decimal | None = None
    follow_up_at: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CollectionActivityRead(ORMModel):
    id: UUID
    case_id: UUID
    company_id: UUID
    activity_type: str
    outcome: str | None
    notes: str | None
    amount: Decimal | None
    follow_up_at: datetime | None
    performed_at: datetime
    metadata_json: dict[str, Any]


class RegulatorySubmissionCreate(BaseModel):
    report_type: Literal["portfolio", "arrears", "provisions", "write_offs", "complaints", "aml", "liquidity", "consumer_protection", "credit_reporting", "full_return"]
    period_start: date
    period_end: date
    notes: str | None = None


class RegulatorySubmissionUpdate(BaseModel):
    status: Literal["draft", "generated", "validated", "approved", "submitted", "rejected"]
    regulator_reference: str | None = None
    notes: str | None = None


class RegulatorySubmissionRead(ORMModel):
    id: UUID
    company_id: UUID
    report_type: str
    submission_reference: str
    period_start: date
    period_end: date
    status: str
    payload: dict[str, Any]
    validation_errors: list[Any]
    generated_file_id: UUID | None
    generated_at: datetime | None
    approved_at: datetime | None
    submitted_at: datetime | None
    regulator_reference: str | None
    notes: str | None
    created_at: datetime


class CreditDecisionPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    version: int = Field(default=1, ge=1)
    status: Literal["draft", "active", "retired"] = "draft"
    rules: dict[str, Any] = Field(default_factory=dict)
    scorecard: dict[str, Any] = Field(default_factory=dict)
    decline_reasons: list[str] = Field(default_factory=list)
    refer_reasons: list[str] = Field(default_factory=list)
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class CreditDecisionPolicyRead(ORMModel):
    id: UUID
    company_id: UUID
    name: str
    version: int
    status: str
    rules: dict[str, Any]
    scorecard: dict[str, Any]
    decline_reasons: list[Any]
    refer_reasons: list[Any]
    effective_from: datetime | None
    effective_to: datetime | None
    created_at: datetime


class CreditDecisionEvaluateRequest(BaseModel):
    borrower_id: UUID
    application_id: UUID | None = None
    policy_id: UUID
    requested_amount: Decimal | None = None
    proposed_installment: Decimal | None = None
    additional_inputs: dict[str, Any] = Field(default_factory=dict)


class CreditDecisionRead(ORMModel):
    id: UUID
    company_id: UUID
    borrower_id: UUID
    application_id: UUID | None
    policy_id: UUID
    decision_reference: str
    decision: str
    score: Decimal
    reasons: list[Any]
    conditions: list[Any]
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any]
    decided_by: str
    override_decision: str | None
    override_reason: str | None
    created_at: datetime


class WorkflowTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    workflow_type: str = "loan_approval"
    version: int = Field(default=1, ge=1)
    status: Literal["draft", "active", "retired"] = "draft"
    steps: list[dict[str, Any]] = Field(default_factory=list)
    conditions: dict[str, Any] = Field(default_factory=dict)


class WorkflowTemplateRead(ORMModel):
    id: UUID
    company_id: UUID
    name: str
    workflow_type: str
    version: int
    status: str
    steps: list[Any]
    conditions: dict[str, Any]
    created_at: datetime


class WorkflowInstanceCreate(BaseModel):
    template_id: UUID
    application_id: UUID | None = None
    loan_id: UUID | None = None
    borrower_id: UUID | None = None
    assigned_user_id: UUID | None = None
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    due_at: datetime | None = None


class WorkflowAdvanceRequest(BaseModel):
    action: Literal["approve", "reject", "return", "skip", "complete"]
    notes: str | None = None
    assigned_user_id: UUID | None = None


class WorkflowInstanceRead(ORMModel):
    id: UUID
    company_id: UUID
    template_id: UUID
    application_id: UUID | None
    loan_id: UUID | None
    borrower_id: UUID | None
    instance_reference: str
    status: str
    current_step_index: int
    current_step_key: str | None
    assigned_role: str | None
    assigned_user_id: UUID | None
    history: list[Any]
    context_snapshot: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None
    due_at: datetime | None
