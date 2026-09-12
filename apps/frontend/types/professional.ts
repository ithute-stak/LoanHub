export type DirectApplicationStatus = "submitted" | "under_review" | "approved" | "rejected";

export type DirectLoanApplication = {
  id: string;
  company_id: string;
  branch_id: string | null;
  borrower_id: string;
  product_id: string | null;
  application_reference: string;
  channel: "internal_client_offer" | string;
  requested_amount: number;
  approved_amount: number | null;
  interest_rate: number | null;
  term_count: number;
  repayment_type: string;
  purpose: string | null;
  installment_due_dates: string[];
  status: DirectApplicationStatus | string;
  affordability_snapshot: Record<string, unknown>;
  credit_warning: Record<string, unknown>;
  submitted_at: string | null;
  reviewed_at: string | null;
  reviewed_by_user_id: string | null;
  approved_at: string | null;
  approved_by_user_id: string | null;
  rejected_at: string | null;
  rejected_by_user_id: string | null;
  decision_notes: string | null;
  captured_by_user_id: string | null;
  loan_id: string | null;
  loan_reference: string | null;
  borrower_name: string;
  account_reference: string | null;
  product_name: string | null;
  created_at: string;
  updated_at: string;
};

export type DirectLoanApplicationCreate = {
  borrower_id: string;
  branch_id?: string | null;
  product_id?: string | null;
  requested_amount: number;
  term_count: number;
  repayment_type?: "monthly";
  purpose?: string | null;
  installment_due_dates: string[];
};

export type DirectApplicationApprovePayload = {
  product_id: string;
  approved_amount: number;
  interest_rate?: number | null;
  processing_fee?: number | null;
  installment_due_dates: string[];
  decision_notes?: string | null;
};

export type DirectApplicationReviewPayload = {
  notes?: string | null;
};

export type DirectApplicationRejectPayload = {
  reason: string;
};

export type DirectApplicationApproveResult = {
  application: DirectLoanApplication;
  loan: {
    id: string;
    loan_reference: string;
    status: string;
    principal_amount: number;
    total_repayable: number;
    installment_amount: number;
  };
};

export type PlatformSuggestion = {
  id: string;
  reference: string;
  company_id: string | null;
  branch_id: string | null;
  submitted_by_user_id: string | null;
  title: string;
  category: string;
  description: string;
  priority: string;
  status: string;
  platform_response: string | null;
  created_at: string;
  updated_at: string;
};

export type PlatformSuggestionCreate = {
  title: string;
  category?:
    | "feature_request"
    | "support_query"
    | "payment_issue"
    | "technical_issue"
    | "training";
  description: string;
  priority?: "low" | "normal" | "high" | "urgent";
};

export type SystemAssistantResponse = {
  answer: string;
  action_path?: string | null;
  action_label?: string | null;
};
