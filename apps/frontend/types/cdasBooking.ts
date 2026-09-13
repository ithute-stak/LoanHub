export type CdasBookingDecision = "ALREADY_BOOKED" | "BOOK_NOW" | "WAIT_UNTIL";
export type CdasRowBookingStatus = "BOOKED_BY_US" | "BOOK_NOW" | "WAIT" | "NOT_ACTIVE";
export type CdasBookingMonitorPhase = "UPCOMING" | "ALERTING" | "BOOK_NOW" | "BOOKED";

export interface CdasBookingAnalyzeRequest {
  raw_text: string;
  booking_lead_months: number;
  own_item_codes: string[];
  own_agency_names: string[];
  as_of?: string;
}

export interface CdasDeductionAnalysis {
  item_code: string;
  agency_name: string;
  deduction_amount: number;
  effective_date: string;
  expiry_date: string;
  reference_no: string;
  status: string;
  is_own_booking: boolean;
  is_active: boolean;
  elapsed_months: number;
  months_to_expiry: number;
  scheduled_deduction_months: number;
  booking_open_date: string;
  months_until_booking: number;
  booking_status: CdasRowBookingStatus;
}

export interface CdasBookingAnalysis {
  as_of: string;
  booking_lead_months: number;
  decision: CdasBookingDecision;
  decision_message: string;
  next_possible_booking_date: string | null;
  total_monthly_deductions: number;
  own_monthly_deductions: number;
  competitor_monthly_deductions: number;
  own_bookings: CdasDeductionAnalysis[];
  opportunity: CdasDeductionAnalysis | null;
  deductions: CdasDeductionAnalysis[];
}

export interface CdasBookingMonitorCreate {
  client_name: string;
  client_reference?: string | null;
  item_code: string;
  agency_name: string;
  deduction_amount: number;
  effective_date: string;
  expiry_date: string;
  reference_no?: string | null;
  source_status: string;
  booking_lead_months: number;
}

export interface CdasBookingMonitor {
  id: string;
  client_name: string;
  client_reference: string | null;
  item_code: string;
  agency_name: string;
  deduction_amount: number;
  effective_date: string;
  expiry_date: string;
  reference_no: string | null;
  source_status: string;
  booking_lead_months: number;
  booking_open_date: string;
  alert_start_date: string;
  phase: CdasBookingMonitorPhase;
  days_until_booking: number;
  booked_at: string | null;
  created_at: string;
}
