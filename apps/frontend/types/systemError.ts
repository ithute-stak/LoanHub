export type SystemErrorLog = {
    id: string;
    request_id: string | null;
    fingerprint: string;
    user_id: string | null;
    company_id: string | null;
    branch_id: string | null;
    method: string | null;
    path: string;
    status_code: number;
    error_type: string;
    message: string;
    stack_trace: string | null;
    severity: string;
    environment: string | null;
    user_agent: string | null;
    context: Record<string, unknown>;
    occurrence_count: number;
    first_seen_at: string;
    last_seen_at: string;
    is_resolved: boolean;
    resolved_at: string | null;
    resolved_by_user_id: string | null;
    resolution_notes: string | null;
    created_at: string;
    updated_at: string;
};

export type SystemErrorListResponse = {
    items: SystemErrorLog[];
    total: number;
    unresolved_count: number;
    page: number;
    page_size: number;
};
