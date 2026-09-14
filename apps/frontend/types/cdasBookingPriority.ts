export type CdasBookingPriorityBand = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "BOOKED";

export interface CdasBookingPriorityComponents {
  urgency: number;
  value: number;
  readiness: number;
  quality: number;
}

export interface CdasBookingPriorityItem {
  id: string;
  client_name: string | null;
  client_reference: string | null;
  agency_name: string | null;
  reference_no: string | null;
  deduction_amount: number;
  booking_date: string | null;
  expiry_date: string | null;
  state: "UPCOMING" | "BOOK_NOW" | "BOOKED";
  days_from_today: number | null;
  decision: "ALREADY_BOOKED" | "BOOK_NOW" | "WAIT_UNTIL" | "REVIEW_REQUIRED" | null;
  assessed_available_amount: number | null;
  data_quality_issue_count: number;
  amount_owing: number | null;
  booking_months: number | null;
  priority_score: number;
  priority_band: CdasBookingPriorityBand;
  priority_components: CdasBookingPriorityComponents;
  priority_reasons: string[];
  priority_warnings: string[];
}

export interface CdasBookingPrioritySummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  review_required: number;
  booked: number;
  open: number;
  monthly_deduction_value: number;
}

export interface CdasBookingPriorityQueue {
  as_of: string;
  summary: CdasBookingPrioritySummary;
  items: CdasBookingPriorityItem[];
  total: number;
}
