export type MaturityRenewalPolicy = {
  id: string;
  company_id: string;
  enabled: boolean;
  rollover_basis: "outstanding_balance" | string;
  reuse_original_rate: boolean;
  renewal_rate_percent: number | null;
  reuse_original_term: boolean;
  renewal_term_months: number | null;
  include_processing_fee: boolean;
  grace_days: number;
  max_cycles: number | null;
  notify_borrower: boolean;
  configured_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type MaturityRenewalLoanOverview = {
  id: string;
  loan_reference: string;
  borrower_name: string;
  branch_id: string | null;
  balance: number;
  installment_amount: number;
  maturity_date: string | null;
  original_maturity_date: string | null;
  renewal_cycle_count: number;
  automatic_renewal_enabled: boolean | null;
  effective_auto_renewal: boolean;
  renewal_stopped_at: string | null;
  renewal_stop_reason: string | null;
  is_matured: boolean;
  latest_cycle: {
    cycle_number: number;
    opening_balance: number;
    total_repayable: number;
    installment_amount: number;
    started_on: string;
    maturity_date: string;
  } | null;
};

export type MaturityRecoveryOverview = {
  policy: MaturityRenewalPolicy;
  summary: {
    active_facilities: number;
    matured_with_balance: number;
    auto_renewing: number;
    renewal_stopped: number;
  };
  loans: MaturityRenewalLoanOverview[];
};
