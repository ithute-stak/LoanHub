import { api } from "@/lib/api";

export type CollectionWorkItem = {
  id: string;
  case_id: string;
  case_reference: string | null;
  loan_id: string;
  loan_reference: string | null;
  folio_number: string | null;
  borrower_id: string;
  borrower_email: string | null;
  assigned_to_user_id: string | null;
  assigned_to: string | null;
  action_type: string;
  treatment_code: string;
  recovery_path: string;
  priority_score: number;
  priority: string;
  reason: string | null;
  due_at: string;
  status: string;
  attempt_count: number;
  context_snapshot: Record<string, unknown>;
};

export type CollectionAutomationDashboard = {
  summary: {
    open_work_items: number;
    urgent_work_items: number;
    overdue_work_items: number;
    broken_promises: number;
    legal_ready_cases: number;
    total_overdue: number;
  };
  recovery_paths: Record<string, number>;
  queue: CollectionWorkItem[];
  productivity: Array<{
    user_id: string | null;
    name: string;
    actions: number;
    promises: number;
    recovered: number;
  }>;
};

export type CollectionTreatmentPolicy = {
  id: string;
  name: string;
  version: number;
  is_active: boolean;
  strategy: {
    bands?: Array<{
      min_dpd: number;
      max_dpd: number;
      stage: string;
      action: string;
      treatment: string;
      due_hours?: number;
    }>;
    broken_promise_action?: string;
    broken_promise_treatment?: string;
    broken_promise_due_hours?: number;
  };
};

export async function getCollectionAutomationDashboard(): Promise<CollectionAutomationDashboard> {
  return (await api.get<CollectionAutomationDashboard>("/collections/automation/dashboard")).data;
}

export async function runCollectionAutomation() {
  return (await api.post("/collections/automation/run")).data;
}

export async function getCollectionTreatmentPolicy(): Promise<CollectionTreatmentPolicy> {
  return (await api.get<CollectionTreatmentPolicy>("/collections/automation/policy")).data;
}

export async function updateCollectionTreatmentPolicy(strategy: CollectionTreatmentPolicy["strategy"]): Promise<CollectionTreatmentPolicy> {
  return (await api.put<CollectionTreatmentPolicy>("/collections/automation/policy", { strategy })).data;
}

export async function completeCollectionWorkItem(itemId: string, notes?: string | null): Promise<CollectionWorkItem> {
  return (await api.post<CollectionWorkItem>(`/collections/automation/work-items/${itemId}/complete`, { notes })).data;
}

export async function assignCollectionWorkItem(itemId: string, userId: string | null): Promise<CollectionWorkItem> {
  return (await api.put<CollectionWorkItem>(`/collections/automation/work-items/${itemId}/assignment`, {
    assigned_to_user_id: userId,
  })).data;
}

export async function getCollectionLegalReadiness(caseId: string) {
  return (await api.get(`/collections/automation/cases/${caseId}/legal-readiness`)).data;
}

export async function escalateCollectionCaseToLegal(caseId: string, payload?: { override_readiness?: boolean; override_reason?: string | null }) {
  return (await api.post(`/collections/automation/cases/${caseId}/escalate-legal`, payload ?? {})).data;
}
