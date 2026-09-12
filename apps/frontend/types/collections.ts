import type { ManagedFile } from "@/types/files";

export type CollectionActionType = "call" | "visit" | "promise_to_pay" | "default_notice" | "court" | "other";

export type CollectionAction = {
  id: string;
  case_id: string;
  company_id: string;
  activity_type: string;
  outcome: string | null;
  notes: string | null;
  amount: number | null;
  follow_up_at: string | null;
  performed_at: string | null;
  performed_by_user_id: string | null;
  metadata_json: Record<string, unknown>;
  documents: ManagedFile[];
};

export type CollectionWorkspaceCase = {
  id: string;
  company_id: string;
  branch_id: string | null;
  borrower_id: string;
  loan_id: string;
  case_reference: string;
  status: string;
  stage: string;
  days_past_due: number;
  overdue_amount: number;
  outstanding_balance: number;
  priority: string;
  next_action_at: string | null;
  last_contact_at: string | null;
  legal_handover_at: string | null;
  assigned_to_user_id: string | null;
  action_claimed_by_user_id: string | null;
  action_claimed_at: string | null;
  action_claim_expires_at: string | null;
  promise_amount: number | null;
  promise_date: string | null;
  promise_status: string | null;
  write_off_at: string | null;
  recovered_amount: number;
  notes: string | null;
  created_at: string | null;
  loan_reference: string;
  loan_status: string;
  earliest_overdue_date: string | null;
  earliest_overdue_amount: number;
  borrower_name: string;
  phone: string | null;
  email: string | null;
  physical_address: string | null;
  next_of_kin_phones: string[];
  emergency_contact_phones: string[];
  bank_name: string | null;
  bank_account_holder: string | null;
  bank_account_last4: string | null;
  masked_bank_account: string | null;
  salary_account: boolean;
  last_action: CollectionAction | null;
};

export type UpcomingCourtAction = {
  activity_id: string;
  case_id: string;
  case_reference: string;
  borrower_name: string | null;
  loan_reference: string | null;
  court_date: string;
  court_name: string | null;
  court_case_number: string | null;
};

export type CollectionsWorkspace = {
  summary: {
    open_cases: number;
    legal_cases: number;
    one_day_past_due: number;
    total_overdue: number;
  };
  cases: CollectionWorkspaceCase[];
  upcoming_court: UpcomingCourtAction[];
};

export type CollectionDailyReport = {
  id: string;
  reference: string;
  title: string;
  scope_type: string;
  company_id: string | null;
  branch_id: string | null;
  period_start: string;
  period_end: string;
  generated_at: string;
  metrics: Record<string, unknown>;
  file: ManagedFile | null;
};
