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
