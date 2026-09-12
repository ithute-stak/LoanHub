import type { PaymentMethod } from "@/types/expenseManagement";
import type { PaymentResult } from "@/types/loan";
import type { PaymentProvider } from "@/types/payment";
import { api } from "@/lib/api";

export type FeeType = "flat" | "percentage" | "hybrid";

export type BorrowerRequestFee = {
  id: string;
  company_id: string | null;
  name: string;
  fee_type: FeeType;
  flat_amount: number;
  percentage: number;
  minimum_amount: number | null;
  maximum_amount: number | null;
  currency: string;
  required_before_submission: boolean;
  refundable: boolean;
  effective_from: string | null;
  effective_to: string | null;
  is_active: boolean;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type BorrowerRequestFeeWrite = Omit<BorrowerRequestFee, "id" | "created_by_user_id" | "created_at" | "updated_at">;

export type AccountOpeningFee = {
  id: string;
  company_id: string | null;
  name: string;
  fee_type: FeeType;
  flat_amount: number;
  percentage: number;
  minimum_amount: number | null;
  maximum_amount: number | null;
  currency: string;
  effective_from: string | null;
  effective_to: string | null;
  is_active: boolean;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type AccountOpeningFeeWrite = Omit<AccountOpeningFee, "id" | "created_by_user_id" | "created_at" | "updated_at">;

export type TransactionAgreement = {
  id: string;
  company_id: string;
  agreement_number: string;
  name: string;
  inbound_percentage: number;
  outbound_percentage: number;
  inbound_flat_fee: number;
  outbound_flat_fee: number;
  minimum_charge: number | null;
  maximum_charge: number | null;
  currency: string;
  settlement_frequency: "daily" | "weekly" | "monthly" | "quarterly" | "custom";
  settlement_day: number | null;
  effective_from: string;
  effective_to: string | null;
  terms: string | null;
  status: string;
  owner_accepted_by_user_id: string | null;
  company_accepted_by_user_id: string | null;
  owner_accepted_at: string | null;
  company_accepted_at: string | null;
  activated_at: string | null;
  suspended_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TransactionAgreementWrite = Omit<
  TransactionAgreement,
  | "id"
  | "agreement_number"
  | "status"
  | "owner_accepted_by_user_id"
  | "company_accepted_by_user_id"
  | "owner_accepted_at"
  | "company_accepted_at"
  | "activated_at"
  | "suspended_at"
  | "created_at"
  | "updated_at"
>;

export type ChargeLedgerEntry = {
  id: string;
  company_id: string;
  agreement_id: string;
  payment_id: string;
  claim_id: string | null;
  direction: "inbound" | "outbound";
  provider: PaymentProvider;
  payment_purpose: string;
  gross_amount: number;
  percentage_rate: number;
  flat_fee: number;
  charge_amount: number;
  currency: string;
  status: string;
  accrued_at: string;
  claimed_at: string | null;
  settled_at: string | null;
  created_at: string;
};

export type ChargeClaim = {
  id: string;
  company_id: string;
  agreement_id: string;
  claim_number: string;
  period_start: string;
  period_end: string;
  transaction_count: number;
  gross_transaction_value: number;
  amount: number;
  currency: string;
  status: string;
  issued_at: string | null;
  due_at: string | null;
  acknowledged_at: string | null;
  paid_at: string | null;
  disputed_at: string | null;
  notes: string | null;
  dispute_reason: string | null;
  created_at: string;
  updated_at: string;
};

export async function listBorrowerRequestFees(): Promise<BorrowerRequestFee[]> {
  return (await api.get<BorrowerRequestFee[]>("/finance-config/borrower-request-fees")).data;
}

export async function saveBorrowerRequestFee(payload: BorrowerRequestFeeWrite, id?: string): Promise<BorrowerRequestFee> {
  return (await (id
    ? api.put<BorrowerRequestFee>(`/finance-config/borrower-request-fees/${id}`, payload)
    : api.post<BorrowerRequestFee>("/finance-config/borrower-request-fees", payload))).data;
}

export async function listAccountOpeningFees(): Promise<AccountOpeningFee[]> {
  return (await api.get<AccountOpeningFee[]>("/finance-config/account-opening-fees")).data;
}

export async function saveAccountOpeningFee(payload: AccountOpeningFeeWrite, id?: string): Promise<AccountOpeningFee> {
  return (await (id
    ? api.put<AccountOpeningFee>(`/finance-config/account-opening-fees/${id}`, payload)
    : api.post<AccountOpeningFee>("/finance-config/account-opening-fees", payload))).data;
}

export async function listTransactionAgreements(companyId?: string): Promise<TransactionAgreement[]> {
  return (await api.get<TransactionAgreement[]>("/finance-config/agreements", {
    params: companyId ? { company_id: companyId } : undefined,
  })).data;
}

export async function saveTransactionAgreement(payload: TransactionAgreementWrite, id?: string): Promise<TransactionAgreement> {
  return (await (id
    ? api.put<TransactionAgreement>(`/finance-config/agreements/${id}`, payload)
    : api.post<TransactionAgreement>("/finance-config/agreements", payload))).data;
}

export async function makeOwnerAgreementDecision(id: string, accept: boolean, reason?: string): Promise<TransactionAgreement> {
  return (await api.post<TransactionAgreement>(`/finance-config/agreements/${id}/owner-decision`, { accept, reason })).data;
}

export async function makeCompanyAgreementDecision(id: string, accept: boolean, reason?: string): Promise<TransactionAgreement> {
  return (await api.post<TransactionAgreement>(`/finance-config/agreements/${id}/company-decision`, { accept, reason })).data;
}

export async function listChargeLedger(companyId?: string): Promise<ChargeLedgerEntry[]> {
  return (await api.get<ChargeLedgerEntry[]>("/finance-config/charge-ledger", {
    params: companyId ? { company_id: companyId } : undefined,
  })).data;
}

export async function listChargeClaims(companyId?: string): Promise<ChargeClaim[]> {
  return (await api.get<ChargeClaim[]>("/finance-config/claims", {
    params: companyId ? { company_id: companyId } : undefined,
  })).data;
}

export async function createChargeClaim(payload: {
  company_id: string;
  period_start: string;
  period_end: string;
  due_days: number;
  notes?: string | null;
}): Promise<ChargeClaim> {
  return (await api.post<ChargeClaim>("/finance-config/claims", payload)).data;
}

export async function listCompanyAgreements(): Promise<TransactionAgreement[]> {
  return (await api.get<TransactionAgreement[]>("/finance-config/company/agreements")).data;
}

export async function listCompanyChargeLedger(): Promise<ChargeLedgerEntry[]> {
  return (await api.get<ChargeLedgerEntry[]>("/finance-config/company/charge-ledger")).data;
}

export async function listCompanyChargeClaims(): Promise<ChargeClaim[]> {
  return (await api.get<ChargeClaim[]>("/finance-config/company/claims")).data;
}

export async function decideCompanyClaim(id: string, action: "acknowledge" | "dispute", reason?: string): Promise<ChargeClaim> {
  return (await api.post<ChargeClaim>(`/finance-config/claims/${id}/company-decision`, { action, reason })).data;
}

export type ClaimSettlementPayload = {
  payment_method: PaymentMethod;
  proof_reference?: string | null;
  proof_url?: string | null;
  proof_notes?: string | null;
  notes?: string | null;
  idempotency_key?: string;
};

export async function settleCompanyClaim(id: string, payload: ClaimSettlementPayload): Promise<PaymentResult> {
  return (await api.post<PaymentResult>(`/finance-config/claims/${id}/settle`, payload)).data;
}

export const settleCompanyClaimCash = settleCompanyClaim;
