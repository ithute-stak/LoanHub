export interface CdasEmployerCompetitorAgency {
  agency_name: string;
  active_deduction_count: number;
}

export interface CdasEmployerIntelligenceItem {
  employer_name: string;
  client_count: number;
  active_deduction_count: number;
  active_monthly_value: number;
  average_monthly_deductions_per_client: number;
  own_monthly_value: number;
  competitor_monthly_value: number;
  competitor_share_percent: number;
  book_now_count: number;
  book_now_value: number;
  next_30_days_count: number;
  next_30_days_value: number;
  next_90_days_count: number;
  next_90_days_value: number;
  earliest_competitor_booking_date: string | null;
  capacity_known_count: number;
  available_capacity_total: number;
  average_available_capacity: number;
  no_headroom_count: number;
  data_quality_client_count: number;
  data_quality_issue_count: number;
  data_quality_client_percent: number;
  decision_counts: Record<string, number>;
  top_competitor_agencies: CdasEmployerCompetitorAgency[];
}

export interface CdasEmployerIntelligence {
  as_of: string;
  summary: {
    employer_count: number;
    client_count: number;
    missing_employer_clients: number;
    active_monthly_value: number;
    competitor_monthly_value: number;
    book_now_count: number;
    book_now_value: number;
    next_30_days_value: number;
    next_90_days_value: number;
    available_capacity_total: number;
    data_quality_client_count: number;
  };
  items: CdasEmployerIntelligenceItem[];
  total: number;
}
