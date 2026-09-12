import { api } from "@/lib/api";

export type CompanyCapability = {
  number: number;
  key: string;
  name: string;
  implementation: string;
  status: string;
};

export type CompanyCommandDashboard = {
  generated_at: string;
  currency: string;
  portfolio: {
    loans_total: number;
    active_loans: number;
    overdue_loans: number;
    portfolio_balance: number;
    principal_originated: number;
    contractual_margin: number;
    overdue_scheduled_amount: number;
    expected_collections_30_days: number;
    par_1: number;
    par_7: number;
    par_30: number;
    par_60: number;
    par_90: number;
    branch_exposure: Record<string, number>;
  };
  treasury: {
    recorded_money_in: number;
    recorded_money_out: number;
    net_recorded_liquidity: number;
    entry_count: number;
  };
  collections: {
    open_cases: number;
    case_count: number;
    buckets: Record<string, number>;
    bucket_exposure: Record<string, number>;
    promise_to_pay: number;
    legal_handover: number;
    recovered_amount: number;
  };
  governance: {
    open_compliance_cases: number;
    high_risk_compliance_cases: number;
    open_reconciliation_exceptions: number;
    active_approval_workflows: number;
    unresolved_system_errors: number;
  };
  operations: {
    open_records: number;
    overdue_actions: number;
    by_module: Record<string, number>;
  };
  cash_flow: { successful_payment_volume: number; successful_payment_count: number };
  profitability: { contractual_margin: number; recoveries: number; note: string };
  liquidity_forecast: {
    recorded_net_liquidity: number;
    expected_collections_30_days: number;
    illustrative_30_day_position: number;
    note: string;
  };
  warnings: Array<{ level: string; title: string; detail: string }>;
};

export type OperatingRecord = {
  id: string;
  company_id: string;
  branch_id: string | null;
  module: string;
  record_type: string;
  reference: string;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  borrower_id: string | null;
  loan_id: string | null;
  assigned_user_id: string | null;
  counterparty_name: string | null;
  amount: number | null;
  currency: string;
  due_at: string | null;
  data: Record<string, unknown>;
  tags: string[];
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type APIKeyRecord = {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  allowed_ips: string[];
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

export type WebhookRecord = {
  id: string;
  name: string;
  endpoint_url: string;
  secret_prefix: string;
  event_types: string[];
  is_active: boolean;
  failure_count: number;
  last_delivery_at: string | null;
  created_at: string;
};

export async function getCompanyCapabilities(): Promise<CompanyCapability[]> {
  return (await api.get<CompanyCapability[]>("/company-operating-system/capabilities")).data;
}

export async function getCompanyCommandDashboard(): Promise<CompanyCommandDashboard> {
  return (await api.get<CompanyCommandDashboard>("/company-operating-system/dashboard")).data;
}

export async function listOperatingRecords(module?: string): Promise<OperatingRecord[]> {
  return (await api.get<OperatingRecord[]>("/company-operating-system/records", { params: module ? { module } : undefined })).data;
}

export async function createOperatingRecord(payload: {
  module: string;
  record_type: string;
  title: string;
  description?: string;
  status?: string;
  priority?: string;
  counterparty_name?: string;
  amount?: number;
  due_at?: string;
  tags?: string[];
  data?: Record<string, unknown>;
}): Promise<OperatingRecord> {
  return (await api.post<OperatingRecord>("/company-operating-system/records", payload)).data;
}

export async function updateOperatingRecord(id: string, payload: Partial<OperatingRecord>): Promise<OperatingRecord> {
  return (await api.patch<OperatingRecord>(`/company-operating-system/records/${id}`, payload)).data;
}

export async function getCollectionsStrategy(): Promise<Record<string, unknown>> {
  return (await api.get<Record<string, unknown>>("/company-operating-system/collections/strategy")).data;
}

export async function getReconciliationSummary(): Promise<Record<string, unknown>> {
  return (await api.get<Record<string, unknown>>("/company-operating-system/reconciliation/summary")).data;
}

export async function simulateCompanyPricing(payload: {
  principal: number;
  rate_percent: number;
  term_months: number;
  processing_fee: number;
  interest_method: string;
}): Promise<Record<string, unknown>> {
  return (await api.post<Record<string, unknown>>("/company-operating-system/pricing/simulate", payload)).data;
}

export async function listCompanyApiKeys(): Promise<APIKeyRecord[]> {
  return (await api.get<APIKeyRecord[]>("/company-operating-system/api-keys")).data;
}

export async function createCompanyApiKey(payload: { name: string; scopes: string[] }): Promise<APIKeyRecord & { api_key: string }> {
  return (await api.post<APIKeyRecord & { api_key: string }>("/company-operating-system/api-keys", payload)).data;
}

export async function revokeCompanyApiKey(id: string): Promise<APIKeyRecord> {
  return (await api.post<APIKeyRecord>(`/company-operating-system/api-keys/${id}/revoke`)).data;
}

export async function listCompanyWebhooks(): Promise<WebhookRecord[]> {
  return (await api.get<WebhookRecord[]>("/company-operating-system/webhooks")).data;
}

export async function createCompanyWebhook(payload: { name: string; endpoint_url: string; event_types: string[] }): Promise<WebhookRecord & { signing_secret: string }> {
  return (await api.post<WebhookRecord & { signing_secret: string }>("/company-operating-system/webhooks", payload)).data;
}

export async function generateCompanyBoardPack(): Promise<Record<string, unknown>> {
  return (await api.post<Record<string, unknown>>("/company-operating-system/board-packs")).data;
}

export async function askCompanyDataAssistant(question: string): Promise<{
  answer: string;
  evidence: Record<string, unknown>;
  generated_at: string;
  mode: string;
  notice: string;
}> {
  return (await api.post("/company-operating-system/assistant", { question })).data;
}
