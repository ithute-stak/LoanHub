import { api } from "@/lib/api";

export type ReadinessComponent = { key: string; label: string; score: number; max: number };
export type BorrowerReadiness = {
  score: number;
  band: string;
  confidence: "low" | "medium" | "high";
  components: ReadinessComponent[];
  helping: string[];
  reducing: string[];
  actions: string[];
  is_credit_bureau_score: false;
  disclaimer: string;
};

export type FinancialHealth = {
  monthly_income: number;
  additional_income: number;
  living_expenses: number;
  loanhub_installments: number;
  external_installments: number;
  total_monthly_commitments: number;
  estimated_disposable_income: number;
  loanhub_balance: number;
  external_debt_balance: number;
  total_outstanding_debt: number;
  debt_to_income_percent: number;
  maximum_affordable_installment: number;
  source: string;
};

export type BorrowerFinancialOverview = {
  financial_health: FinancialHealth;
  readiness: BorrowerReadiness;
  counts: {
    active_loans: number;
    external_debts: number;
    open_service_requests: number;
    active_applications: number;
  };
  next_due: null | {
    installment_id: string;
    loan_id: string;
    loan_reference: string | null;
    lender: string | null;
    due_date: string;
    amount_due: number;
    status: string;
  };
  consents: { share_profile: boolean; credit_checks: boolean };
};

export type BorrowerFinancialProfile = {
  employment: Record<string, string | number | null>;
  income_sources: Array<{
    id: string;
    source_type: string;
    description: string | null;
    declared_amount: number;
    verified_amount: number;
    frequency: string;
    is_verified: boolean;
  }>;
  expenses: Array<{
    id: string;
    category: string;
    description: string | null;
    monthly_amount: number;
    is_verified: boolean;
  }>;
  external_debts: Array<{
    id: string;
    creditor: string;
    account_reference: string | null;
    debt_type: string;
    started_on: string | null;
    original_amount: number;
    current_balance: number;
    monthly_installment: number;
    total_installments: number | null;
    installments_paid: number;
    remaining_installments: number | null;
    next_due_date: string | null;
    settlement_amount: number | null;
    remaining_term_months: number | null;
    status: string;
    is_verified: boolean;
  }>;
  bank_accounts: Array<{
    id: string;
    bank_name: string;
    account_holder: string;
    account_type: string;
    account_last4: string;
    salary_account: boolean;
    verification_status: string;
    masked_card_number: string | null;
    card_brand: string | null;
  }>;
  kyc: { identity_verified: boolean; address_verified: boolean; phone_verified: boolean; profiles: number };
};

export type ApplicationStage = { key: string; label: string; complete: boolean };
export type BorrowerApplicationTracker = {
  id: string;
  requested_amount: number;
  preferred_term_months: number;
  loan_purpose: string | null;
  status: string;
  created_at: string;
  submitted_at: string | null;
  offer_count: number;
  documents_count: number;
  selected_offer_id: string | null;
  loan_id: string | null;
  loan_reference: string | null;
  lender: string | null;
  stages: ApplicationStage[];
  action_required: string | null;
};

export type OfferComparison = {
  request: {
    id: string;
    requested_amount: number;
    preferred_term_months: number;
    loan_purpose: string | null;
    selected_offer_id: string | null;
  };
  offers: Array<{
    id: string;
    company_id: string;
    company_name: string;
    approved_amount: number;
    term_months: number;
    interest_rate_percent: number;
    processing_fee: number;
    monthly_repayment: number;
    total_repayment: number;
    status: string;
    expires_at: string | null;
    is_selected: boolean;
    is_lowest_total: boolean;
    is_lowest_installment: boolean;
  }>;
  guidance: string;
};

export type RepaymentCalendarItem = {
  id: string;
  loan_id: string;
  loan_reference: string | null;
  lender: string | null;
  installment_number: number;
  due_date: string;
  principal_due: number;
  interest_due: number;
  fee_due: number;
  total_due: number;
  paid_amount: number;
  remaining_due: number;
  status: string;
  paid_at: string | null;
};

export type EligibilityProduct = {
  product_id: string;
  company_id: string;
  company_name: string;
  product_name: string;
  description: string | null;
  min_amount: number;
  max_amount: number;
  min_term_months: number;
  max_term_months: number;
  interest_method: string;
  interest_rate_percent: number;
  processing_fee: number;
  estimated_for_amount: number;
  estimated_term_months: number;
  estimated_monthly_installment: number;
  estimated_total_repayment: number;
  estimated_projected_dti_percent: number;
  rate_basis: string | null;
  status: "appears_eligible" | "needs_verification" | "unlikely";
  reasons: string[];
};

export type BorrowerEligibility = { products: EligibilityProduct[]; disclaimer: string };

export type BorrowerTimelineEvent = {
  at: string;
  type: string;
  title: string;
  description: string;
  href: string;
};

export type BorrowerSecurity = {
  active_sessions: number;
  last_seen_at: string | null;
  account_verified: boolean;
  consents: { share_profile: boolean; credit_checks: boolean };
  profile_access: Array<{
    company_id: string;
    company_name: string;
    loan_request_id: string;
    unlocked_at: string | null;
    expires_at: string | null;
    purpose: string;
  }>;
  account_security_url: string;
};

export type BorrowerServiceRequest = {
  id: string;
  borrower_id: string;
  borrower_name?: string;
  company_id: string;
  company_name: string;
  loan_id: string | null;
  loan_reference: string | null;
  request_type: string;
  request_type_label: string;
  status: string;
  subject: string;
  details: string | null;
  requested_value: number | null;
  company_response: string | null;
  responded_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PayoffEstimate = {
  loan_id: string;
  loan_reference: string;
  lender: string;
  current_balance: number;
  scheduled_installment: number;
  extra_payment: number;
  estimated_balance_after_extra: number;
  estimated_installments_remaining: number;
  remaining_scheduled_amount: number;
  official_settlement_required: true;
  disclaimer: string;
};

export async function getBorrowerFinancialOverview(): Promise<BorrowerFinancialOverview> {
  return (await api.get<BorrowerFinancialOverview>("/borrower-command/overview")).data;
}

export async function getBorrowerFinancialProfile(): Promise<BorrowerFinancialProfile> {
  return (await api.get<BorrowerFinancialProfile>("/borrower-command/financial-profile")).data;
}

export async function getBorrowerApplications(): Promise<BorrowerApplicationTracker[]> {
  return (await api.get<BorrowerApplicationTracker[]>("/borrower-command/applications")).data;
}

export async function getBorrowerOfferComparison(requestId: string): Promise<OfferComparison> {
  return (await api.get<OfferComparison>(`/borrower-command/offers/${requestId}`)).data;
}

export async function getBorrowerRepaymentCalendar(includePaid = false): Promise<RepaymentCalendarItem[]> {
  return (await api.get<RepaymentCalendarItem[]>("/borrower-command/repayment-calendar", { params: { include_paid: includePaid } })).data;
}

export async function getBorrowerEligibility(): Promise<BorrowerEligibility> {
  return (await api.get<BorrowerEligibility>("/borrower-command/eligibility")).data;
}

export async function getBorrowerTimeline(): Promise<BorrowerTimelineEvent[]> {
  return (await api.get<BorrowerTimelineEvent[]>("/borrower-command/timeline")).data;
}

export async function getBorrowerSecurity(): Promise<BorrowerSecurity> {
  return (await api.get<BorrowerSecurity>("/borrower-command/security")).data;
}

export async function getBorrowerServiceRequests(): Promise<BorrowerServiceRequest[]> {
  return (await api.get<BorrowerServiceRequest[]>("/borrower-command/service-requests")).data;
}

export async function createBorrowerServiceRequest(payload: {
  request_type: string;
  loan_id?: string | null;
  company_id?: string | null;
  subject?: string | null;
  details?: string | null;
  requested_value?: number | null;
}): Promise<BorrowerServiceRequest> {
  return (await api.post<BorrowerServiceRequest>("/borrower-command/service-requests", payload)).data;
}

export async function cancelBorrowerServiceRequest(requestId: string): Promise<BorrowerServiceRequest> {
  return (await api.patch<BorrowerServiceRequest>(`/borrower-command/service-requests/${requestId}/cancel`)).data;
}

export async function updateBorrowerConsents(payload: {
  consent_to_share_profile?: boolean;
  consent_to_credit_checks?: boolean;
}): Promise<{ share_profile: boolean; credit_checks: boolean }> {
  return (await api.patch<{ share_profile: boolean; credit_checks: boolean }>("/borrower-command/consents", payload)).data;
}

export async function getPayoffEstimate(loanId: string, extraPayment: number): Promise<PayoffEstimate> {
  return (await api.get<PayoffEstimate>(`/borrower-command/payoff/${loanId}`, { params: { extra_payment: extraPayment } })).data;
}

export async function getCompanyBorrowerServiceRequests(status?: string): Promise<BorrowerServiceRequest[]> {
  return (await api.get<BorrowerServiceRequest[]>("/borrower-command/company/service-requests", { params: status ? { status } : undefined })).data;
}

export async function updateCompanyBorrowerServiceRequest(
  requestId: string,
  payload: { status: string; company_response?: string | null },
): Promise<BorrowerServiceRequest> {
  return (await api.patch<BorrowerServiceRequest>(`/borrower-command/company/service-requests/${requestId}`, payload)).data;
}
