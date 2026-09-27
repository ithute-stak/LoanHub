import { api } from "@/lib/api";

export type CreditLossProvisionLine = {
  id: string;
  loan_id: string;
  folio_number: string;
  stage: 1 | 2 | 3;
  days_past_due: number;
  exposure: number;
  provision_rate: number;
  required_allowance: number;
  rationale: string[];
  evidence: Record<string, unknown>;
  write_off_candidate: boolean;
};

export type CreditLossProvisionRun = {
  id: string;
  run_reference: string;
  as_of_date: string;
  status: string;
  loan_count: number;
  gross_exposure: number;
  required_allowance: number;
  prior_allowance: number;
  allowance_movement: number;
  stage_1_allowance: number;
  stage_2_allowance: number;
  stage_3_allowance: number;
  management_overlay: number;
  overlay_reason: string | null;
  summary: Record<string, unknown>;
  journal_entry_id: string | null;
  generated_at: string;
  approved_at: string | null;
  lines?: CreditLossProvisionLine[];
};

export type CreditLossProvisionOverview = {
  latest: CreditLossProvisionRun | null;
  history: CreditLossProvisionRun[];
  guardrails: {
    maker_checker_required: boolean;
    approval_posts_accounting_journal: boolean;
    formal_accounting_policy_review_required: boolean;
  };
};

export async function getCreditLossProvisionOverview(): Promise<CreditLossProvisionOverview> {
  return (await api.get<CreditLossProvisionOverview>("/credit-loss-provisioning/overview")).data;
}

export async function createCreditLossProvisionRun(payload: {
  as_of_date: string;
  management_overlay?: number;
  overlay_reason?: string | null;
}): Promise<CreditLossProvisionRun> {
  return (await api.post<CreditLossProvisionRun>("/credit-loss-provisioning/runs", payload)).data;
}

export async function getCreditLossProvisionRun(runId: string): Promise<CreditLossProvisionRun> {
  return (await api.get<CreditLossProvisionRun>(`/credit-loss-provisioning/runs/${runId}`)).data;
}

export async function approveCreditLossProvisionRun(runId: string): Promise<CreditLossProvisionRun> {
  return (await api.post<CreditLossProvisionRun>(`/credit-loss-provisioning/runs/${runId}/approve`)).data;
}
