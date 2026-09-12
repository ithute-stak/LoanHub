export type DashboardMetric = {
  key: string;
  label: string;
  value: number;
  tone: string;
};

export type LendingOperationsDashboard = {
  metrics: DashboardMetric[];
  alerts: Array<{ severity: string; message: string }>;
  module_counts: Record<string, number>;
};

export type CDASPayrollProfile = {
  id: string;
  company_id: string;
  borrower_id: string;
  branch_id: string | null;
  employee_number: string;
  ministry_department: string | null;
  payroll_group: string | null;
  employment_status: string;
  gross_salary: number;
  net_salary: number;
  existing_deductions: number;
  maximum_deduction_percent: number;
  verified: boolean;
  verified_at: string | null;
  verification_reference: string | null;
  verification_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CDASAffordability = {
  affordable: boolean;
  net_salary: number;
  existing_deductions: number;
  proposed_deduction: number;
  maximum_total_deductions: number;
  total_deductions_after: number;
  take_home_after: number;
  available_deduction_capacity: number;
  deduction_ratio_percent: number;
  reasons: string[];
};

export type CDASMandate = {
  id: string;
  company_id: string;
  branch_id: string | null;
  borrower_id: string;
  loan_id: string;
  payroll_profile_id: string;
  mandate_number: string;
  employee_number: string;
  monthly_deduction: number;
  start_date: string;
  end_date: string | null;
  expected_installments: number;
  deductions_received: number;
  total_expected: number;
  total_received: number;
  status: string;
  borrower_consent: boolean;
  external_reference: string | null;
  rejection_reason: string | null;
  created_at: string;
};

export type CDASRemittanceBatch = {
  id: string;
  company_id: string;
  payroll_month: string;
  batch_reference: string;
  source: string;
  status: string;
  expected_amount: number;
  received_amount: number;
  matched_amount: number;
  exception_amount: number;
  line_count: number;
  matched_count: number;
  exception_count: number;
  reconciled_at: string | null;
  notes: string | null;
  created_at: string;
};

export type CDASRemittanceLine = {
  id: string;
  batch_id: string;
  employee_number: string;
  line_reference: string;
  expected_amount: number;
  deducted_amount: number;
  variance_amount: number;
  status: string;
  reason: string | null;
  payment_transaction_id: string | null;
};

export type ReconciliationRun = {
  id: string;
  run_reference: string;
  run_type: string;
  period_start: string;
  period_end: string;
  status: string;
  records_checked: number;
  matched_records: number;
  exception_records: number;
  matched_amount: number;
  exception_amount: number;
  summary: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
};

export type ReconciliationException = {
  id: string;
  run_id: string;
  exception_type: string;
  severity: string;
  reference: string | null;
  expected_amount: number;
  actual_amount: number;
  variance_amount: number;
  status: string;
  description: string;
  resolution_notes: string | null;
  created_at: string;
};

export type CreditBureauEnquiry = {
  id: string;
  borrower_id: string;
  application_id: string | null;
  provider: string;
  enquiry_reference: string;
  purpose: string;
  consent_confirmed: boolean;
  status: string;
  score: number | null;
  risk_grade: string | null;
  existing_accounts: number;
  current_exposure: number;
  monthly_obligations: number;
  adverse_records: number;
  requested_at: string;
  completed_at: string | null;
  failure_reason: string | null;
};

export type ComplianceCase = {
  id: string;
  borrower_id: string | null;
  loan_id: string | null;
  application_id: string | null;
  case_reference: string;
  case_type: string;
  category: string | null;
  severity: string;
  status: string;
  title: string;
  description: string | null;
  risk_score: number;
  flags: string[];
  resolution: string | null;
  due_at: string | null;
  closed_at: string | null;
  created_at: string;
};

export type ComplianceScreening = {
  id: string;
  case_id: string;
  screening_type: string;
  provider: string;
  status: string;
  matched: boolean;
  match_score: number;
  result: Record<string, unknown>;
  notes: string | null;
  screened_at: string;
};

export type CollectionCase = {
  id: string;
  borrower_id: string;
  loan_id: string;
  case_reference: string;
  status: string;
  stage: string;
  days_past_due: number;
  overdue_amount: number;
  outstanding_balance: number;
  priority: string;
  next_action_at: string | null;
  promise_amount: number | null;
  promise_date: string | null;
  promise_status: string | null;
  recovered_amount: number;
  notes: string | null;
  created_at: string;
};

export type CollectionActivity = {
  id: string;
  case_id: string;
  activity_type: string;
  outcome: string | null;
  notes: string | null;
  amount: number | null;
  follow_up_at: string | null;
  performed_at: string;
};

export type RegulatorySubmission = {
  id: string;
  report_type: string;
  submission_reference: string;
  period_start: string;
  period_end: string;
  status: string;
  payload: Record<string, unknown>;
  validation_errors: unknown[];
  generated_file_id: string | null;
  generated_at: string | null;
  approved_at: string | null;
  submitted_at: string | null;
  regulator_reference: string | null;
  notes: string | null;
  created_at: string;
};

export type CreditDecisionPolicy = {
  id: string;
  name: string;
  version: number;
  status: string;
  rules: Record<string, unknown>;
  scorecard: Record<string, unknown>;
  decline_reasons: string[];
  refer_reasons: string[];
  effective_from: string | null;
  effective_to: string | null;
  created_at: string;
};

export type CreditDecision = {
  id: string;
  borrower_id: string;
  application_id: string | null;
  policy_id: string;
  decision_reference: string;
  decision: string;
  score: number;
  reasons: string[];
  conditions: string[];
  input_snapshot: Record<string, unknown>;
  output_snapshot: Record<string, unknown>;
  decided_by: string;
  created_at: string;
};

export type WorkflowTemplate = {
  id: string;
  name: string;
  workflow_type: string;
  version: number;
  status: string;
  steps: Array<Record<string, unknown>>;
  conditions: Record<string, unknown>;
  created_at: string;
};

export type WorkflowInstance = {
  id: string;
  template_id: string;
  application_id: string | null;
  loan_id: string | null;
  borrower_id: string | null;
  instance_reference: string;
  status: string;
  current_step_index: number;
  current_step_key: string | null;
  assigned_role: string | null;
  history: Array<Record<string, unknown>>;
  context_snapshot: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  due_at: string | null;
};
