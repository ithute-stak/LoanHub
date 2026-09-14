export type CdasMaxLoanStatus = "CALCULATED" | "NO_CAPACITY";

export interface CdasMaxLoanRequest {
  monthly_capacity: number;
  term_months: number;
  annual_interest_rate: number;
  monthly_service_fee?: number;
  insurance_percent?: number;
}

export interface CdasMaxLoanResult {
  status: CdasMaxLoanStatus;
  inputs: {
    monthly_capacity: number;
    term_months: number;
    annual_interest_rate: number;
    monthly_service_fee: number;
    insurance_percent: number;
  };
  installment_budget: number;
  max_financed_balance: number;
  insurance_amount: number;
  max_principal: number;
  projected_monthly_total: number;
  calculation_note: string;
}
