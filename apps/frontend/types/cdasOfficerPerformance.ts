export interface CdasOfficerPerformanceSummary {
  staff_total: number;
  active_staff: number;
  assigned_open: number;
  unassigned_open: number;
  book_now_open: number;
  overdue_follow_ups: number;
  contacts_last_30_days: number;
  booked_total: number;
  failed_total: number;
}

export interface CdasOfficerPerformanceRow {
  user_id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  role?: string | null;
  is_active: boolean;
  assigned_total: number;
  open_assigned: number;
  book_now_assigned: number;
  upcoming_assigned: number;
  open_monthly_deduction_value: number;
  overdue_follow_ups: number;
  scheduled_follow_ups: number;
  uncontacted_open: number;
  contacts_total: number;
  contacts_last_30_days: number;
  contact_outcomes_last_30_days: Record<string, number>;
  contact_channels_last_30_days: Record<string, number>;
  booked_assigned: number;
  failed_assigned: number;
  booked_by_officer: number;
  failures_reported_last_30_days: number;
}

export interface CdasOfficerUnassignedItem {
  id: string;
  client_name?: string | null;
  client_reference?: string | null;
  state: string;
  pipeline_stage: string;
  booking_open_date?: string | null;
  opportunity_agency_name?: string | null;
  opportunity_deduction_amount: number;
}

export interface CdasOfficerPerformanceWorkspace {
  as_of: string;
  window_days: number;
  summary: CdasOfficerPerformanceSummary;
  officers: CdasOfficerPerformanceRow[];
  unassigned_items: CdasOfficerUnassignedItem[];
}
