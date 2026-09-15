export interface CdasManagementOperations {
  active_opportunities: number;
  active_monthly_deduction_value: number;
  overdue_booking_windows: number;
  due_today: number;
  next_30_days: number;
  critical_priorities: number;
  high_priorities: number;
  booked_total: number;
}

export interface CdasManagementWorkflow {
  unassigned_open: number;
  overdue_follow_ups: number;
  scheduled_follow_ups: number;
  contacted_open: number;
  currently_failed: number;
  retryable: number;
  retry_due: number;
  failure_attempts: number;
}

export interface CdasManagementDataQuality {
  profiles_checked: number;
  profiles_with_issues: number;
  blocker_clients: number;
  total_issues: number;
  blocker_issues: number;
  warning_issues: number;
  excluded_monthly_amount: number;
  duplicate_candidate_pairs: number;
  high_confidence_duplicate_pairs: number;
  affected_duplicate_profiles: number;
  clients_with_material_changes: number;
  material_changes: number;
}

export interface CdasManagementForecastWindow {
  opportunity_count: number;
  monthly_deduction_value: number;
}

export interface CdasManagementForecast {
  book_now_count: number;
  book_now_value: number;
  scheduled_count: number;
  scheduled_value: number;
  next_3_months: CdasManagementForecastWindow;
  next_6_months: CdasManagementForecastWindow;
  next_12_months: CdasManagementForecastWindow;
  excluded_quality_count: number;
  excluded_quality_value: number;
  unscheduled_count: number;
  peak_month: string | null;
  peak_month_value: number;
}

export interface CdasManagementPipelineStage {
  id: string;
  label: string;
  order: number;
  count: number;
  monthly_deduction_value: number;
}

export interface CdasManagementFailureReason {
  reason_code: string;
  reason_label: string;
  count: number;
}

export interface CdasManagementForecastMonth {
  month: string;
  label: string;
  opportunity_count: number;
  client_count: number;
  monthly_deduction_value: number;
  employer_count: number;
  agency_count: number;
}

export interface CdasManagementConcentration {
  book_now_count: number;
  book_now_value: number;
  scheduled_count: number;
  scheduled_value: number;
  total_opportunity_value: number;
}

export interface CdasManagementEmployerConcentration extends CdasManagementConcentration {
  employer: string;
}

export interface CdasManagementAgencyConcentration extends CdasManagementConcentration {
  agency: string;
}

export interface CdasManagementDashboard {
  as_of: string | null;
  operations: CdasManagementOperations;
  workflow: CdasManagementWorkflow;
  data_quality: CdasManagementDataQuality;
  forecast: CdasManagementForecast;
  pipeline_stages: CdasManagementPipelineStage[];
  failure_reasons: CdasManagementFailureReason[];
  forecast_months: CdasManagementForecastMonth[];
  top_employers: CdasManagementEmployerConcentration[];
  top_agencies: CdasManagementAgencyConcentration[];
  policy: {
    aggregate_only: boolean;
    automated_credit_decision: boolean;
    description: string;
  };
}
