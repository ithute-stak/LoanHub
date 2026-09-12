import { api } from "@/lib/api";
import type {
  AssistedCompanyClientCreate,
  CompanyClient,
  CompanyClientExistingLoanCheck,
  CompanyClientExternalDebt,
  CompanyClientExternalDebtInput,
  CompanyClientCaseEntry,
  CompanyClientCaseEntryCreate,
  CompanyClientCaseRecord,
  CompanyClientPortfolioInsights,
  CompanyClientNationalIdChangeRequest,
  CompanyClientProfile,
  CompanyClientProfileUpdate,
  CompanyClientProfileDocument,
  InternalClientLoanRequest,
  InternalClientLoanRequestCreate,
} from "@/types/companyClient";
import type { PaymentTransaction } from "@/types/payment";
import type { PaymentMethod } from "@/types/expenseManagement";

export type CompanyClientDirectoryParams = {
  search?: string;
  status?: string;
  loan_status?: string;
  employment_status?: string;
  employer?: string;
  opening_fee_status?: string;
  branch_id?: string;
  has_bank_account?: boolean;
  has_loan?: boolean;
  bank_last4?: string;
  due_within_days?: number;
  salary_due_within_days?: number;
  overdue_only?: boolean;
  limit?: number;
};

export async function listCompanyClients(params?: CompanyClientDirectoryParams): Promise<CompanyClient[]> {
  return (await api.get<CompanyClient[]>("/company-clients", { params })).data;
}

export async function getCompanyClientPortfolioInsights(
  dueWithinDays = 14,
): Promise<CompanyClientPortfolioInsights> {
  return (await api.get<CompanyClientPortfolioInsights>("/company-clients/portfolio-insights", {
    params: { due_within_days: dueWithinDays, limit: 30 },
  })).data;
}


export async function getCompanyClientProfile(accountId: string): Promise<CompanyClientProfile> {
  return (await api.get<CompanyClientProfile>(`/company-clients/${accountId}/profile`)).data;
}

export async function updateCompanyClientProfile(
  accountId: string,
  payload: CompanyClientProfileUpdate,
): Promise<CompanyClientProfile> {
  let requestPayload = payload;
  if (payload.bank_account && !String(payload.bank_account.account_number || "").trim()) {
    // A blank account number means "keep the encrypted account already on file".
    // Do not resend bank/routing fields in that case: the backend deliberately
    // requires a matching new account number whenever those fields are changed.
    const unchangedBankFields = { ...payload.bank_account };
    delete unchangedBankFields.bank_name;
    delete unchangedBankFields.branch_name;
    delete unchangedBankFields.branch_code;
    delete unchangedBankFields.account_number;
    requestPayload = {
      ...payload,
      bank_account: unchangedBankFields,
    };
  }
  return (await api.patch<CompanyClientProfile>(`/company-clients/${accountId}/profile`, requestPayload)).data;
}

export async function requestCompanyClientNationalIdChange(
  accountId: string,
  payload: { proposed_national_id: string; reason: string },
): Promise<CompanyClientNationalIdChangeRequest> {
  return (await api.post<CompanyClientNationalIdChangeRequest>(
    `/company-clients/${accountId}/national-id-change-requests`,
    payload,
  )).data;
}

export async function decideCompanyClientNationalIdChangeAsOwner(
  accountId: string,
  requestId: string,
  payload: { approve: boolean; reason?: string | null },
): Promise<CompanyClientNationalIdChangeRequest> {
  return (await api.post<CompanyClientNationalIdChangeRequest>(
    `/company-clients/${accountId}/national-id-change-requests/${requestId}/company-owner-decision`,
    payload,
  )).data;
}

export async function uploadCompanyClientProfileImage(
  accountId: string,
  file: File,
): Promise<CompanyClientProfileDocument> {
  const form = new FormData();
  form.append("file", file);
  return (await api.post<CompanyClientProfileDocument>(
    `/company-clients/${accountId}/profile-image`,
    form,
  )).data;
}

export async function uploadCompanyClientDocument(
  accountId: string,
  payload: {
    file: File;
    documentType: string;
    description?: string;
    isConfidential?: boolean;
  },
): Promise<CompanyClientProfileDocument> {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("document_type", payload.documentType);
  if (payload.description?.trim()) form.append("description", payload.description.trim());
  form.append("is_confidential", String(payload.isConfidential ?? true));
  return (await api.post<CompanyClientProfileDocument>(
    `/company-clients/${accountId}/documents`,
    form,
  )).data;
}

export async function loadCompanyClientFileObjectUrl(
  accountId: string,
  fileId: string,
): Promise<string> {
  const response = await api.get<Blob>(
    `/company-clients/${accountId}/files/${fileId}/content`,
    { responseType: "blob" },
  );
  return URL.createObjectURL(response.data);
}

export async function downloadCompanyClientFile(
  accountId: string,
  file: CompanyClientProfileDocument,
): Promise<void> {
  const response = await api.get<Blob>(
    `/company-clients/${accountId}/files/${file.id}/content`,
    { params: { download: true }, responseType: "blob" },
  );
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.original_name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}


export async function checkCompanyClientExistingLoans(
  nationalId: string,
  signal?: AbortSignal,
): Promise<CompanyClientExistingLoanCheck> {
  return (
    await api.get<CompanyClientExistingLoanCheck>(
      "/company-clients/existing-loan-check",
      { params: { national_id: nationalId }, signal },
    )
  ).data;
}

export async function openCompanyClientAccount(payload: AssistedCompanyClientCreate): Promise<CompanyClient> {
  return (await api.post<CompanyClient>("/company-clients", payload)).data;
}

export async function listCompanyClientExternalDebts(accountId: string): Promise<CompanyClientExternalDebt[]> {
  return (await api.get<CompanyClientExternalDebt[]>(`/company-clients/${accountId}/external-debts`)).data;
}

export async function createCompanyClientExternalDebt(
  accountId: string,
  payload: CompanyClientExternalDebtInput,
): Promise<CompanyClientExternalDebt> {
  return (await api.post<CompanyClientExternalDebt>(`/company-clients/${accountId}/external-debts`, payload)).data;
}

export async function updateCompanyClientExternalDebt(
  accountId: string,
  debtId: string,
  payload: Partial<CompanyClientExternalDebtInput>,
): Promise<CompanyClientExternalDebt> {
  return (await api.patch<CompanyClientExternalDebt>(`/company-clients/${accountId}/external-debts/${debtId}`, payload)).data;
}

export async function recordCompanyClientExternalDebtPayment(
  accountId: string,
  debtId: string,
  payload: {
    amount: number;
    paid_on: string;
    installments_covered: number;
    next_due_date?: string | null;
    notes?: string | null;
  },
): Promise<CompanyClientExternalDebt> {
  return (await api.post<CompanyClientExternalDebt>(
    `/company-clients/${accountId}/external-debts/${debtId}/payments`,
    payload,
  )).data;
}

export async function createInternalClientLoanRequest(
  accountId: string,
  payload: InternalClientLoanRequestCreate,
): Promise<InternalClientLoanRequest> {
  return (await api.post<InternalClientLoanRequest>(`/company-clients/${accountId}/internal-loan-requests`, payload)).data;
}

export async function settleCompanyClientOpeningFee(
  accountId: string,
  payload: {
    payment_method: PaymentMethod;
    proof_reference?: string | null;
    proof_url?: string | null;
    proof_notes?: string | null;
    notes?: string | null;
    idempotency_key?: string | null;
  },
): Promise<PaymentTransaction> {
  return (await api.post<PaymentTransaction>(`/company-clients/${accountId}/opening-fee-payment`, payload)).data;
}


export async function listCompanyClientCaseRecords(): Promise<CompanyClientCaseRecord[]> {
  return (await api.get<CompanyClientCaseRecord[]>("/company-clients/case-records")).data;
}

export async function listCompanyClientCaseEntries(accountId: string): Promise<CompanyClientCaseEntry[]> {
  return (await api.get<CompanyClientCaseEntry[]>(`/company-clients/${accountId}/case-entries`)).data;
}

export async function createCompanyClientCaseEntry(
  accountId: string,
  payload: CompanyClientCaseEntryCreate,
): Promise<CompanyClientCaseEntry> {
  return (await api.post<CompanyClientCaseEntry>(`/company-clients/${accountId}/case-entries`, payload)).data;
}


export async function updateCompanyClientCaseEntryStatus(
  accountId: string,
  entryId: string,
  status: string,
): Promise<CompanyClientCaseEntry> {
  return (await api.patch<CompanyClientCaseEntry>(`/company-clients/${accountId}/case-entries/${entryId}`, { status })).data;
}