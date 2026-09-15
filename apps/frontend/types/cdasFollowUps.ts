import type { CdasBookingOpportunity } from "@/types/cdasBooking";

export type CdasContactChannel = "call" | "whatsapp" | "sms" | "email" | "other";
export type CdasContactOutcome =
  | "no_answer"
  | "interested"
  | "not_interested"
  | "call_back"
  | "documents_requested"
  | "documents_received"
  | "submitted"
  | "other";

export interface CdasContactRecord {
  id: string;
  opportunity_id: string;
  channel: CdasContactChannel;
  outcome: CdasContactOutcome;
  notes: string | null;
  contacted_at: string;
  next_follow_up_at: string | null;
  created_by_user_id: string | null;
  created_at: string;
}

export interface CdasFollowUpItem extends CdasBookingOpportunity {
  assigned_to_user_id: string | null;
  contact_count: number;
  latest_contact: CdasContactRecord | null;
  next_follow_up_at: string | null;
  is_follow_up_overdue: boolean;
  contacts: CdasContactRecord[];
}

export interface CdasFollowUpStaff {
  user_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  role: string;
}

export interface CdasFollowUpWorkspace {
  as_of: string;
  summary: {
    open: number;
    unassigned: number;
    overdue_follow_ups: number;
    scheduled_follow_ups: number;
    contacted: number;
  };
  items: CdasFollowUpItem[];
  staff: CdasFollowUpStaff[];
  total: number;
}

export interface CdasContactCreateRequest {
  channel: CdasContactChannel;
  outcome: CdasContactOutcome;
  notes?: string;
  contacted_at?: string;
  next_follow_up_at?: string;
}
