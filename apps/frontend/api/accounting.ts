import { api } from "@/lib/api";
import type {
  AccountingAccount,
  FinancialBooksPack,
  FinancialStatement,
  JournalEntry,
  TrialBalance,
} from "@/types/accounting";

export type AccountingFilters = {
  companyId?: string;
  branchId?: string | null;
  fromDate?: string;
  toDate?: string;
  status?: string;
  skip?: number;
  limit?: number;
};

function params(filters?: AccountingFilters) {
  return {
    company_id: filters?.companyId,
    branch_id: filters?.branchId || undefined,
    from_date: filters?.fromDate,
    to_date: filters?.toDate,
    status: filters?.status,
    skip: filters?.skip,
    limit: filters?.limit,
  };
}

export async function bootstrapAccounting(companyId?: string): Promise<AccountingAccount[]> {
  return (await api.post<AccountingAccount[]>("/accounting/bootstrap", null, { params: { company_id: companyId } })).data;
}

export async function listAccountingAccounts(companyId?: string): Promise<AccountingAccount[]> {
  return (await api.get<AccountingAccount[]>("/accounting/accounts", { params: { company_id: companyId } })).data;
}

export async function listJournalEntries(filters?: AccountingFilters): Promise<JournalEntry[]> {
  return (await api.get<JournalEntry[]>("/accounting/journal-entries", { params: params(filters) })).data;
}

export async function createJournalEntry(payload: {
  entry_date: string;
  branch_id?: string | null;
  description: string;
  reference_type?: string | null;
  reference_id?: string | null;
  lines: Array<{ account_id: string; description?: string; debit: number; credit: number }>;
}, companyId?: string): Promise<JournalEntry> {
  return (await api.post<JournalEntry>("/accounting/journal-entries", payload, { params: { company_id: companyId } })).data;
}

export async function postJournalEntry(entryId: string, companyId?: string): Promise<JournalEntry> {
  return (await api.post<JournalEntry>(`/accounting/journal-entries/${entryId}/post`, null, { params: { company_id: companyId } })).data;
}

export async function getTrialBalance(filters?: AccountingFilters): Promise<TrialBalance> {
  return (await api.get<TrialBalance>("/accounting/trial-balance", { params: params(filters) })).data;
}

export async function getProfitAndLoss(filters?: AccountingFilters): Promise<FinancialStatement> {
  return (await api.get<FinancialStatement>("/accounting/profit-and-loss", { params: params(filters) })).data;
}

export async function getBalanceSheet(filters?: AccountingFilters): Promise<FinancialStatement> {
  return (await api.get<FinancialStatement>("/accounting/balance-sheet", { params: params(filters) })).data;
}


export async function getFinancialBooks(filters: {
  companyId?: string;
  branchId?: string | null;
  fromDate: string;
  toDate: string;
  includeLedgerDetail?: boolean;
}): Promise<FinancialBooksPack> {
  return (await api.get<FinancialBooksPack>("/accounting/financial-books", {
    params: {
      company_id: filters.companyId,
      branch_id: filters.branchId || undefined,
      from_date: filters.fromDate,
      to_date: filters.toDate,
      include_ledger_detail: filters.includeLedgerDetail ?? true,
    },
  })).data;
}

export async function getLatestPreparedFinancialBooks(companyId?: string): Promise<{
  available: boolean;
  reference?: string;
  prepared_at?: string | null;
  timezone?: string;
  schedule?: string;
  from_date?: string | null;
  to_date?: string | null;
  books: FinancialBooksPack | null;
}> {
  return (await api.get("/accounting/financial-books/latest", {
    params: { company_id: companyId },
  })).data;
}


export async function createOpeningBalanceMigration(payload: {
  entry_date: string;
  description: string;
  migration_reference: string;
  branch_id?: string | null;
  lines: Array<{ account_id: string; description?: string; debit: number; credit: number }>;
}, companyId?: string): Promise<JournalEntry> {
  return (await api.post<JournalEntry>("/accounting/opening-balances", payload, {
    params: { company_id: companyId },
  })).data;
}



export type MonthEndControlPack = {
  period_start: string;
  period_end: string;
  branch_id?: string | null;
  ready_to_lock: boolean;
  failed_checks: string[];
  checks: Record<string, boolean>;
  loan_receivables_subledger: {
    ledger_account_code: string;
    folio_count: number;
    folio_total: number;
    control_source_total: number;
    general_ledger_total: number;
    folio_to_control_variance: number;
    control_to_gl_variance: number;
    balanced: boolean;
    folios: Array<{
      loan_id: string;
      loan_reference: string;
      folio_number: string;
      borrower_id: string;
      branch_id?: string | null;
      status: string;
      operational_balance: number;
      source_principal_outstanding: number;
      written_off: boolean;
    }>;
  };
  vat_reconciliation: {
    closing_input_vat_receivable: number;
    closing_output_vat_payable: number;
    net_vat_payable: number;
    net_vat_receivable: number;
    ledger_balanced: boolean;
    policy_note: string;
  };
  fixed_asset_depreciation: {
    asset_count_due: number;
    total_due: number;
    assets: Array<{
      asset_id: string;
      reference?: string | null;
      name: string;
      branch_id?: string | null;
      amount_due: number;
      carrying_amount_before: number;
      last_depreciation_date?: string | null;
    }>;
  };
  adjustment_register: {
    posted_count: number;
    draft_count: number;
    entries: Array<{
      journal_entry_id: string;
      entry_number: string;
      entry_date: string;
      reference_type?: string | null;
      reference_id?: string | null;
      description: string;
      status: string;
      amount: number;
    }>;
  };
  policy_note: string;
};

export async function getMonthEndControlPack(filters: {
  companyId?: string;
  branchId?: string | null;
  periodStart: string;
  periodEnd: string;
}): Promise<MonthEndControlPack> {
  return (await api.get<MonthEndControlPack>("/accounting/month-end-control-pack", {
    params: {
      company_id: filters.companyId,
      branch_id: filters.branchId || undefined,
      period_start: filters.periodStart,
      period_end: filters.periodEnd,
    },
  })).data;
}


export async function createMonthEndAdjustmentDraft(payload: {
  adjustment_type: "accrual" | "prepayment" | "accrued_income";
  amount: number;
  account_code: string;
  description: string;
  entry_date: string;
  branch_id?: string | null;
  reference_id?: string;
  reversal_date?: string | null;
}, companyId?: string): Promise<JournalEntry> {
  return (await api.post<JournalEntry>("/accounting/month-end-adjustments/drafts", payload, {
    params: { company_id: companyId },
  })).data;
}

export async function prepareMonthEndReversalDrafts(filters: {
  companyId?: string;
  branchId?: string | null;
  asOf: string;
}): Promise<{
  prepared_count: number;
  waiting_for_source_post_count: number;
  prepared: Array<{ journal_entry_id: string; entry_number: string; existing: boolean }>;
}> {
  return (await api.post("/accounting/month-end-adjustments/prepare-reversals", null, {
    params: {
      company_id: filters.companyId,
      branch_id: filters.branchId || undefined,
      as_of: filters.asOf,
    },
  })).data;
}

export async function depreciateAssetsForPeriod(filters: {
  companyId?: string;
  branchId?: string | null;
  periodStart: string;
  periodEnd: string;
}): Promise<{ posted: Array<{ asset_id: string; journal_entry_id: string; amount: number }>; total_depreciation: number }> {
  return (await api.post("/accounting/assets/depreciate-period", {
    period_start: filters.periodStart,
    period_end: filters.periodEnd,
  }, {
    params: {
      company_id: filters.companyId,
      branch_id: filters.branchId || undefined,
    },
  })).data;
}


export type FinancialPlan = {
  id: string;
  reference: string;
  name: string;
  description?: string | null;
  status: string;
  branch_id?: string | null;
  plan_type: "budget" | "forecast";
  fiscal_start: string;
  fiscal_end: string;
  version: number;
  source_plan_id?: string | null;
  approved_by_user_id?: string | null;
  approved_at?: string | null;
  total_planned: number;
  lines: Array<{
    account_code: string;
    account_name: string;
    account_type: string;
    period_start: string;
    amount: number;
    note?: string | null;
    basis?: string;
  }>;
};

export type FinancialPlanVariance = {
  plan: FinancialPlan;
  as_of: string;
  planned_total: number;
  actual_total: number;
  net_variance: number;
  intelligence_policy: string;
  top_variances: Array<{
    account_code: string;
    account_name: string;
    account_type: string;
    period: string;
    planned: number;
    actual: number;
    variance: number;
    variance_percent?: number | null;
    favorability: "favorable" | "unfavorable" | "neutral";
    explanation: string;
    cause_inferred: false;
  }>;
};


export type TreasuryCommitment = {
  id: string;
  reference: string;
  title: string;
  description?: string | null;
  status: string;
  branch_id?: string | null;
  category: string;
  due_date: string;
  amount: number;
};

export type TreasuryCashForecast = {
  from_date: string;
  to_date: string;
  branch_id?: string | null;
  opening_liquidity: {
    cash: number;
    bank: number;
    electronic_clearing: number;
    available_cash: number;
    gross_liquid_funds: number;
  };
  scenario: {
    collection_rate: number;
    obligation_rate: number;
    unexpected_outflow: number;
    minimum_cash: number;
  };
  total_expected_collections: number;
  total_approved_obligations: number;
  projected_closing_cash: number;
  minimum_projected_cash: number;
  breach_count: number;
  breaches: Array<{ date: string; projected_closing_cash: number; minimum_cash: number; shortfall: number }>;
  daily_forecast: Array<{
    date: string;
    opening_cash: number;
    expected_collections: number;
    approved_obligations: number;
    projected_closing_cash: number;
    minimum_cash_breach: boolean;
  }>;
  policy_note: string;
};

export type TreasuryStressTest = {
  from_date: string;
  to_date: string;
  minimum_cash: number;
  policy_note: string;
  scenarios: Array<{
    scenario: string;
    collection_rate: number;
    obligation_rate: number;
    projected_closing_cash: number;
    minimum_projected_cash: number;
    breach_count: number;
    first_breach?: { date: string; shortfall: number } | null;
  }>;
};

export async function listTreasuryCommitments(companyId?: string, branchId?: string | null): Promise<TreasuryCommitment[]> {
  return (await api.get<TreasuryCommitment[]>("/accounting/treasury/commitments", {
    params: { company_id: companyId, branch_id: branchId || undefined },
  })).data;
}

export async function createTreasuryCommitment(payload: {
  title: string;
  category: "expense" | "payroll" | "provider" | "tax" | "refund" | "capital" | "other";
  due_date: string;
  amount: number;
  branch_id?: string | null;
  description?: string;
}, companyId?: string): Promise<TreasuryCommitment> {
  return (await api.post<TreasuryCommitment>("/accounting/treasury/commitments", payload, {
    params: { company_id: companyId },
  })).data;
}

export async function approveTreasuryCommitment(commitmentId: string, companyId?: string): Promise<TreasuryCommitment> {
  return (await api.post<TreasuryCommitment>(`/accounting/treasury/commitments/${commitmentId}/approve`, null, {
    params: { company_id: companyId },
  })).data;
}

export async function getTreasuryCashForecast(payload: {
  from_date: string;
  to_date: string;
  minimum_cash: number;
  collection_rate: number;
  obligation_rate: number;
  unexpected_outflow: number;
  branch_id?: string | null;
}, companyId?: string): Promise<TreasuryCashForecast> {
  return (await api.post<TreasuryCashForecast>("/accounting/treasury/cash-forecast", payload, {
    params: { company_id: companyId },
  })).data;
}

export async function getTreasuryStressTest(payload: {
  from_date: string;
  to_date: string;
  minimum_cash: number;
  branch_id?: string | null;
}, companyId?: string): Promise<TreasuryStressTest> {
  return (await api.post<TreasuryStressTest>("/accounting/treasury/stress-test", {
    ...payload,
    collection_rate: 1,
    obligation_rate: 1,
    unexpected_outflow: 0,
  }, {
    params: { company_id: companyId },
  })).data;
}


export type AuditJournalReviewEntry = {
  journal_entry_id: string;
  entry_number: string;
  entry_date: string;
  description: string;
  reference_type?: string | null;
  reference_id?: string | null;
  amount: number;
  flags: string[];
  evidence_files: Array<{
    file_id: string;
    reference: string;
    name: string;
    mime_type: string;
    size_bytes: number;
    checksum_sha256: string;
    scan_status: string;
    is_encrypted: boolean;
    is_confidential: boolean;
  }>;
  review_status: string;
};

export type AccountingAuditCompliancePack = {
  period_start: string;
  period_end: string;
  branch_id?: string | null;
  controls: Record<string, boolean>;
  control_pass_count: number;
  control_fail_count: number;
  audit_integrity: {
    sealed_event_count: number;
    chain_valid: boolean;
    broken_event_id?: string | null;
    company_period_event_count: number;
    severity_counts: Record<string, number>;
  };
  journal_review: {
    journal_count: number;
    flagged_count: number;
    large_amount_threshold: number;
    evidence_required_count: number;
    evidence_missing_count: number;
    policy_note: string;
    flagged_entries: AuditJournalReviewEntry[];
  };
  audit_sample: AuditJournalReviewEntry[];
  vat_control: {
    closing_input_vat_receivable: number;
    closing_output_vat_payable: number;
    net_vat_payable: number;
    net_vat_receivable: number;
    ledger_balanced: boolean;
    policy_note: string;
  };
  corporation_tax_control: {
    closing_tax_expense: number;
    closing_tax_payable: number;
    control_flags: Record<string, boolean>;
    policy_note: string;
  };
  statutory_assessment: {
    status: string;
    jurisdiction: string;
    note: string;
  };
};

export async function getAccountingAuditCompliancePack(filters: {
  companyId?: string;
  branchId?: string | null;
  periodStart: string;
  periodEnd: string;
}): Promise<AccountingAuditCompliancePack> {
  return (await api.get<AccountingAuditCompliancePack>("/accounting/audit-compliance-pack", {
    params: {
      company_id: filters.companyId,
      branch_id: filters.branchId || undefined,
      period_start: filters.periodStart,
      period_end: filters.periodEnd,
    },
  })).data;
}

export async function listFinancialPlans(companyId?: string, branchId?: string | null): Promise<FinancialPlan[]> {
  return (await api.get<FinancialPlan[]>("/accounting/financial-plans", {
    params: { company_id: companyId, branch_id: branchId || undefined },
  })).data;
}

export async function createFinancialPlan(payload: {
  name: string;
  plan_type: "budget" | "forecast";
  fiscal_start: string;
  fiscal_end: string;
  branch_id?: string | null;
  notes?: string;
  lines: Array<{ account_code: string; period_start: string; amount: number; note?: string }>;
}, companyId?: string): Promise<FinancialPlan> {
  return (await api.post<FinancialPlan>("/accounting/financial-plans", payload, {
    params: { company_id: companyId },
  })).data;
}

export async function approveFinancialPlan(planId: string, companyId?: string): Promise<FinancialPlan> {
  return (await api.post<FinancialPlan>(`/accounting/financial-plans/${planId}/approve`, null, {
    params: { company_id: companyId },
  })).data;
}

export async function getFinancialPlanVariance(planId: string, asOf: string, companyId?: string, branchId?: string | null): Promise<FinancialPlanVariance> {
  return (await api.get<FinancialPlanVariance>(`/accounting/financial-plans/${planId}/variance`, {
    params: { company_id: companyId, branch_id: branchId || undefined, as_of: asOf },
  })).data;
}

export async function createRollingForecast(planId: string, cutoffDate: string, name: string, companyId?: string): Promise<FinancialPlan> {
  return (await api.post<FinancialPlan>(`/accounting/financial-plans/${planId}/rolling-forecast`, null, {
    params: { company_id: companyId, cutoff_date: cutoffDate, name },
  })).data;
}

export async function exportFinancialBooks(filters: {
  companyId?: string;
  branchId?: string | null;
  fromDate: string;
  toDate: string;
  format: "pdf" | "xlsx";
}): Promise<Blob> {
  return (await api.get("/accounting/financial-books/export", {
    params: {
      company_id: filters.companyId,
      branch_id: filters.branchId || undefined,
      from_date: filters.fromDate,
      to_date: filters.toDate,
      format: filters.format,
    },
    responseType: "blob",
  })).data as Blob;
}

export async function previewYearEndClosing(filters: {
  companyId?: string;
  branchId?: string | null;
  financialYearStart: string;
  financialYearEnd: string;
}): Promise<Record<string, unknown>> {
  return (await api.get("/accounting/year-end-closing/preview", {
    params: {
      company_id: filters.companyId,
      branch_id: filters.branchId || undefined,
      financial_year_start: filters.financialYearStart,
      financial_year_end: filters.financialYearEnd,
    },
  })).data as Record<string, unknown>;
}

export async function createYearEndClosingDraft(filters: {
  companyId?: string;
  branchId?: string | null;
  financialYearStart: string;
  financialYearEnd: string;
}): Promise<JournalEntry> {
  return (await api.post<JournalEntry>("/accounting/year-end-closing", null, {
    params: {
      company_id: filters.companyId,
      branch_id: filters.branchId || undefined,
      financial_year_start: filters.financialYearStart,
      financial_year_end: filters.financialYearEnd,
    },
  })).data;
}

export async function cancelYearEndClosingDraft(entryId: string, companyId?: string): Promise<void> {
  await api.delete(`/accounting/year-end-closing/${entryId}`, {
    params: { company_id: companyId },
  });
}
