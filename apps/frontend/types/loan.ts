import type { CashTransaction } from "@/types/payment";
import type { PaymentMethod } from "@/types/expenseManagement";
import type { ManagedFile } from "@/types/files";

export type LoanStatus = "pending" | "approved" | "active" | "completed" | "defaulted" | "rejected" | "cancelled";
export type RepaymentType = "daily" | "weekly" | "monthly" | "custom";
export type RiskLevel = "low" | "medium" | "high";
export type InstallmentStatus = "pending" | "partially_paid" | "paid" | "overdue" | "waived";

export type RepaymentInstallment = {
  id: string;
  renewal_cycle_id: string | null;
  superseded_by_cycle_id: string | null;
  is_superseded: boolean;
  superseded_at: string | null;
  installment_number: number;
  due_date: string;
  principal_due: number;
  interest_due: number;
  fee_due: number;
  total_due: number;
  paid_amount: number;
  status: InstallmentStatus;
  paid_at: string | null;
};

export type InterestMethod =
  | "micro_loan"
  | "simple_interest"
  | "flat_rate"
  | "compound_interest"
  | "reducing_balance"
  | "daily_accrual_reducing";

export type MicroLoanStep = {
  month: number;
  opening_balance: number;
  amount_after_rate: number;
  component_amount: number;
  carried_balance: number;
};

export type InterestSegment = {
  period_start: string;
  period_end: string;
  days: number;
  days_in_month: number;
  interest: number;
};

export type LoanCalculationScheduleRow = {
  installment_number: number;
  period_start: string;
  due_date: string;
  opening_balance: number;
  principal_due: number;
  interest_due: number;
  fee_due: number;
  total_due: number;
  closing_balance: number;
  interest_segments: InterestSegment[];
};

export type LoanCalculation = {
  method: InterestMethod;
  method_label: string;
  rate_basis: string;
  principal: number;
  rate_percent: number;
  months: number;
  processing_fee: number;
  interest_start_date: string;
  first_payment_date: string;
  maturity_date: string;
  total_interest: number;
  total_repayable: number;
  monthly_installment: number;
  schedule_amounts: number[];
  schedule: LoanCalculationScheduleRow[];
  steps: MicroLoanStep[];
};

/** Backward-compatible alias retained for existing imports. */
export type MicroLoanCalculation = LoanCalculation;


export type LoanRenewalCycle = {
  id: string;
  cycle_number: number;
  status: string;
  automatic: boolean;
  opening_balance: number;
  rollover_basis: string;
  rate_percent: number;
  processing_fee: number;
  term_months: number;
  calculation_method: string;
  installment_amount: number;
  total_repayable: number;
  started_on: string;
  maturity_date: string;
  rolled_at: string;
};

export type Loan = {
  id: string;
  loan_request_id: string | null;
  loan_offer_id: string | null;
  company_id: string;
  branch_id: string | null;
  borrower_id: string;
  loan_reference: string;
  origination_channel: string;
  principal_amount: number;
  interest_rate: number;
  processing_fee: number;
  total_repayable: number;
  repayment_type: RepaymentType;
  repayment_period: number;
  installment_amount: number;
  calculation_method: InterestMethod | string;
  calculation_breakdown: Record<string, unknown>;
  approved_at: string | null;
  disbursed_at: string | null;
  first_payment_due: string | null;
  maturity_date: string | null;
  amount_paid: number;
  balance: number;
  status: LoanStatus;
  risk_level: RiskLevel;
  is_overdue: boolean;
  automatic_renewal_enabled: boolean | null;
  renewal_cycle_count: number;
  original_maturity_date: string | null;
  last_renewed_at: string | null;
  renewal_stopped_at: string | null;
  renewal_stop_reason: string | null;
  is_top_up?: boolean;
  parent_loan_id?: string | null;
  top_up_settlement_amount?: number;
  top_up_cash_amount?: number;
  installments: RepaymentInstallment[];
  renewal_cycles: LoanRenewalCycle[];
};

export type CashRepaymentPreview = {
  loan_id: string;
  loan_reference: string;
  borrower_name: string;
  current_installment_number: number;
  current_due_date: string;
  expected_monthly_installment: number;
  installment_outstanding_before: number;
  amount_tendered: number;
  amount_applied: number;
  change_amount: number;
  forward_amount: number;
  installment_outstanding_after: number;
  loan_balance_before: number;
  loan_balance_after: number;
  installments_fully_covered: number;
  payment_completes_loan: boolean;
  early_settlement_required: boolean;
  future_installments_in_payoff: number;
};

export type CashPaymentResult = {
  payment_id: string;
  payment_method: PaymentMethod;
  status: "pending" | "processing" | "succeeded" | "failed" | "cancelled" | "reversed";
  provider_reference: string;
  proof_reference: string | null;
  receipt_number: string | null;
  receipt_file: ManagedFile | null;
  cash_transaction: CashTransaction | null;
  preview: CashRepaymentPreview | null;
};

export type PaymentResult = CashPaymentResult;

export type OverpaymentAction = "give_change" | "carry_forward";


export type EarlySettlementStatus =
  | "quoted"
  | "processing"
  | "settled"
  | "failed"
  | "expired"
  | "reversed";

export type EarlySettlement = {
  id: string;
  company_id: string;
  borrower_id: string;
  loan_id: string;
  payment_id: string | null;
  quoted_by_user_id: string | null;
  settled_by_user_id: string | null;
  status: EarlySettlementStatus;
  settlement_date: string;
  quote_expires_at: string;
  calculation_method: InterestMethod | string;
  original_term_months: number;
  chargeable_periods: number;
  original_maturity_date: string | null;
  original_principal: number;
  original_total_repayable: number;
  original_balance: number;
  original_amount_paid: number;
  original_total_interest: number;
  earned_interest: number;
  unearned_interest_rebate: number;
  processing_fee_retained: number;
  payments_received: number;
  revised_total_repayable: number;
  settlement_amount: number;
  settlement_principal: number;
  settlement_interest: number;
  settlement_fees: number;
  overpayment_credit: number;
  borrower_acknowledged: boolean;
  agreement_note: string | null;
  agreement_reference: string | null;
  calculation_snapshot: Record<string, unknown>;
  installment_snapshot: Array<Record<string, unknown>>;
  settled_at: string | null;
  reversed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type EarlySettlementPaymentResult = {
  settlement: EarlySettlement;
  payment: CashPaymentResult;
};

export type LoanPaymentSlip = {
  id: string;
  payment_id: string;
  receipt_number: string;
  payment_purpose: string;
  payment_method: string;
  amount: number;
  provider_reference: string | null;
  verification_code: string;
  completed_at: string | null;
  pdf_file_id: string | null;
};

export type LoanDocumentKind = "loan-information" | "repayment-schedule" | "payment-history";
