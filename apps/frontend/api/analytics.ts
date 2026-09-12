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
};
