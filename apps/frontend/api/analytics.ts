

export type ManagementCommandIntelligence = {
    generated_at: string;
    date_from: string;
    date_to: string;
    branch_id?: string | null;
    command_status: "controlled" | "attention" | "high" | "critical";
    enterprise_risk_score: number;
    enterprise_risk_level: string;
    priority_counts: {
        critical: number;
        high: number;
        medium: number;
        total: number;
    };
    priority_actions: Array<{
        id: string;
        rank: number;
        source: string;
        domain: string;
        severity: "low" | "medium" | "high" | "critical";
        priority_score: number;
        title: string;
        why_now: string;
        recommended_action: string;
        action_url: string;
        evidence: Record<string, unknown>;
        decision_mode: "human_review";
    }>;
    opportunities: Array<{
        code: string;
        title: string;
        evidence: Record<string, unknown>;
        management_option: string;
        action_url: string;
    }>;
    executive_metrics: Record<string, {
        label: string;
        value: number;
        format: "money" | "integer" | "percent" | "decimal";
        change_percent?: number | null;
    }>;
    policy_note: string;
};
import { api } from "@/lib/api";
import type { AnalyticsDashboard, AnalyticsFilters } from "@/types/analytics";

function params(filters: AnalyticsFilters) {
    return {
        date_from: filters.date_from,
        date_to: filters.date_to,
        granularity: filters.granularity,
        branch_id: filters.branch_id || undefined,
    };
}

export const analyticsApi = {
    company: async (filters: AnalyticsFilters): Promise<AnalyticsDashboard> =>
        (await api.get<AnalyticsDashboard>("/analytics/company", { params: params(filters) })).data,

    platform: async (filters: AnalyticsFilters): Promise<AnalyticsDashboard> =>
        (await api.get<AnalyticsDashboard>("/analytics/platform", { params: params(filters) })).data,

    borrower: async (filters: AnalyticsFilters): Promise<AnalyticsDashboard> =>
        (await api.get<AnalyticsDashboard>("/analytics/borrower", { params: params(filters) })).data,

    command: async (filters: AnalyticsFilters): Promise<ManagementCommandIntelligence> =>
        (await api.get<ManagementCommandIntelligence>("/analytics/company-command", { params: params(filters) })).data,
};
