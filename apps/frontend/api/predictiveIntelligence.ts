import { api } from "@/lib/api";

export type PredictiveRun = {
  id: string;
  run_reference: string;
  run_type: string;
  status: string;
  model_version: string;
  as_of_date: string;
  source_snapshot_date: string;
  previous_snapshot_date: string | null;
  loan_count: number;
  stable_count: number;
  watch_count: number;
  elevated_count: number;
  high_count: number;
  critical_count: number;
  projected_par30_entry_count: number;
  observed_collection_rate: number;
  summary: Record<string, unknown>;
  generated_at: string;
};

export type PredictiveSignal = {
  id: string;
  run_id: string;
  loan_id: string;
  borrower_id: string;
  folio_number: string;
  loan_reference: string | null;
  risk_score: number;
  risk_band: "stable" | "watch" | "elevated" | "high" | "critical";
  current_dpd: number;
  previous_dpd: number | null;
  dpd_change: number | null;
  current_bucket: string;
  previous_bucket: string | null;
  first_payment_default: boolean;
  projected_par30_entry: boolean;
  stress_bucket_30d: string;
  outstanding_balance: number;
  rationale: string[];
  recommended_action: string;
  evidence: Record<string, unknown>;
};

export type PredictiveCashflow = {
  id: string;
  run_id: string;
  horizon_days: number;
  period_end: string;
  contractual_due: number;
  expected_collection: number;
  observed_collection_rate: number;
  due_installment_count: number;
  history_installment_count: number;
  confidence_band: string;
  method: string;
  evidence: Record<string, unknown>;
};

export type PredictiveOverview = {
  latest_run: PredictiveRun | null;
  signals: PredictiveSignal[];
  cashflow: PredictiveCashflow[];
  high_risk_exposure: number;
  guardrails: {
    advisory_only: boolean;
    calibrated_probability_model: boolean;
    automatic_credit_decisions: boolean;
    automatic_collection_actions: boolean;
  };
};

export async function getPredictiveOverview(): Promise<PredictiveOverview> {
  return (await api.get<PredictiveOverview>("/predictive-intelligence/overview")).data;
}

export async function runPredictiveIntelligence(): Promise<PredictiveRun> {
  return (await api.post<PredictiveRun>("/predictive-intelligence/runs")).data;
}

export async function getPredictiveSignals(params?: {
  risk_band?: string;
  projected_par30_entry?: boolean;
}): Promise<PredictiveSignal[]> {
  return (await api.get<PredictiveSignal[]>("/predictive-intelligence/signals", { params })).data;
}
