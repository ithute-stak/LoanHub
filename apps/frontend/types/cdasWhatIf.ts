export type CdasWhatIfStatus =
  | "FITS_NOW"
  | "FITS_AFTER_RELEASE"
  | "EXCEEDS_KNOWN_CAPACITY"
  | "CAPACITY_UNKNOWN";

export type CdasWhatIfConfidence = "HIGH" | "INDICATIVE" | "LOW" | "REVIEW_REQUIRED";

export interface CdasWhatIfRequest {
  opportunity_id: string;
  proposed_installment?: number;
  proposed_amount?: number;
  term_months?: number;
  annual_interest_rate?: number;
}

export interface CdasWhatIfReleaseDeduction {
  item_code: string | null;
  agency_name: string | null;
  reference_no: string | null;
  deduction_amount: number;
  expiry_date: string | null;
}

export interface CdasWhatIfReleaseWindow {
  booking_date: string;
  released_monthly_deduction: number;
  cumulative_release: number;
  deductions: CdasWhatIfReleaseDeduction[];
}

export interface CdasWhatIfResult {
  as_of: string;
  opportunity_id: string;
  client_name: string | null;
  client_reference: string | null;
  agency_name: string | null;
  decision: string | null;
  data_quality_issue_count: number;
  calculation_method: "DIRECT_INSTALLMENT" | "AMORTIZED_PAYMENT";
  scenario: {
    proposed_installment: number;
    proposed_amount: number | null;
    term_months: number | null;
    annual_interest_rate: number | null;
  };
  current_capacity: number | null;
  fits_now: boolean;
  remaining_capacity: number | null;
  shortfall: number | null;
  status: CdasWhatIfStatus;
  requires_waiting_for_release: boolean;
  earliest_fit_date: string | null;
  earliest_fit_capacity: number | null;
  confidence: CdasWhatIfConfidence;
  release_windows: CdasWhatIfReleaseWindow[];
  warnings: string[];
  projection_note: string;
}
