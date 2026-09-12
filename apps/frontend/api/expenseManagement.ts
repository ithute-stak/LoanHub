import { api } from "@/lib/api";
import type {
  BranchDailyLedger, BranchDailySubmission, BranchDailySubmissionList, BranchFundingTransfer, BranchFundingTransferCreate,
  ExpenseCategory, ExpenseCategoryCreate, FinancialIntegrityRepair, FinancialIntegrityReport, OpeningSource, OpeningSourceCreate, PaymentMethod,
  PaymentMethodOption, TreasuryDashboard, TreasuryDirection, TreasuryEntry, TreasuryEntryCreate,
  TreasurySettings, TreasurySettingsUpdate, TreasuryStatement,
} from "@/types/expenseManagement";

function repeatedParams(name: string, values?: readonly string[]): URLSearchParams {
  const params = new URLSearchParams();
  values?.forEach((value) => params.append(name, value));
  return params;
}

export const expenseManagementApi = {
  paymentMethods: async (): Promise<PaymentMethodOption[]> =>
    (await api.get<PaymentMethodOption[]>("/expense-management/payment-methods")).data,
  settings: async (): Promise<TreasurySettings> =>
    (await api.get<TreasurySettings>("/expense-management/settings")).data,
  updateSettings: async (payload: TreasurySettingsUpdate): Promise<TreasurySettings> =>
    (await api.put<TreasurySettings>("/expense-management/settings", payload)).data,
  categories: async (includeInactive = false): Promise<ExpenseCategory[]> =>
    (await api.get<ExpenseCategory[]>("/expense-management/expense-categories", { params: { include_inactive: includeInactive } })).data,
  createCategory: async (payload: ExpenseCategoryCreate): Promise<ExpenseCategory> =>
    (await api.post<ExpenseCategory>("/expense-management/expense-categories", payload)).data,
  updateCategory: async (categoryId: string, payload: Partial<ExpenseCategoryCreate>): Promise<ExpenseCategory> =>
    (await api.put<ExpenseCategory>(`/expense-management/expense-categories/${categoryId}`, payload)).data,
  dashboard: async (businessDate: string, branchId?: string | null): Promise<TreasuryDashboard> =>
    (await api.get<TreasuryDashboard>("/expense-management/dashboard", { params: { business_date: businessDate, branch_id: branchId || undefined } })).data,
  integrity: async (businessDate: string, branchId?: string | null): Promise<FinancialIntegrityReport> =>
    (await api.get<FinancialIntegrityReport>("/expense-management/integrity", { params: { business_date: businessDate, branch_id: branchId || undefined } })).data,
  repairIntegrity: async (businessDate: string, branchId?: string | null): Promise<FinancialIntegrityRepair> =>
    (await api.post<FinancialIntegrityRepair>("/expense-management/integrity/repair", null, { params: { business_date: businessDate, branch_id: branchId || undefined } })).data,
  currentDay: async (branchId: string | null, businessDate: string): Promise<BranchDailyLedger> =>
    (await api.get<BranchDailyLedger>("/expense-management/days/current", { params: { branch_id: branchId || undefined, business_date: businessDate } })).data,
  createOpeningSource: async (payload: OpeningSourceCreate): Promise<OpeningSource> =>
    (await api.post<OpeningSource>("/expense-management/opening-sources", payload)).data,
  voidOpeningSource: async (sourceId: string, reason: string): Promise<OpeningSource> =>
    (await api.post<OpeningSource>(`/expense-management/opening-sources/${sourceId}/void`, { reason })).data,
  recordEntry: async (payload: TreasuryEntryCreate): Promise<TreasuryEntry> =>
    (await api.post<TreasuryEntry>("/expense-management/entries", payload)).data,
  approveEntry: async (entryId: string, reason?: string | null): Promise<TreasuryEntry> =>
    (await api.post<TreasuryEntry>(`/expense-management/entries/${entryId}/approve`, { reason: reason || null })).data,
  rejectEntry: async (entryId: string, reason: string): Promise<TreasuryEntry> =>
    (await api.post<TreasuryEntry>(`/expense-management/entries/${entryId}/reject`, { reason })).data,
  voidEntry: async (entryId: string, reason: string): Promise<TreasuryEntry> =>
    (await api.post<TreasuryEntry>(`/expense-management/entries/${entryId}/void`, { reason })).data,
  submitDay: async (ledgerId: string, payload: { declared_closing_balance?: number | null; notes?: string | null }): Promise<BranchDailySubmission> =>
    (await api.post<BranchDailySubmission>(`/expense-management/days/${ledgerId}/submit`, payload)).data,
  submissions: async (filters?: { dateFrom?: string; dateTo?: string; branchId?: string | null; automatic?: boolean; skip?: number; limit?: number }): Promise<BranchDailySubmissionList> =>
    (await api.get<BranchDailySubmissionList>("/expense-management/submissions", { params: {
      date_from: filters?.dateFrom, date_to: filters?.dateTo, branch_id: filters?.branchId || undefined,
      automatic: filters?.automatic, skip: filters?.skip ?? 0, limit: filters?.limit ?? 50,
    } })).data,
  submission: async (submissionId: string): Promise<BranchDailySubmission> =>
    (await api.get<BranchDailySubmission>(`/expense-management/submissions/${submissionId}`)).data,
  regenerateSubmissionPdf: async (submissionId: string): Promise<BranchDailySubmission> =>
    (await api.post<BranchDailySubmission>(`/expense-management/submissions/${submissionId}/regenerate-pdf`)).data,
  reopenDay: async (ledgerId: string, reason: string): Promise<BranchDailyLedger> =>
    (await api.post<BranchDailyLedger>(`/expense-management/days/${ledgerId}/reopen`, { reason })).data,
  reviewDay: async (ledgerId: string): Promise<BranchDailyLedger> =>
    (await api.post<BranchDailyLedger>(`/expense-management/days/${ledgerId}/review`)).data,
  runDailyCycle: async (): Promise<{ opened_ledgers: number; submitted_ledgers: number }> =>
    (await api.post<{ opened_ledgers: number; submitted_ledgers: number }>("/expense-management/run-daily-cycle")).data,
  transfers: async (dateFrom?: string, dateTo?: string): Promise<BranchFundingTransfer[]> =>
    (await api.get<BranchFundingTransfer[]>("/expense-management/transfers", { params: { date_from: dateFrom, date_to: dateTo } })).data,
  createTransfer: async (payload: BranchFundingTransferCreate): Promise<BranchFundingTransfer> =>
    (await api.post<BranchFundingTransfer>("/expense-management/transfers", payload)).data,
  receiveTransfer: async (transferId: string): Promise<BranchFundingTransfer> =>
    (await api.post<BranchFundingTransfer>(`/expense-management/transfers/${transferId}/receive`)).data,
  statement: async (filters: {
    dateFrom: string; dateTo: string; branchId?: string | null; paymentMethods?: PaymentMethod[]; directions?: TreasuryDirection[];
  }): Promise<TreasuryStatement> => {
    const params = repeatedParams("payment_methods", filters.paymentMethods);
    filters.directions?.forEach((value) => params.append("directions", value));
    params.set("date_from", filters.dateFrom); params.set("date_to", filters.dateTo);
    if (filters.branchId) params.set("branch_id", filters.branchId);
    return (await api.get<TreasuryStatement>("/expense-management/statements", { params })).data;
  },
  downloadStatementCsv: async (filters: {
    dateFrom: string; dateTo: string; branchId?: string | null; paymentMethods?: PaymentMethod[]; directions?: TreasuryDirection[];
  }): Promise<void> => {
    const params = repeatedParams("payment_methods", filters.paymentMethods);
    filters.directions?.forEach((value) => params.append("directions", value));
    params.set("date_from", filters.dateFrom); params.set("date_to", filters.dateTo);
    if (filters.branchId) params.set("branch_id", filters.branchId);
    const response = await api.get<Blob>("/expense-management/statements/export.csv", { params, responseType: "blob" });
    const url = URL.createObjectURL(response.data); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `loanhub-money-statement-${filters.dateFrom}-${filters.dateTo}.csv`;
    document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
  },
};
