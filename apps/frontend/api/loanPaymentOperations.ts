import { api } from "@/lib/api";

const base = "/loan-payment-operations";

export type LoanPaymentOperationsSummary = {
  active_mandates: number;
  mandates_due: number;
  reminders_attention: number;
  restructures_pending: number;
  accounting_exports: number;
};

export type OnlineRepaymentMandate = {
  id: string;
  loan_id: string;
  provider: string;
  amount: string;
  status: string;
  next_debit_date?: string | null;
  failure_reason?: string | null;
};

export type RestructureRequest = {
  id: string;
  loan_id: string;
  borrower_id: string;
  status: string;
  requested_term_months: number;
  payment_holiday_days: number;
  reason: string;
  preview: Record<string, unknown>;
  agreement_reference?: string | null;
};

export const loanPaymentOperationsApi = {
  summary: async () => (await api.get<LoanPaymentOperationsSummary>(`${base}/summary`)).data,
  myMandates: async () => (await api.get<OnlineRepaymentMandate[]>(`${base}/borrower/mandates`)).data,
  createMandate: async (payload: Record<string, unknown>) => (await api.post<OnlineRepaymentMandate>(`${base}/borrower/mandates`, payload)).data,
  cancelMandate: async (id: string) => (await api.post<OnlineRepaymentMandate>(`${base}/borrower/mandates/${id}/cancel`)).data,
  reminderPreferences: async (companyId: string) => (await api.get(`${base}/borrower/reminder-preferences`, { params: { company_id: companyId } })).data,
  saveReminderPreferences: async (companyId: string, payload: Record<string, unknown>) => (await api.put(`${base}/borrower/reminder-preferences`, payload, { params: { company_id: companyId } })).data,
  myRestructures: async () => (await api.get<RestructureRequest[]>(`${base}/borrower/restructures`)).data,
  requestRestructure: async (payload: Record<string, unknown>) => (await api.post<RestructureRequest>(`${base}/borrower/restructures`, payload)).data,
  restructures: async () => (await api.get<RestructureRequest[]>(`${base}/restructures`)).data,
  approveRestructure: async (id: string, payload: Record<string, unknown>) => (await api.post<RestructureRequest>(`${base}/restructures/${id}/approve`, payload)).data,
  reminders: async () => (await api.get<any[]>(`${base}/reminders`)).data,
  runReminders: async () => (await api.post<{ created: number; configuration_required: number }>(`${base}/reminders/run`)).data,
  runDueMandates: async () => (await api.post<{ created: number; succeeded: number; processing: number; failed: number }>(`${base}/mandates/run-due`)).data,
  accountingExports: async () => (await api.get<any[]>(`${base}/accounting-exports`)).data,
  createAccountingExport: async (payload: Record<string, unknown>) => (await api.post(`${base}/accounting-exports`, payload)).data,
};
