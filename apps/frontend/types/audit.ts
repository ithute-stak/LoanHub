export type AuditLog = {
    id: string;
    user_id: string | null;
    company_id: string | null;
    branch_id: string | null;
    action: string;
    table_name: string | null;
    entity_type: string | null;
    record_id: string | null;
    description: string | null;
    actor_role: string | null;
    actor_name: string | null;
    company_name: string | null;
    branch_name: string | null;
    entity_reference: string | null;
    severity: string;
    status: string;
    before_data: Record<string, unknown>;
    after_data: Record<string, unknown>;
    changed_fields: string[];
    event_data: Record<string, unknown>;
    request_id: string | null;
    ip_address: string | null;
    user_agent: string | null;
    duration_ms: number | null;
    created_at: string;
};

export type AuditLogListResponse = {
    items: AuditLog[];
    total: number;
    page: number;
    page_size: number;
};
