import type { ManagedFile } from "@/types/files";

export type ReportMetrics = Record<string, string | number>;

export type GeneratedReport = {
    id: string;
    reference: string;
    scope_type: string;
    company_id: string | null;
    branch_id: string | null;
    schedule_id: string | null;
    title: string;
    report_type: string;
    output_format: string;
    period_start: string;
    period_end: string;
    status: string;
    metrics: ReportMetrics;
    generated_at: string;
    file: ManagedFile | null;
};

export type ReportSchedule = {
    id: string;
    scope_type: string;
    company_id: string | null;
    branch_id: string | null;
    name: string;
    report_type: string;
    frequency: string;
    output_format: string;
    recipients: string[];
    is_active: boolean;
    next_run_at: string;
    last_run_at: string | null;
    last_status: string | null;
    last_error: string | null;
    created_at: string;
};

export type ReportSummary = {
    scope_type: string;
    company_id: string | null;
    branch_id: string | null;
    period_start: string;
    period_end: string;
    metrics: ReportMetrics;
};
