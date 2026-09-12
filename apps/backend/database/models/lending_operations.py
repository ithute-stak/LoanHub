from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class CDASPayrollProfile(Base):
    __tablename__ = "cdas_payroll_profiles"
    __table_args__ = (
        UniqueConstraint("company_id", "borrower_id", name="uq_cdas_payroll_company_borrower"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_number = Column(String(100), nullable=False, index=True)
    ministry_department = Column(String(200), nullable=True)
    payroll_group = Column(String(120), nullable=True)
    employment_status = Column(String(40), nullable=False, default="active", index=True)
    gross_salary = Column(Numeric(15, 2), nullable=False, default=0)
    net_salary = Column(Numeric(15, 2), nullable=False, default=0)
    existing_deductions = Column(Numeric(15, 2), nullable=False, default=0)
    maximum_deduction_percent = Column(Numeric(8, 3), nullable=False, default=40)
    verified = Column(Boolean, nullable=False, default=False, index=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verification_reference = Column(String(160), nullable=True)
    verification_notes = Column(Text, nullable=True)


class CDASDeductionMandate(Base):
    __tablename__ = "cdas_deduction_mandates"
    __table_args__ = (
        UniqueConstraint("company_id", "mandate_number", name="uq_cdas_mandate_number"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False, index=True)
    payroll_profile_id = Column(UUID(as_uuid=True), ForeignKey("cdas_payroll_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    mandate_number = Column(String(80), nullable=False, index=True)
    employee_number = Column(String(100), nullable=False, index=True)
    monthly_deduction = Column(Numeric(15, 2), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    expected_installments = Column(Integer, nullable=False, default=1)
    deductions_received = Column(Integer, nullable=False, default=0)
    total_expected = Column(Numeric(15, 2), nullable=False, default=0)
    total_received = Column(Numeric(15, 2), nullable=False, default=0)
    status = Column(String(40), nullable=False, default="draft", index=True)
    borrower_consent = Column(Boolean, nullable=False, default=False)
    consent_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="SET NULL"), nullable=True)
    external_reference = Column(String(180), nullable=True, index=True)
    rejection_reason = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class CDASRemittanceBatch(Base):
    __tablename__ = "cdas_remittance_batches"
    __table_args__ = (
        UniqueConstraint("company_id", "batch_reference", name="uq_cdas_remittance_batch_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    payroll_month = Column(Date, nullable=False, index=True)
    batch_reference = Column(String(100), nullable=False, index=True)
    source = Column(String(40), nullable=False, default="manual")
    status = Column(String(40), nullable=False, default="draft", index=True)
    expected_amount = Column(Numeric(15, 2), nullable=False, default=0)
    received_amount = Column(Numeric(15, 2), nullable=False, default=0)
    matched_amount = Column(Numeric(15, 2), nullable=False, default=0)
    exception_amount = Column(Numeric(15, 2), nullable=False, default=0)
    line_count = Column(Integer, nullable=False, default=0)
    matched_count = Column(Integer, nullable=False, default=0)
    exception_count = Column(Integer, nullable=False, default=0)
    imported_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="SET NULL"), nullable=True)
    imported_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reconciled_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class CDASRemittanceLine(Base):
    __tablename__ = "cdas_remittance_lines"
    __table_args__ = (
        UniqueConstraint("batch_id", "line_reference", name="uq_cdas_batch_line_reference"),
    )

    batch_id = Column(UUID(as_uuid=True), ForeignKey("cdas_remittance_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    mandate_id = Column(UUID(as_uuid=True), ForeignKey("cdas_deduction_mandates.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_number = Column(String(100), nullable=False, index=True)
    line_reference = Column(String(120), nullable=False)
    expected_amount = Column(Numeric(15, 2), nullable=False, default=0)
    deducted_amount = Column(Numeric(15, 2), nullable=False, default=0)
    variance_amount = Column(Numeric(15, 2), nullable=False, default=0)
    status = Column(String(40), nullable=False, default="unmatched", index=True)
    reason = Column(Text, nullable=True)
    payment_transaction_id = Column(UUID(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True)
    raw_payload = Column(JSONB, nullable=False, default=dict)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    run_reference = Column(String(100), nullable=False, unique=True, index=True)
    run_type = Column(String(50), nullable=False, default="full", index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(String(40), nullable=False, default="running", index=True)
    records_checked = Column(Integer, nullable=False, default=0)
    matched_records = Column(Integer, nullable=False, default=0)
    exception_records = Column(Integer, nullable=False, default=0)
    matched_amount = Column(Numeric(15, 2), nullable=False, default=0)
    exception_amount = Column(Numeric(15, 2), nullable=False, default=0)
    summary = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ReconciliationException(Base):
    __tablename__ = "reconciliation_exceptions"

    run_id = Column(UUID(as_uuid=True), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    exception_type = Column(String(80), nullable=False, index=True)
    severity = Column(String(30), nullable=False, default="medium", index=True)
    source_entity_type = Column(String(80), nullable=True)
    source_entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    reference = Column(String(180), nullable=True, index=True)
    expected_amount = Column(Numeric(15, 2), nullable=False, default=0)
    actual_amount = Column(Numeric(15, 2), nullable=False, default=0)
    variance_amount = Column(Numeric(15, 2), nullable=False, default=0)
    status = Column(String(40), nullable=False, default="open", index=True)
    description = Column(Text, nullable=False)
    resolution_notes = Column(Text, nullable=True)
    resolved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class CreditBureauEnquiry(Base):
    __tablename__ = "credit_bureau_enquiries"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="SET NULL"), nullable=True, index=True)
    provider = Column(String(80), nullable=False, default="manual")
    enquiry_reference = Column(String(100), nullable=False, unique=True, index=True)
    purpose = Column(String(80), nullable=False, default="credit_assessment")
    consent_confirmed = Column(Boolean, nullable=False, default=False)
    status = Column(String(40), nullable=False, default="requested", index=True)
    score = Column(Integer, nullable=True)
    risk_grade = Column(String(40), nullable=True)
    existing_accounts = Column(Integer, nullable=False, default=0)
    current_exposure = Column(Numeric(15, 2), nullable=False, default=0)
    monthly_obligations = Column(Numeric(15, 2), nullable=False, default=0)
    adverse_records = Column(Integer, nullable=False, default=0)
    enquiry_data = Column(JSONB, nullable=False, default=dict)
    response_data = Column(JSONB, nullable=False, default=dict)
    report_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="SET NULL"), nullable=True)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)


class ComplianceCase(Base):
    __tablename__ = "compliance_cases"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="SET NULL"), nullable=True, index=True)
    case_reference = Column(String(100), nullable=False, unique=True, index=True)
    case_type = Column(String(40), nullable=False, default="kyc", index=True)
    category = Column(String(80), nullable=True, index=True)
    severity = Column(String(30), nullable=False, default="medium", index=True)
    status = Column(String(40), nullable=False, default="open", index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text, nullable=True)
    risk_score = Column(Numeric(8, 3), nullable=False, default=0)
    flags = Column(JSONB, nullable=False, default=list)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    opened_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution = Column(Text, nullable=True)
    due_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)


class ComplianceScreening(Base):
    __tablename__ = "compliance_screenings"

    case_id = Column(UUID(as_uuid=True), ForeignKey("compliance_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    screening_type = Column(String(60), nullable=False, index=True)
    provider = Column(String(80), nullable=False, default="manual")
    status = Column(String(40), nullable=False, default="completed", index=True)
    matched = Column(Boolean, nullable=False, default=False)
    match_score = Column(Numeric(8, 3), nullable=False, default=0)
    result = Column(JSONB, nullable=False, default=dict)
    notes = Column(Text, nullable=True)
    screened_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    screened_at = Column(DateTime, nullable=False)


class CollectionCase(Base):
    __tablename__ = "collection_cases"
    __table_args__ = (
        UniqueConstraint("company_id", "loan_id", name="uq_collection_case_company_loan"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False, index=True)
    case_reference = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(40), nullable=False, default="open", index=True)
    stage = Column(String(50), nullable=False, default="early_arrears", index=True)
    days_past_due = Column(Integer, nullable=False, default=0)
    overdue_amount = Column(Numeric(15, 2), nullable=False, default=0)
    outstanding_balance = Column(Numeric(15, 2), nullable=False, default=0)
    priority = Column(String(30), nullable=False, default="normal", index=True)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    next_action_at = Column(DateTime, nullable=True)
    promise_amount = Column(Numeric(15, 2), nullable=True)
    promise_date = Column(Date, nullable=True)
    promise_status = Column(String(40), nullable=True)
    last_contact_at = Column(DateTime, nullable=True)
    legal_handover_at = Column(DateTime, nullable=True)
    write_off_at = Column(DateTime, nullable=True)
    recovered_amount = Column(Numeric(15, 2), nullable=False, default=0)
    notes = Column(Text, nullable=True)


class CollectionActivity(Base):
    __tablename__ = "collection_activities"

    case_id = Column(UUID(as_uuid=True), ForeignKey("collection_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type = Column(String(60), nullable=False, index=True)
    outcome = Column(String(60), nullable=True)
    notes = Column(Text, nullable=True)
    amount = Column(Numeric(15, 2), nullable=True)
    follow_up_at = Column(DateTime, nullable=True)
    performed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    performed_at = Column(DateTime, nullable=False)
    metadata_json = Column(JSONB, nullable=False, default=dict)


class RegulatorySubmission(Base):
    __tablename__ = "regulatory_submissions"
    __table_args__ = (
        UniqueConstraint("company_id", "submission_reference", name="uq_regulatory_submission_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type = Column(String(80), nullable=False, index=True)
    submission_reference = Column(String(100), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(String(40), nullable=False, default="draft", index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    validation_errors = Column(JSONB, nullable=False, default=list)
    generated_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="SET NULL"), nullable=True)
    prepared_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    regulator_reference = Column(String(180), nullable=True)
    notes = Column(Text, nullable=True)


class CreditDecisionPolicy(Base):
    __tablename__ = "credit_decision_policies"
    __table_args__ = (
        UniqueConstraint("company_id", "name", "version", name="uq_credit_decision_policy_version"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(40), nullable=False, default="draft", index=True)
    rules = Column(JSONB, nullable=False, default=dict)
    scorecard = Column(JSONB, nullable=False, default=dict)
    decline_reasons = Column(JSONB, nullable=False, default=list)
    refer_reasons = Column(JSONB, nullable=False, default=list)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    configured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class CreditDecision(Base):
    __tablename__ = "credit_decisions"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="SET NULL"), nullable=True, index=True)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("credit_decision_policies.id", ondelete="RESTRICT"), nullable=False, index=True)
    decision_reference = Column(String(100), nullable=False, unique=True, index=True)
    decision = Column(String(40), nullable=False, index=True)
    score = Column(Numeric(8, 3), nullable=False, default=0)
    reasons = Column(JSONB, nullable=False, default=list)
    conditions = Column(JSONB, nullable=False, default=list)
    input_snapshot = Column(JSONB, nullable=False, default=dict)
    output_snapshot = Column(JSONB, nullable=False, default=dict)
    decided_by = Column(String(40), nullable=False, default="rules_engine")
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    override_decision = Column(String(40), nullable=True)
    override_reason = Column(Text, nullable=True)


class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"
    __table_args__ = (
        UniqueConstraint("company_id", "name", "version", name="uq_workflow_template_version"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    workflow_type = Column(String(60), nullable=False, default="loan_approval", index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(40), nullable=False, default="draft", index=True)
    steps = Column(JSONB, nullable=False, default=list)
    conditions = Column(JSONB, nullable=False, default=dict)
    configured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("workflow_templates.id", ondelete="RESTRICT"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    instance_reference = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(40), nullable=False, default="active", index=True)
    current_step_index = Column(Integer, nullable=False, default=0)
    current_step_key = Column(String(100), nullable=True, index=True)
    assigned_role = Column(String(50), nullable=True, index=True)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    history = Column(JSONB, nullable=False, default=list)
    context_snapshot = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)
