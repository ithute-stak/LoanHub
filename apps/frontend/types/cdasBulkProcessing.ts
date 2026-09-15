import type { CdasBookingAnalyzeRequest, CdasBookingDecision } from "@/types/cdasBooking";

export interface CdasBulkAnalyzeRequest {
  items: CdasBookingAnalyzeRequest[];
}

export interface CdasBulkResultItem {
  index: number;
  status: "SUCCESS" | "ERROR";
  client_name: string | null;
  client_reference: string | null;
  analysis_id: string | null;
  archived_new: boolean;
  decision: CdasBookingDecision | null;
  next_possible_booking_date: string | null;
  assessed_available_amount: number | null;
  data_quality_issue_count: number;
  error: string | null;
}

export interface CdasBulkSummary {
  total: number;
  successful: number;
  errors: number;
  archived_new: number;
  archive_reused: number;
  review_required: number;
  decisions: Record<string, number>;
}

export interface CdasBulkAnalyzeResponse {
  summary: CdasBulkSummary;
  items: CdasBulkResultItem[];
}
