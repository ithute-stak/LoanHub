import type { CdasAnalysisRecord } from "@/types/cdasBooking";

export interface CdasOfficialProfile {
  employee_no: string | null;
  name: string | null;
  surname: string | null;
  full_name: string | null;
  date_of_birth: string | null;
  department: string | null;
  joining_date: string | null;
  end_date: string | null;
}

export interface CdasOfficialDeduction {
  deduction_id: number | string | null;
  employee_no: string | null;
  item_code: string | null;
  reference_no: string | null;
  deduction_type: number | string | null;
  deduction_status: number | string | null;
  deduction_amount: number;
  principal_amount: number;
  reducing_balance: number;
  total_installment: number | string | null;
  installment_count: number | string | null;
  remaining_day: number | string | null;
  effective_month: string | null;
  effective_date: string | null;
  review_date: string | null;
  approve_date: string | null;
  settlement_date: string | null;
  is_own_deduction: boolean;
}

export interface CdasOfficialSnapshot {
  source: "CDAS_API";
  source_version: string;
  profile: CdasOfficialProfile;
  capacity: {
    max_available_deduction_amount: number;
    max_available_after_selected_deductions: number | null;
    assessed_available_amount: number;
    booking_allowed: boolean;
    status: "NEGATIVE_AVAILABLE" | "NO_HEADROOM" | "AVAILABLE";
    shortfall_amount: number;
  };
  decision: "REVIEW_REQUIRED";
  decision_message: string;
  reported_active_monthly_deductions: number;
  total_monthly_deductions: number;
  own_monthly_deductions: number;
  competitor_monthly_deductions: number;
  deductions: CdasOfficialDeduction[];
  own_bookings: CdasOfficialDeduction[];
  official_api: {
    affordability: number;
    own_deduction_status: number | null;
  };
}

export interface CdasOfficialRefreshResponse {
  source: "CDAS_API";
  checked_at: string | null;
  snapshot: CdasOfficialSnapshot;
  archive: {
    created: boolean;
    record: CdasAnalysisRecord;
  };
}

export interface CdasOfficialRefreshRequest {
  employee_no: string;
  own_deduction_status?: number;
}

export interface CdasBorrowerIntelligenceRequest {
  national_id: string;
  employee_no: string;
  own_deduction_status?: number;
}

export interface CdasExactIdentityLink {
  borrower_id: string;
  account_id: string;
  account_reference: string;
  client_name: string | null;
  national_id_masked: string;
  employee_no: string;
  verified: boolean;
  basis: "EXACT_NATIONAL_ID_AND_CDAS_EMPLOYEE_NO" | "EXACT_LOANHUB_NATIONAL_ID_PLUS_CDAS_EMPLOYEE_NO" | string;
  provider_national_id_present: boolean;
}

export interface CdasLoanHubLoanIntelligence {
  loan_id: string;
  loan_reference: string;
  status: string;
  balance: number;
  amount_paid: number;
  principal_amount: number;
  installment_amount: number;
  repayment_period: number;
  maturity_date: string | null;
  is_overdue: boolean;
  eligible_existing_obligation: boolean;
}

export interface CdasCollectionProposal {
  total_outstanding: number;
  available_affordability: number;
  suggested_monthly_deduction: number;
  estimated_collection_months: number | null;
  can_add_deduction: boolean;
  calculation_basis: string;
  warning: string;
  current_contractual_monthly_installments: number;
}

export interface CdasLoanHubBorrowerIntelligence {
  total_outstanding: number;
  approved_not_active_balance: number;
  active_or_defaulted_loan_count: number;
  approved_not_active_loan_count: number;
  loans: CdasLoanHubLoanIntelligence[];
  collection_proposal: CdasCollectionProposal;
}

export interface CdasBorrowerIntelligenceResponse {
  source: "CDAS_API";
  checked_at: string | null;
  identity: CdasExactIdentityLink;
  snapshot: CdasOfficialSnapshot;
  loanhub: CdasLoanHubBorrowerIntelligence;
  archive: {
    created: boolean;
    record: CdasAnalysisRecord;
  };
}

export interface CdasRegistrationPlan {
  ready: boolean;
  blockers: string[];
  loan_id: string;
  loan_reference: string;
  borrower_id: string;
  employee_no: string | null;
  deduction_amount: number;
  principal_amount: number;
  total_installment: number;
  effective_month: string;
  latest_affordability: number | null;
  daily_suggested_monthly_deduction: number | null;
  daily_estimated_collection_months: number | null;
  latest_monitor_date: string | null;
  existing_mandate: boolean;
  borrower_consent_required: boolean;
  item_code_required: boolean;
  reference_no_required: boolean;
  provider_write_performed: false;
  message: string;
}

export type CdasLoanLifecycleStatus =
  | "registration_pending"
  | "registration_failed"
  | "registration_retry_pending"
  | "registered"
  | "reviewed"
  | "approved"
  | "active"
  | "changed"
  | "cancelled"
  | "settled"
  | "auto_settled"
  | "deleted"
  | string;

export interface CdasLoanDeductionRegistrationRequest {
  loan_id: string;
  employee_no: string;
  item_code: string;
  reference_no: string;
  loan_policy?: number;
  deduction_amount: number;
  principal_amount: number;
  total_installment: number;
  effective_month: string;
  borrower_consent: boolean;
}

export interface CdasRegistrationRetryRequest {
  item_code: string;
  reference_no: string;
  loan_policy?: number;
  deduction_amount: number;
  principal_amount: number;
  total_installment: number;
  effective_month: string;
}

export type CdasLinkedActionRequestType = 3 | 4 | 5 | 6 | 9 | 10;

export interface CdasLinkedActionRequest {
  request_type: CdasLinkedActionRequestType;
}

export interface CdasLinkedModifyRequest {
  effective_date: string;
  deduction_amount?: number;
  principal_amount?: number;
  total_installment?: number;
}

export interface CdasLinkedSettlementRequest {
  effective_date: string;
  settlement_reason: 1 | 2 | 3 | 4;
}

export interface CdasOfficialMandateEvent {
  id: string;
  state_id: string;
  actor_user_id: string | null;
  event_type: string;
  request_type: number | null;
  request_snapshot: Record<string, unknown>;
  response_snapshot: Record<string, unknown>;
  provider_status_code: number | null;
  success: boolean;
  message: string | null;
  occurred_at: string | null;
}

export interface CdasOfficialMandateState {
  id: string;
  company_id?: string;
  mandate_id: string;
  application_id?: string | null;
  loan_id?: string | null;
  environment: "test" | "live" | string;
  employee_no?: string | null;
  employee_number?: string | null;
  deduction_id: number | null;
  item_code: string;
  reference_no: string;
  loan_policy: number;
  principal_amount: number | string;
  deduction_amount?: number | string | null;
  effective_month: string;
  total_installment?: number | null;
  cdas_status: number | null;
  lifecycle_status: CdasLoanLifecycleStatus;
  last_request_type: number | null;
  requires_reconciliation: boolean;
  last_error: string | null;
  last_synced_at: string | null;
  registered_at: string | null;
  reviewed_at: string | null;
  approved_at: string | null;
  settled_at: string | null;
  cancelled_at: string | null;
  mandate?: Record<string, unknown>;
  events?: CdasOfficialMandateEvent[];
  [key: string]: unknown;
}
