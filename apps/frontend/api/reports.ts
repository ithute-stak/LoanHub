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


export type DailyIssuanceReport = {
    company_id: string;
    branch_id: string | null;
    period_start: string;
    period_end: string;
    basis: string;
    date_basis: string;
    totals: {
        loans_issued: number;
        principal_issued: string;
        expected_contractual_return: string;
        expected_return_above_principal: string;
    };
    cash_to_borrowers: string | null;
    breakdown: {
        new_loans_count: number;
        new_loans_principal: string;
        new_loans_cash_to_borrowers: string;
        topups_count: number;
        topups_principal: string;
        topups_cash_to_borrowers: string;
        topups_settlements: string;
    } | null;
    details: Array<{
        date: string;
        time: string;
        loan_reference: string;
        folio_number: string;
        client_name: string;
        branch: string;
        disbursed_by: string;
        is_top_up: boolean;
        principal_issued: string;
        cash_to_borrower: string;
        top_up_settlement: string;
        expected_contractual_return: string;
        installments: number;
        installment_amount: string;
        first_payment_due: string | null;
    }>;
    daily: Array<{
        date: string;
        loans_issued: number;
        principal_issued: string;
        expected_contractual_return: string;
        expected_return_above_principal: string;
    }>;
};

export type DailyIssuanceFilters = {
    period_start: string;
    period_end: string;
    branch_id?: string;
};

export async function getDailyIssuanceReport(filters: DailyIssuanceFilters): Promise<DailyIssuanceReport> {
    const response = await api.get<DailyIssuanceReport>("/reports/daily-issuance", { params: { ...filters, include_details: true } });
    return response.data;
}

export async function downloadDailyIssuanceReport(
    filters: DailyIssuanceFilters,
    format: "csv" | "pdf" | "xlsx",
): Promise<void> {
    const response = await api.get<Blob>(`/reports/daily-issuance.${format}`, {
        params: filters,
        responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    try {
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `loanhub-daily-issuance.${format}`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
    } finally {
        URL.revokeObjectURL(url);
    }
}
