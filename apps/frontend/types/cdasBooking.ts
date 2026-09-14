export type CdasBookingDecision = "ALREADY_BOOKED" | "BOOK_NOW" | "WAIT_UNTIL" | "REVIEW_REQUIRED";
export type CdasRowBookingStatus = "BOOKED_BY_US" | "BOOK_NOW" | "WAIT" | "NOT_ACTIVE" | "DATA_CONFLICT" | "DATA_INCOMPLETE";
export type CdasDataQualityStatus = "OK" | "DATE_CONFLICT" | "MISSING_EXPIRY";
export type CdasOpportunityState = "UPCOMING" | "BOOK_NOW" | "BOOKED";
export type CdasCapacityStatus = "UNKNOWN" | "NEGATIVE_AVAILABLE" | "NO_HEADROOM" | "AVAILABLE";

export interface CdasBookingAnalyzeRequest {
  raw_text: string;
  booking_lead_months: number;
  own_item_codes: string[];
  own_agency_names: string[];
  as_of?: string;
}

export interface CdasBookingMonitorRequest extends CdasBookingAnalyzeRequest {
  client_name?: string;
  client_reference?: string;
  alert_lead_days: number;
}

export interface CdasClientProfile {
  employee_no: string | null;
  name: string | null;
  surname: string | null;
  full_name: string | null;
  gender: string | null;
  date_of_birth: string | null;
  nid: string | null;
  employer: string | null;
  joining_date: string | null;
  end_date: string | null;
  early_retirement_date: string | null;
  compulsory_retirement_date: string | null;
}

export interface CdasCapacitySnapshot {
  max_available_deduction_amount: number | null;
  max_available_after_selected_deductions: number | null;
  status: CdasCapacityStatus;
  shortfall_amount: number;
}

export interface CdasRetirementAnalysis {
  early_retirement_date: string | null;
  compulsory_retirement_date: string | null;
  days_until_early_retirement: number | null;
  days_until_compulsory_retirement: number | null;
}

export interface CdasApplicationContext {
  new_deduction_agency_code: string | null;
  new_deduction_agency_name: string | null;
  current_cdas_agency_code: string | null;
  current_cdas_agency_name: string | null;
  agency_auto_detected: boolean;
}

export interface CdasDeductionAnalysis {
  item_code: string;
  agency_name: string;
  deduction_amount: number;
  effective_date: string;
  expiry_date: string | null;
  reference_no: string;
  status: string;
  reported_active: boolean;
  is_own_booking: boolean;
  is_active: boolean;
  excluded_from_booking: boolean;
  data_quality_status: CdasDataQualityStatus;
  data_quality_message: string | null;
  elapsed_months: number | null;
  months_to_expiry: number | null;
  scheduled_deduction_months: number | null;
  booking_open_date: string | null;
  months_until_booking: number | null;
  booking_status: CdasRowBookingStatus;
}

export interface CdasBookingAnalysis {
  as_of: string;
  booking_lead_months: number;
  profile: CdasClientProfile;
  capacity: CdasCapacitySnapshot;
  retirement_analysis: CdasRetirementAnalysis;
  application_context: CdasApplicationContext;
  decision: CdasBookingDecision;
  decision_message: string;
  next_possible_booking_date: string | null;
  reported_active_monthly_deductions: number;
  total_monthly_deductions: number;
  own_monthly_deductions: number;
  competitor_monthly_deductions: number;
  excluded_monthly_deductions: number;
  data_quality_issue_count: number;
  data_quality_issues: CdasDeductionAnalysis[];
  own_bookings: CdasDeductionAnalysis[];
  opportunity: CdasDeductionAnalysis | null;
  deductions: CdasDeductionAnalysis[];
}

export interface CdasBookingOpportunity {
  id: string;
  client_name: string | null;
  client_reference: string | null;
  status: string;
  state: CdasOpportunityState;
  booking_lead_months: number;
  alert_lead_days: number;
  booking_open_date: string | null;
  alert_start_date: string | null;
  days_until_booking: number | null;
  opportunity_agency_name: string | null;
  opportunity_item_code: string | null;
  opportunity_reference_no: string | null;
  opportunity_effective_date: string | null;
  opportunity_expiry_date: string | null;
  opportunity_deduction_amount: number;
  total_monthly_deductions: number;
  own_monthly_deductions: number;
  competitor_monthly_deductions: number;
  analysis_snapshot: CdasBookingAnalysis;
  booked_at: string | null;
  booked_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CdasBookingOpportunityList {
  items: CdasBookingOpportunity[];
  total: number;
}
