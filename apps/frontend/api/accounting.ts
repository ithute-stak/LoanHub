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
