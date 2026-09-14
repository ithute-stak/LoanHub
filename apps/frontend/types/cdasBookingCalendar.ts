export type CdasBookingCalendarBucket =
  | "OVERDUE"
  | "TODAY"
  | "THIS_WEEK"
  | "NEXT_30_DAYS"
  | "NEXT_90_DAYS"
  | "LATER"
  | "UNSCHEDULED"
  | "BOOKED";

export interface CdasBookingCalendarEvent {
  id: string;
  client_name: string | null;
  client_reference: string | null;
  agency_name: string | null;
  item_code: string | null;
  reference_no: string | null;
  deduction_amount: number;
  booking_date: string | null;
  alert_start_date: string | null;
  expiry_date: string | null;
  booked_at: string | null;
  state: "UPCOMING" | "BOOK_NOW" | "BOOKED";
  bucket: CdasBookingCalendarBucket;
  days_from_today: number | null;
  is_overdue: boolean;
  analysis_snapshot: Record<string, unknown>;
}

export interface CdasBookingCalendarSummary {
  open: number;
  overdue: number;
  today: number;
  this_week: number;
  next_30_days: number;
  next_90_days: number;
  later: number;
  unscheduled: number;
  booked: number;
}

export interface CdasBookingCalendar {
  as_of: string;
  week_end: string;
  next_30_days_end: string;
  next_90_days_end: string;
  summary: CdasBookingCalendarSummary;
  events: CdasBookingCalendarEvent[];
  total: number;
}
