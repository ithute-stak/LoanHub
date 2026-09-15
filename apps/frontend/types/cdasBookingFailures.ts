import type { CdasBookingOpportunity } from "@/types/cdasBooking";

export interface CdasBookingFailureRecord {
  id: string;
  opportunity_id: string;
  reason_code: string;
  reason_label: string;
  reason_details: string | null;
  failed_at: string;
  retry_eligible: boolean;
  retry_after: string | null;
  created_by_user_id: string | null;
  created_at: string;
}

export interface CdasBookingFailureRequest {
  reason_code: string;
  reason_details?: string;
  failed_at?: string;
  retry_eligible: boolean;
  retry_after?: string;
}

export interface CdasFailureOpportunity extends CdasBookingOpportunity {
  failure_count: number;
  latest_failure: CdasBookingFailureRecord | null;
  failure_history: CdasBookingFailureRecord[];
  retry_due: boolean;
}

export interface CdasBookingFailureWorkspace {
  as_of: string;
  summary: {
    failure_attempts: number;
    currently_failed: number;
    retryable: number;
    retry_due: number;
    non_retryable: number;
  };
  reason_counts: Array<{ reason_code: string; reason_label: string; count: number }>;
  reason_options: Array<{ value: string; label: string }>;
  recordable_opportunities: CdasBookingOpportunity[];
  items: CdasFailureOpportunity[];
  total: number;
}
