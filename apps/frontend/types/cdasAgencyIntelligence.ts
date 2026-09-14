export interface CdasAgencyIntelligenceItem {
  agency_name: string;
  item_codes: string[];
  client_count: number;
  active_deduction_count: number;
  active_monthly_value: number;
  average_deduction_amount: number;
  own_booking_count: number;
  own_monthly_value: number;
  competitor_booking_count: number;
  competitor_monthly_value: number;
  competitor_value_share_percent: number;
  book_now_count: number;
  book_now_value: number;
  next_30_days_count: number;
  next_30_days_value: number;
  next_90_days_count: number;
  next_90_days_value: number;
  earliest_competitor_booking_date: string | null;
  data_quality_issue_count: number;
}

export interface CdasAgencyIntelligenceSummary {
  agency_count: number;
  client_count: number;
  active_deduction_count: number;
  active_monthly_value: number;
  own_monthly_value: number;
  competitor_monthly_value: number;
  book_now_count: number;
  book_now_value: number;
  next_30_days_count: number;
  next_30_days_value: number;
  next_90_days_count: number;
  next_90_days_value: number;
}

export interface CdasAgencyIntelligence {
  as_of: string;
  summary: CdasAgencyIntelligenceSummary;
  items: CdasAgencyIntelligenceItem[];
  total: number;
}
