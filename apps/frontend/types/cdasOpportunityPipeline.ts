import type { CdasBookingOpportunity, CdasPipelineStage } from "@/types/cdasBooking";

export interface CdasOpportunityPipelineStage {
  id: CdasPipelineStage;
  label: string;
  order: number;
  count: number;
  monthly_deduction_value: number;
  items: CdasBookingOpportunity[];
}

export interface CdasOpportunityPipelineSummary {
  active: number;
  failed: number;
  booked: number;
  active_monthly_deduction_value: number;
  failed_monthly_deduction_value: number;
  booked_monthly_deduction_value: number;
}

export interface CdasOpportunityPipeline {
  stages: CdasOpportunityPipelineStage[];
  summary: CdasOpportunityPipelineSummary;
  total: number;
}
