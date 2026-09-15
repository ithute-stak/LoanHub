import type { CdasAnalysisRecord, CdasBookingDecision, CdasOpportunityState, CdasPipelineStage } from "@/types/cdasBooking";

export interface CdasAdvancedSearchParams {
  q?: string;
  employer?: string;
  agency?: string;
  decision?: string;
  state?: string;
  pipeline_stage?: string;
  assigned_to_user_id?: string;
  quality?: "all" | "clean" | "issues";
  booking_from?: string;
  booking_to?: string;
  analyzed_from?: string;
  analyzed_to?: string;
  min_capacity?: number;
  max_capacity?: number;
  min_deduction?: number;
  max_deduction?: number;
  limit?: number;
}

export interface CdasAdvancedSearchOpportunity {
  id: string;
  client_name: string | null;
  client_reference: string | null;
  employer: string | null;
  decision: CdasBookingDecision | null;
  assessed_available_amount: number | null;
  data_quality_issue_count: number;
  state: CdasOpportunityState;
  pipeline_stage: CdasPipelineStage;
  assigned_to_user_id: string | null;
  assigned_to_name: string | null;
  booking_open_date: string | null;
  opportunity_agency_name: string | null;
  opportunity_item_code: string | null;
  opportunity_reference_no: string | null;
  opportunity_deduction_amount: number;
  created_at: string;
  updated_at: string;
}

export interface CdasAdvancedSearchOfficer {
  user_id: string;
  name: string;
  role: string;
  is_active: boolean;
}

export interface CdasAdvancedSearchResponse {
  summary: {
    analysis_total: number;
    analysis_matches: number;
    opportunity_total: number;
    opportunity_matches: number;
  };
  analyses: CdasAnalysisRecord[];
  opportunities: CdasAdvancedSearchOpportunity[];
  truncated: {
    analyses: boolean;
    opportunities: boolean;
  };
  options: {
    employers: string[];
    agencies: string[];
    decisions: string[];
    states: string[];
    pipeline_stages: string[];
    officers: CdasAdvancedSearchOfficer[];
  };
}
