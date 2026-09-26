import { api } from "@/lib/api";

export type CreditCondition = {
  id: string;
  source: string;
  condition_type: "pre_contract" | "pre_disbursement" | "monitoring";
  title: string;
  description: string | null;
  status: "open" | "satisfied" | "waived" | "failed";
  due_date: string | null;
  evidence_note: string | null;
  waiver_reason: string | null;
};

export type CommitteeVote = {
  id: string;
  user_id: string;
  role: string;
  decision: "approve" | "approve_with_conditions" | "reject" | "abstain";
  rationale: string;
  conditions: Array<{ title: string; description?: string | null; condition_type?: string; due_date?: string | null }>;
  voted_at: string | null;
};

export type UnderwritingAssessment = {
  id: string;
  revision: number;
  status: string;
  analyst_user_id: string | null;
  requested_amount: number;
  proposed_amount: number;
  proposed_installment: number;
  proposed_term: number;
  verified_income: number;
  household_expenses: number;
  existing_debt_installments: number;
  dti_percent: number;
  affordability_headroom: number;
  bureau_score: number | null;
  bureau_risk_grade: string | null;
  kyc_status: string | null;
  risk_score: number | null;
  risk_grade: string;
  recommendation: string;
  rationale: string;
  strengths: string[];
  weaknesses: string[];
  exceptions: string[];
  mitigants: string[];
  proposed_conditions: Array<{ title: string; description?: string | null; condition_type?: string; due_date?: string | null }>;
  evidence_snapshot: Record<string, unknown>;
  submitted_at: string | null;
};

export type CreditCommitteeCase = {
  id: string;
  case_reference: string;
  application_id: string;
  application_reference: string | null;
  application_status: string | null;
  borrower_id: string;
  borrower_name: string;
  requested_amount: number;
  term_count: number;
  application_type: string | null;
  channel: string | null;
  status: string;
  required_votes: number;
  approval_threshold_percent: number;
  maker_checker_required: boolean;
  analyst_user_id: string | null;
  analyst_submitted_at: string | null;
  evidence_snapshot: Record<string, any>;
  latest_assessment: UnderwritingAssessment | null;
  votes: CommitteeVote[];
  vote_summary: {
    counts: Record<string, number>;
    decisive_vote_count: number;
    approve_like_count: number;
    approval_ratio_percent: number;
    required_votes: number;
    approval_threshold_percent: number;
    quorum_met: boolean;
    computed_outcome: string | null;
  };
  conditions: CreditCondition[];
  final_decision: string | null;
  final_decision_reason: string | null;
  final_decided_at: string | null;
  override_used: boolean;
  override_reason: string | null;
  locked_at: string | null;
  created_at: string | null;
  events?: Array<{ id: string; event_type: string; actor_user_id: string | null; payload: Record<string, unknown>; created_at: string | null }>;
};

export type CommitteeDashboard = {
  summary: {
    awaiting_intake: number;
    underwriting: number;
    committee_review: number;
    awaiting_conditions: number;
    approved: number;
    rejected: number;
  };
  awaiting_intake: Array<{
    application_id: string;
    application_reference: string;
    borrower_id: string;
    borrower_name: string;
    requested_amount: number;
    term_count: number;
    status: string;
    submitted_at: string | null;
  }>;
  cases: CreditCommitteeCase[];
};

export type ConditionProposal = {
  title: string;
  description?: string | null;
  condition_type?: "pre_contract" | "pre_disbursement" | "monitoring";
  due_date?: string | null;
};

export async function getCommitteeDashboard(): Promise<CommitteeDashboard> {
  return (await api.get<CommitteeDashboard>("/credit-committee/dashboard")).data;
}

export async function intakeCommitteeApplication(applicationId: string): Promise<CreditCommitteeCase> {
  return (await api.post<CreditCommitteeCase>(`/credit-committee/intake/${applicationId}`)).data;
}

export async function getCommitteeCase(caseId: string): Promise<CreditCommitteeCase> {
  return (await api.get<CreditCommitteeCase>(`/credit-committee/cases/${caseId}`)).data;
}

export async function submitUnderwritingAssessment(caseId: string, payload: {
  proposed_amount?: number;
  proposed_installment?: number;
  proposed_term?: number;
  verified_income?: number;
  household_expenses?: number;
  existing_debt_installments?: number;
  dti_percent?: number;
  affordability_headroom?: number;
  bureau_score?: number;
  bureau_risk_grade?: string;
  risk_score?: number;
  risk_grade: "low" | "medium" | "high" | "critical";
  recommendation: "approve" | "approve_with_conditions" | "reject" | "refer";
  rationale: string;
  strengths: string[];
  weaknesses: string[];
  exceptions: string[];
  mitigants: string[];
  proposed_conditions: ConditionProposal[];
}): Promise<UnderwritingAssessment> {
  return (await api.post<UnderwritingAssessment>(`/credit-committee/cases/${caseId}/assessment`, payload)).data;
}

export async function castCommitteeVote(caseId: string, payload: {
  decision: "approve" | "approve_with_conditions" | "reject" | "abstain";
  rationale: string;
  conditions: ConditionProposal[];
}) {
  return (await api.put<{ vote: { id: string; decision: string }; case: CreditCommitteeCase }>(`/credit-committee/cases/${caseId}/vote`, payload)).data;
}

export async function finalizeCommitteeCase(caseId: string, payload: {
  reason?: string;
  decision?: "approved" | "conditionally_approved" | "rejected";
  override_reason?: string;
}) {
  return (await api.post<CreditCommitteeCase>(`/credit-committee/cases/${caseId}/finalize`, payload)).data;
}

export async function updateCommitteeCondition(caseId: string, conditionId: string, payload: {
  status: "open" | "satisfied" | "waived" | "failed";
  evidence_note?: string;
  waiver_reason?: string;
}) {
  return (await api.patch<{ condition: CreditCondition; case: CreditCommitteeCase }>(`/credit-committee/cases/${caseId}/conditions/${conditionId}`, payload)).data;
}

export async function updateCommitteeGovernance(caseId: string, payload: {
  required_votes: number;
  approval_threshold_percent: number;
  maker_checker_required: boolean;
  reason: string;
}) {
  return (await api.patch<CreditCommitteeCase>(`/credit-committee/cases/${caseId}/governance`, payload)).data;
}

export async function downloadCreditMemo(item: CreditCommitteeCase) {
  const response = await api.get<Blob>(`/credit-committee/cases/${item.id}/credit-memo.pdf`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${item.case_reference}-credit-memo.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5_000);
}
