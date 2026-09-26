import { api } from "@/lib/api";

export type PayrollAccount = {
  id: string;
  employer_group_id: string;
  group_code: string | null;
  group_name: string | null;
  branch_id: string | null;
  payroll_reference: string | null;
  payroll_day: number | null;
  collection_channel: string;
  reconciliation_tolerance: number;
  payroll_contact_name: string | null;
  payroll_contact_email: string | null;
  payroll_contact_phone: string | null;
  notes: string | null;
  is_active: boolean;
};

export type PayrollDeduction = {
  id: string;
  cycle_id: string;
  borrower_id: string | null;
  borrower_name: string;
  loan_id: string | null;
  loan_reference: string | null;
  folio_number: string | null;
  employee_number: string | null;
  expected_amount: number;
  actual_amount: number;
  variance_amount: number;
  status: string;
  rejection_code: string | null;
  rejection_reason: string | null;
  employer_reference: string | null;
};

export type PayrollCycle = {
  id: string;
  account_id: string;
  group_code: string | null;
  group_name: string | null;
  period_key: string;
  scheduled_pay_date: string;
  expected_amount: number;
  actual_amount: number;
  shortage_amount: number;
  excess_amount: number;
  rejected_amount: number;
  expected_line_count: number;
  matched_line_count: number;
  exception_line_count: number;
  status: string;
  source: string;
  generated_at: string | null;
  received_at: string | null;
  reconciled_at: string | null;
  deductions?: PayrollDeduction[];
};

export type EmployerPayrollGroup = {
  employer_group_id: string;
  group_code: string;
  group_name: string;
  account: PayrollAccount | null;
  borrower_count: number;
  active_loan_count: number;
  principal_exposure: number;
  outstanding_exposure: number;
  overdue_exposure: number;
  expected_monthly_deductions: number;
  cdas_loan_count: number;
  cdas_expected_deductions: number;
  terminated_employee_count: number;
  suspended_employee_count: number;
  latest_cycle: PayrollCycle | null;
};

export type EmployerPayrollOverview = {
  summary: {
    work_group_count: number;
    borrower_count: number;
    active_loan_count: number;
    outstanding_exposure: number;
    expected_monthly_deductions: number;
    overdue_exposure: number;
    terminated_employee_count: number;
    reconciliation_exception_count: number;
  };
  groups: EmployerPayrollGroup[];
};

export type PayrollEmployee = {
  id: string;
  account_id: string;
  borrower_id: string;
  borrower_name: string;
  employee_number: string | null;
  employment_state: string;
  effective_date: string | null;
  termination_date: string | null;
  termination_reason: string | null;
  last_verified_at: string | null;
};

export async function getEmployerPayrollOverview(): Promise<EmployerPayrollOverview> {
  return (await api.get<EmployerPayrollOverview>("/employer-payroll/overview")).data;
}

export async function configurePayrollAccount(payload: {
  employer_group_id: string;
  payroll_reference?: string | null;
  payroll_day?: number | null;
  collection_channel?: string;
  reconciliation_tolerance?: number;
  payroll_contact_name?: string | null;
  payroll_contact_email?: string | null;
  payroll_contact_phone?: string | null;
  notes?: string | null;
  is_active?: boolean;
}): Promise<PayrollAccount> {
  return (await api.put<PayrollAccount>("/employer-payroll/accounts", payload)).data;
}

export async function getPayrollCycles(accountId?: string): Promise<PayrollCycle[]> {
  return (await api.get<PayrollCycle[]>("/employer-payroll/cycles", {
    params: accountId ? { account_id: accountId } : undefined,
  })).data;
}

export async function getPayrollCycle(cycleId: string): Promise<PayrollCycle> {
  return (await api.get<PayrollCycle>(`/employer-payroll/cycles/${cycleId}`)).data;
}

export async function generatePayrollCycle(
  accountId: string,
  periodKey: string,
  scheduledPayDate?: string,
): Promise<PayrollCycle> {
  return (await api.post<PayrollCycle>(`/employer-payroll/accounts/${accountId}/cycles`, {
    period_key: periodKey,
    scheduled_pay_date: scheduledPayDate || undefined,
  })).data;
}

export async function uploadPayrollCsv(cycleId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return (await api.post<{ cycle: PayrollCycle; import: { matched_rows: number; unmatched_rows: number; duplicate_match_rows: number } }>(
    `/employer-payroll/cycles/${cycleId}/import.csv`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  )).data;
}

export async function reconcilePayrollCycle(cycleId: string): Promise<PayrollCycle> {
  return (await api.post<PayrollCycle>(`/employer-payroll/cycles/${cycleId}/reconcile`)).data;
}

export async function getPayrollExceptions(): Promise<PayrollDeduction[]> {
  return (await api.get<PayrollDeduction[]>("/employer-payroll/exceptions")).data;
}

export async function getPayrollEmployees(params?: { account_id?: string; employment_state?: string }): Promise<PayrollEmployee[]> {
  return (await api.get<PayrollEmployee[]>("/employer-payroll/employees", { params })).data;
}

export async function updatePayrollEmployee(
  accountId: string,
  borrowerId: string,
  payload: {
    employee_number?: string | null;
    employment_state: string;
    effective_date?: string | null;
    termination_date?: string | null;
    termination_reason?: string | null;
  },
): Promise<PayrollEmployee> {
  return (await api.put<PayrollEmployee>(`/employer-payroll/accounts/${accountId}/employees/${borrowerId}`, payload)).data;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5_000);
}

export async function downloadPayrollCycleCsv(cycle: PayrollCycle) {
  const response = await api.get<Blob>(`/employer-payroll/cycles/${cycle.id}/export.csv`, { responseType: "blob" });
  downloadBlob(response.data, `payroll-${cycle.group_code ?? "group"}-${cycle.period_key}.csv`);
}

export async function downloadPayrollCyclePdf(cycle: PayrollCycle) {
  const response = await api.get<Blob>(`/employer-payroll/cycles/${cycle.id}/export.pdf`, { responseType: "blob" });
  downloadBlob(response.data, `payroll-${cycle.group_code ?? "group"}-${cycle.period_key}.pdf`);
}
