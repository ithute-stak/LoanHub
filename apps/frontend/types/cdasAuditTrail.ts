export interface CdasAuditIntegrity {
  sealed: boolean;
  hash_version: string | null;
  previous_hash: string | null;
  event_hash: string | null;
  sealed_at: string | null;
}

export interface CdasAuditEvent {
  id: string;
  timestamp: string | null;
  user_id: string | null;
  actor_name: string | null;
  actor_role: string | null;
  action: string;
  entity_type: string | null;
  record_id: string | null;
  description: string | null;
  severity: string;
  before_data: Record<string, unknown>;
  after_data: Record<string, unknown>;
  changed_fields: string[];
  event_data: Record<string, unknown>;
  request_id: string | null;
  integrity: CdasAuditIntegrity;
}

export interface CdasAuditActorOption {
  user_id: string;
  name: string;
  role: string | null;
}

export interface CdasAuditTrailResponse {
  items: CdasAuditEvent[];
  total: number;
  page: number;
  page_size: number;
  summary: {
    formal_events_sampled: number;
    sealed_events_sampled: number;
    unsealed_events_sampled: number;
  };
  options: {
    actions: string[];
    entity_types: string[];
    actors: CdasAuditActorOption[];
  };
}

export interface CdasAuditTrailParams {
  action?: string;
  entity_type?: string;
  actor_user_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  page?: number;
  page_size?: number;
}
