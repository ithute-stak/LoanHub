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



export type BoardGovernancePackMetrics = {
  governance_version: number;
  generated_at: string;
  period_start: string;
  period_end: string;
  branch_id?: string | null;
  command: {
    command_status: string;
    enterprise_risk_score: number;
    enterprise_risk_level: string;
    priority_counts: { critical: number; high: number; medium: number; total: number };
    priority_actions: Array<{
      id: string;
      rank: number;
      severity: string;
      domain: string;
      title: string;
      why_now: string;
      recommended_action: string;
      action_url: string;
    }>;
  };
  accountability: {
    open_count: number;
    critical_open_count: number;
    overdue_count: number;
    resolved_pending_verification_count: number;
    verified_count: number;
    open_actions: ManagementAction[];
  };
  finance: {
    profitability?: Record<string, number | null>;
    liquidity?: Record<string, number | null>;
    efficiency?: Record<string, number | null>;
    capital_structure?: Record<string, number | null>;
    inputs?: Record<string, number | null>;
  };
  treasury: {
    opening_liquidity: Record<string, number>;
    total_expected_collections: number;
    total_approved_obligations: number;
    projected_closing_cash: number;
    minimum_projected_cash: number;
    breach_count: number;
    scenario: Record<string, number>;
  };
  audit: {
    control_pass_count: number;
    control_fail_count: number;
    controls: Record<string, boolean>;
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
      evidence_missing_count: number;
    };
    statutory_assessment: {
      status: string;
      jurisdiction: string;
      note: string;
    };
  };
  board_attention: Array<{
    severity: string;
    title: string;
    evidence: Record<string, unknown>;
    oversight_question: string;
  }>;
  opportunities: Array<{
    code: string;
    title: string;
    management_option: string;
    action_url: string;
  }>;
  prior_pack_summary?: {
    reference: string;
    generated_at?: string | null;
    enterprise_risk_score?: number | null;
    critical_priorities?: number | null;
    overdue_actions?: number | null;
    audit_control_failures?: number | null;
    projected_closing_cash?: number | null;
  } | null;
  governance_notice: string;
};

export type BoardGovernancePack = {
  id: string;
  reference: string;
  title: string;
  generated_at: string;
  period_start?: string | null;
  period_end?: string | null;
  status?: string;
  metrics: BoardGovernancePackMetrics;
};

export async function generateCompanyBoardPack(): Promise<BoardGovernancePack> {
  return (await api.post<BoardGovernancePack>("/company-operating-system/board-packs")).data;
}

export async function listCompanyBoardPacks(): Promise<BoardGovernancePack[]> {
  return (await api.get<BoardGovernancePack[]>("/company-operating-system/board-packs")).data;
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


export type ManagementAction = {
  id: string;
  reference: string;
  branch_id: string | null;
  source_signal_id: string;
  source: string;
  domain: string;
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  description: string | null;
  status: "assigned" | "in_progress" | "escalated" | "resolved" | "verified" | "cancelled";
  priority: string;
  assigned_user_id: string | null;
  created_by_user_id: string | null;
  due_at: string | null;
  overdue: boolean;
  days_overdue: number;
  escalation_level: number;
  recommended_action: string | null;
  action_url: string | null;
  source_signal: Record<string, unknown>;
  decision?: string | null;
  decision_note?: string | null;
  resolution?: string | null;
  resolved_by_user_id?: string | null;
  resolved_at?: string | null;
  verification_outcome?: "verified" | "reopened" | null;
  verified_by_user_id?: string | null;
  verified_at?: string | null;
  timeline: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export async function listManagementActions(): Promise<ManagementAction[]> {
  return (await api.get<ManagementAction[]>("/company-operating-system/management-actions")).data;
}

export async function createManagementAction(payload: {
  source_signal_id: string;
  source: string;
  domain: string;
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  why_now: string;
  recommended_action: string;
  action_url: string;
  evidence: Record<string, unknown>;
  assigned_user_id: string;
  due_at: string;
  branch_id?: string | null;
}): Promise<ManagementAction> {
  return (await api.post<ManagementAction>("/company-operating-system/management-actions", payload)).data;
}

export async function recordManagementDecision(id: string, payload: {
  decision: string;
  note: string;
  evidence_references?: string[];
}): Promise<ManagementAction> {
  return (await api.post<ManagementAction>(`/company-operating-system/management-actions/${id}/decisions`, payload)).data;
}

export async function resolveManagementAction(id: string, payload: {
  resolution: string;
  evidence_references?: string[];
}): Promise<ManagementAction> {
  return (await api.post<ManagementAction>(`/company-operating-system/management-actions/${id}/resolve`, payload)).data;
}

export async function verifyManagementAction(id: string, payload: {
  outcome: "verified" | "reopened";
  note: string;
  evidence_references?: string[];
}): Promise<ManagementAction> {
  return (await api.post<ManagementAction>(`/company-operating-system/management-actions/${id}/verify`, payload)).data;
}

export async function escalateOverdueManagementActions(): Promise<{ escalated_count: number; record_ids: string[] }> {
  return (await api.post("/company-operating-system/management-actions/escalate-overdue")).data;
}
