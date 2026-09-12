import type { ManagedFile } from "@/types/files";

export type PaymentMethod =
  | "lelefapaygate"
  | "bank"
  | "swipped"
  | "golink"
  | "cdas"
  | "mpesa_wallet"
  | "mpesa_merchant"
  | "mpesa_agent"
  | "ecocash_wallet"
  | "ecocash_agent"
  | "ecocash_merchant"
  | "cash";

export type TreasuryDirection = "money_in" | "money_out";
export type TreasuryEntryType =
  | "opening_adjustment"
  | "owner_contribution"
  | "branch_funding"
  | "loan_collection"
  | "loan_disbursement"
  | "expense"
  | "branch_remittance"
  | "platform_charge"
  | "refund"
  | "manual_income"
  | "adjustment"
  | "other";
export type OpeningSourceType =
  | "previous_closing"
  | "owner_contribution"
  | "headquarters_funding"
  | "bank_float"
  | "cash_float"
  | "retained_funds"
  | "opening_adjustment"
  | "other";
export type TreasuryEntryApprovalStatus = "posted" | "pending" | "approved" | "rejected";
export type TreasuryDayStatus = "open" | "submitted" | "auto_submitted" | "reviewed" | "reopened";
export type BranchTransferStatus = "issued" | "received" | "cancelled";

export type PaymentMethodOption = { value: PaymentMethod; label: string; proof_recommended: boolean };

export type TreasurySettingsUpdate = {
  headquarters_branch_id: string | null;
  currency: string;
  timezone: string;
  auto_open_enabled: boolean;
  auto_open_time: string;
  auto_submit_enabled: boolean;
  auto_submit_time: string;
  require_proof_for_non_cash: boolean;
  allow_branch_reopen: boolean;
  expense_approval_threshold: number;
  dual_control_expenses: boolean;
};
export type TreasurySettings = TreasurySettingsUpdate & {
  id: string;
  company_id: string;
  created_at: string;
  updated_at: string;
};

export type ExpenseCategory = {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};
export type ExpenseCategoryCreate = { name: string; description?: string | null; is_active?: boolean };

export type OpeningSource = {
  id: string;
  company_id: string;
  branch_id: string;
  daily_ledger_id: string;
  source_type: OpeningSourceType;
  payment_method: PaymentMethod;
  amount: number;
  currency: string;
  description: string;
  source_reference: string;
  proof_reference: string | null;
  proof_url: string | null;
  proof_notes: string | null;
  transfer_id: string | null;
  is_system_generated: boolean;
  is_confirmed: boolean;
  confirmed_at: string | null;
  confirmed_by_user_id: string | null;
  recorded_by_user_id: string | null;
  is_voided: boolean;
  void_reason: string | null;
  voided_at: string | null;
  created_at: string;
  updated_at: string;
};
export type OpeningSourceCreate = {
  branch_id?: string | null;
  business_date?: string | null;
  source_type: Exclude<OpeningSourceType, "previous_closing">;
  payment_method: PaymentMethod;
  amount: number;
  currency?: string;
  description: string;
  source_reference?: string | null;
  proof_reference?: string | null;
  proof_url?: string | null;
  proof_notes?: string | null;
};

export type TreasuryEntry = {
  id: string;
  company_id: string;
  branch_id: string;
  daily_ledger_id: string;
  direction: TreasuryDirection;
  entry_type: TreasuryEntryType;
  payment_method: PaymentMethod;
  approval_status: TreasuryEntryApprovalStatus;
  requires_approval: boolean;
  idempotency_key: string | null;
  voucher_number: string | null;
  amount: number;
  currency: string;
  occurred_at: string;
  description: string;
  proof_reference: string | null;
  proof_url: string | null;
  proof_notes: string | null;
  external_reference: string | null;
  expense_category_id: string | null;
  payment_transaction_id: string | null;
  loan_id: string | null;
  borrower_id: string | null;
  transfer_id: string | null;
  counterparty_branch_id: string | null;
  recorded_by_user_id: string | null;
  approved_at: string | null;
  approved_by_user_id: string | null;
  rejected_at: string | null;
  rejected_by_user_id: string | null;
  rejection_reason: string | null;
  is_voided: boolean;
  void_reason: string | null;
  voided_at: string | null;
  created_at: string;
  updated_at: string;
};
export type TreasuryEntryCreate = {
  branch_id?: string | null;
  direction: TreasuryDirection;
  entry_type: TreasuryEntryType;
  payment_method: PaymentMethod;
  amount: number;
  currency?: string;
  occurred_at?: string | null;
  description: string;
  proof_reference?: string | null;
  proof_url?: string | null;
  proof_notes?: string | null;
  external_reference?: string | null;
  expense_category_id?: string | null;
  loan_id?: string | null;
  borrower_id?: string | null;
  idempotency_key?: string | null;
  voucher_number?: string | null;
};

export type BranchDailySubmission = {
  id: string;
  daily_ledger_id: string;
  company_id: string;
  branch_id: string;
  submitted_to_branch_id: string | null;
  business_date: string;
  sequence_number: number;
  is_automatic: boolean;
  opening_balance: number;
  total_money_in: number;
  total_money_out: number;
  closing_balance: number;
  declared_closing_balance: number | null;
  variance_amount: number;
  entry_count: number;
  pending_entry_count: number;
  channel_totals: Record<string, unknown>;
  expense_totals: Record<string, unknown>;
  opening_source_totals: Record<string, unknown>;
  submitted_at: string;
  submitted_by_user_id: string | null;
  notes: string | null;
  pdf_file_id: string | null;
  pdf_file: ManagedFile | null;
};
export type BranchDailySubmissionList = {
  items: BranchDailySubmission[];
  total: number;
  skip: number;
  limit: number;
};
export type BranchDailyLedger = {
  id: string;
  company_id: string;
  branch_id: string;
  business_date: string;
  status: TreasuryDayStatus;
  opening_balance: number;
  total_money_in: number;
  total_money_out: number;
  expected_closing_balance: number;
  declared_closing_balance: number | null;
  variance_amount: number;
  entry_count: number;
  pending_entry_count: number;
  submitted_at: string | null;
  auto_submitted_at: string | null;
  submitted_by_user_id: string | null;
  reviewed_at: string | null;
  reviewed_by_user_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  entries: TreasuryEntry[];
  opening_sources: OpeningSource[];
  submissions: BranchDailySubmission[];
};

export type MethodTotals = {
  method: PaymentMethod;
  opening_balance: number;
  money_in: number;
  money_out: number;
  net: number;
  closing_balance: number;
  entry_count: number;
};
export type OpeningSourceTotals = { source_type: OpeningSourceType; amount: number; source_count: number };
export type BranchDaySummary = {
  branch_id: string;
  branch_name: string;
  is_headquarters: boolean;
  ledger_id: string;
  status: TreasuryDayStatus;
  opening_balance: number;
  total_money_in: number;
  total_money_out: number;
  expected_closing_balance: number;
  declared_closing_balance: number | null;
  variance_amount: number;
  entry_count: number;
  pending_entry_count: number;
  submitted_at: string | null;
};
export type TreasuryDashboard = {
  business_date: string;
  currency: string;
  headquarters_branch_id: string | null;
  auto_open_enabled: boolean;
  auto_open_time: string;
  auto_submit_enabled: boolean;
  auto_submit_time: string;
  consolidated_previous_closing: number;
  owner_contributions: number;
  headquarters_funding: number;
  other_opening_sources: number;
  total_opening_balance: number;
  total_money_in: number;
  total_money_out: number;
  internal_transfer_out: number;
  external_money_out: number;
  consolidated_closing_balance: number;
  pending_expense_amount: number;
  method_totals: MethodTotals[];
  opening_source_totals: OpeningSourceTotals[];
  branches: BranchDaySummary[];
};

export type BranchFundingTransfer = {
  id: string;
  company_id: string;
  source_branch_id: string;
  target_branch_id: string;
  business_date: string;
  amount: number;
  currency: string;
  payment_method: PaymentMethod;
  reference: string;
  status: BranchTransferStatus;
  proof_reference: string | null;
  proof_url: string | null;
  notes: string | null;
  issued_at: string;
  issued_by_user_id: string | null;
  received_at: string | null;
  received_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};
export type BranchFundingTransferCreate = {
  target_branch_id: string;
  amount: number;
  payment_method: PaymentMethod;
  business_date?: string | null;
  proof_reference?: string | null;
  proof_url?: string | null;
  notes?: string | null;
};
export type TreasuryStatement = {
  date_from: string;
  date_to: string;
  opening_balance: number;
  total_money_in: number;
  total_money_out: number;
  closing_balance: number;
  method_totals: MethodTotals[];
  entries: TreasuryEntry[];
};


export type FinancialIntegritySeverity = "critical" | "warning" | "info";
export type FinancialIntegrityStatus = "healthy" | "warning" | "critical";
export type FinancialIntegrityIssue = {
  code: string;
  severity: FinancialIntegritySeverity;
  title: string;
  detail: string;
  record_type: string | null;
  record_id: string | null;
  branch_id: string | null;
  amount: number | null;
  repairable: boolean;
};
export type FinancialIntegrityReport = {
  business_date: string;
  branch_id: string | null;
  generated_at: string;
  status: FinancialIntegrityStatus;
  checks_run: number;
  issue_count: number;
  critical_count: number;
  warning_count: number;
  repairable_count: number;
  succeeded_payment_count: number;
  treasury_payment_count: number;
  posted_treasury_count: number;
  posted_journal_count: number;
  pending_expense_count: number;
  pending_expense_amount: number;
  proof_exception_count: number;
  ledger_variance_count: number;
  missing_treasury_count: number;
  missing_journal_count: number;
  unbalanced_journal_count: number;
  issues: FinancialIntegrityIssue[];
};
export type FinancialIntegrityRepair = {
  repaired_treasury_entries: number;
  repaired_journals: number;
  recalculated_ledgers: number;
  report: FinancialIntegrityReport;
};
