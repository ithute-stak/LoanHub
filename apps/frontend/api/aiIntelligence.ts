import { api } from "@/lib/api";

export type AIIntelligenceRun = {
  id: string;
  run_reference: string;
  run_type: string;
  status: string;
  model_version: string;
  evidence_cutoff_at: string;
  insight_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  summary: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
};

export type AIIntelligenceInsight = {
  id: string;
  run_id: string;
  insight_type: string;
  domain: string;
  severity: "critical" | "high" | "medium" | "low";
  confidence_percent: number;
  entity_type: string;
  entity_id: string | null;
  folio_number: string | null;
  title: string;
  explanation: string;
  recommended_action: string;
  rationale: string[];
  evidence: Record<string, unknown>;
  status: string;
  feedback: string | null;
  feedback_note: string | null;
  reviewed_at: string | null;
};

export type AIIntelligenceOverview = {
  latest_run: AIIntelligenceRun | null;
  open_count: number;
  critical_count: number;
  high_count: number;
  domain_counts: Record<string, number>;
  top_insights: AIIntelligenceInsight[];
  guardrails: {
    advisory_only: boolean;
    automatic_credit_decisions: boolean;
    automatic_disbursement: boolean;
    human_review_required: boolean;
  };
};

export async function getAIIntelligenceOverview(): Promise<AIIntelligenceOverview> {
  return (await api.get<AIIntelligenceOverview>("/ai-intelligence/overview")).data;
}

export async function runAIIntelligence(): Promise<AIIntelligenceRun> {
  return (await api.post<AIIntelligenceRun>("/ai-intelligence/runs")).data;
}

export async function getAIIntelligenceInsights(params?: {
  status?: string;
  severity?: string;
  domain?: string;
}): Promise<AIIntelligenceInsight[]> {
  return (await api.get<AIIntelligenceInsight[]>("/ai-intelligence/insights", { params })).data;
}

export async function reviewAIInsight(
  insightId: string,
  payload: { status: "reviewed" | "dismissed" | "actioned"; feedback?: string | null; note?: string | null },
): Promise<AIIntelligenceInsight> {
  return (await api.patch<AIIntelligenceInsight>(`/ai-intelligence/insights/${insightId}`, payload)).data;
}
