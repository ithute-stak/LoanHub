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
