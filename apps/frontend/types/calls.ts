export type CallManagementPolicy = {
  id: string;
  company_id: string;
  recording_enabled: boolean;
  recording_retention_days: number;
  call_metadata_retention_months: number;
  automatic_deletion_enabled: boolean;
  live_monitoring_enabled: boolean;
  manager_downloads_enabled: boolean;
  legal_hold_enabled: boolean;
  recording_notice: string;
};

export type CallRecording = {
  id: string;
  status: string;
  mime_type: string | null;
  size_bytes: number | null;
  duration_seconds: number | null;
  deletion_at: string | null;
  deleted_at: string | null;
  legal_hold: {
    id: string;
    reason: string;
    placed_at: string | null;
  } | null;
};

export type CallQualityReview = {
  id: string;
  call_id: string;
  reviewer_user_id: string | null;
  reviewer_name: string | null;
  score: number;
  compliance_status: string;
  customer_care_status: string;
  notes: string | null;
  reviewed_at: string | null;
};

export type ClientCall = {
  id: string;
  company_id: string;
  branch_id: string | null;
  employee_staff_id: string;
  employee_name: string | null;
  device_id: string | null;
  borrower_id: string | null;
  borrower_name: string | null;
  phone_number: string;
  normalized_phone: string;
  loan_id: string | null;
  loan_reference: string | null;
  loan_balance: number | null;
  direction: "incoming" | "outgoing" | string;
  status: string;
  started_at: string | null;
  answered_at: string | null;
  ended_at: string | null;
  duration_seconds: number;
  recording_status: string;
  outcome: string | null;
  notes: string | null;
  is_live: boolean;
  recording: CallRecording | null;
  quality_reviews: CallQualityReview[];
  permissions?: {
    can_edit_description: boolean;
    can_delete: boolean;
  } | null;
};

export type CallDashboard = {
  summary: {
    today_calls: number;
    incoming: number;
    outgoing: number;
    clients_contacted: number;
    live_calls: number;
    recordings_available: number;
    average_duration_seconds: number;
  };
  recent_calls: ClientCall[];
  policy: CallManagementPolicy;
  media_configured: boolean;
  employee_performance?: Array<{
    staff_id: string;
    employee_name: string | null;
    total_calls: number;
    incoming: number;
    outgoing: number;
    clients_contacted: number;
    recordings: number;
    average_duration_seconds: number;
  }>;
};

export type CallClient = {
  borrower_id: string;
  name: string | null;
  phone: string | null;
  loans: Array<{
    id: string;
    loan_reference: string;
    status: string;
    balance: number;
    is_overdue: boolean;
    branch_id?: string | null;
  }>;
};

export type CallClientDetail = CallClient & {
  contacts: Array<{
    name: string;
    relationship: string;
    phone: string;
    is_primary: boolean;
    is_call_permitted: boolean;
  }>;
  recent_calls: ClientCall[];
};

export type DesktopCallingCapability = {
  media_configured: boolean;
  outbound_configured: boolean;
  calling_available: boolean;
  recording_enabled: boolean;
  recording_notice: string | null;
};

export type EmployeeMediaSession = {
  server_url: string;
  token: string;
  room_name: string;
  expires_in: number;
};

export type LiveMonitorSession = {
  server_url: string;
  token: string;
  room_name: string;
  expires_in: number;
  mode: "listen_only";
};
