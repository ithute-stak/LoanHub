import { api } from "@/lib/api";
import type { GeneratedReport, ReportSchedule, ReportSummary } from "@/types/reporting";

export async function getReportSummary(params: Record<string, string | undefined>): Promise<ReportSummary> {
    const response = await api.get<ReportSummary>("/reports/summary", { params });
    return response.data;
}

export async function listReports(params?: Record<string, string | undefined>): Promise<GeneratedReport[]> {
    const response = await api.get<GeneratedReport[]>("/reports", { params });
    return response.data;
}

export async function generateReport(payload: {
    report_type: string;
    output_format: string;
    scope_type: string;
    company_id?: string;
    branch_id?: string;
    period_start: string;
    period_end: string;
}): Promise<GeneratedReport> {
    const response = await api.post<GeneratedReport>("/reports/generate", payload);
    return response.data;
}

export async function listReportSchedules(params?: { company_id?: string }): Promise<ReportSchedule[]> {
    const response = await api.get<ReportSchedule[]>("/reports/schedules", { params });
    return response.data;
}

export async function createReportSchedule(payload: {
    name: string;
    report_type: string;
    frequency: string;
    output_format: string;
    scope_type: string;
    company_id?: string;
    branch_id?: string;
    recipients: string[];
    is_active: boolean;
}): Promise<ReportSchedule> {
    const response = await api.post<ReportSchedule>("/reports/schedules", payload);
    return response.data;
}

export async function deleteReportSchedule(scheduleId: string): Promise<void> {
    await api.delete(`/reports/schedules/${scheduleId}`);
}
