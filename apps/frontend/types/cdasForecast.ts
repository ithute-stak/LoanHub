export interface CdasForecastWindow {
  opportunity_count: number;
  monthly_deduction_value: number;
}

export interface CdasForecastMonth {
  month: string;
  label: string;
  opportunity_count: number;
  client_count: number;
  monthly_deduction_value: number;
  employer_count: number;
  agency_count: number;
}

export interface CdasForecastConcentration {
  name: string;
  book_now_count: number;
  book_now_value: number;
  scheduled_count: number;
  scheduled_value: number;
  total_opportunity_value: number;
}

export interface CdasForecastSummary {
  book_now_count: number;
  book_now_value: number;
  book_now_client_count: number;
  scheduled_count: number;
  scheduled_value: number;
  scheduled_client_count: number;
  next_3_months: CdasForecastWindow;
  next_6_months: CdasForecastWindow;
  next_12_months: CdasForecastWindow;
  excluded_quality_count: number;
  excluded_quality_value: number;
  unscheduled_count: number;
  unscheduled_value: number;
  later_known_count: number;
  later_known_value: number;
  missing_employer_client_count: number;
  peak_month: string | null;
  peak_month_value: number;
}

export interface CdasForecast {
  as_of: string;
  horizon_months: number;
  summary: CdasForecastSummary;
  months: CdasForecastMonth[];
  top_employers: CdasForecastConcentration[];
  top_agencies: CdasForecastConcentration[];
}
