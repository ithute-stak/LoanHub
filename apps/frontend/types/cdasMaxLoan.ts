export type CdasMaxLoanStatus = "CALCULATED" | "NO_CAPACITY" | "CAPACITY_UNKNOWN";
export type CdasMaxLoanConfidence = "HIGH" | "LOW" | "REVIEW_REQUIRED";

export interface CdasMaxLoanRequest {
  opportunity_id: string;
  term_months: number;
  annual_interest_rate: number;
  monthly_service_fee?: number;
  insurance_percent?: number;
}

export interface CdasMaxLoanResult {
  opportunity_id: string;
  client_name: string | null;
  client_reference: string | null;
  agency_name: string | null;
  decision: string | null;
  data_quality_issue_count: number;
  status: CdasMaxLoanStatus;
  confidence: CdasMaxLoanConfidence;
  inputs: {
    term_months: number;
    annual_interest_rate: number;
    monthly_service_fee: number;
    insurance_percent: number;
  };
  available_deduction_capacity: number | null;
  installment_budget: number | null;
  max_financed_balance: number | null;
  insurance_amount: number | null;
  max_principal: number | null;
  projected_monthly_total: number | null;
  warnings: string[];
  calculation_note: string;
}
