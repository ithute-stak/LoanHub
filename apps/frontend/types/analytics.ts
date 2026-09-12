export type AnalyticsMetricFormat = "money" | "integer" | "percent" | "decimal";
export type AnalyticsInsightTone = "positive" | "warning" | "critical" | "neutral";

export type AnalyticsMetric = {
    key: string;
    label: string;
    value: number;
    format: AnalyticsMetricFormat;
    previous_value?: number | null;
    change_percent?: number | null;
    description?: string | null;
};

export type AnalyticsTimePoint = {
    period: string;
    values: Record<string, number>;
};

export type AnalyticsBreakdownPoint = {
    label: string;
    value: number;
    count?: number | null;
    secondary_value?: number | null;
    extra?: Record<string, unknown>;
};

export type AnalyticsScatterPoint = {
    label: string;
    x: number;
    y: number;
    size?: number | null;
    extra?: Record<string, unknown>;
};

export type AnalyticsHeatmapPoint = {
    day: string;
    hour: number;
    value: number;
};

export type AnalyticsInsight = {
    title: string;
    message: string;
    tone: AnalyticsInsightTone;
    action_url?: string | null;
};

export type AnalyticsScope = {
    scope: "platform" | "company" | "borrower";
    company_id?: string | null;
    branch_id?: string | null;
    borrower_id?: string | null;
    role?: string | null;
    date_from: string;
    date_to: string;
    granularity: "day" | "week" | "month";
};

export type AnalyticsDashboard = {
    scope: AnalyticsScope;
    metrics: AnalyticsMetric[];
    series: Record<string, AnalyticsTimePoint[]>;
    breakdowns: Record<string, AnalyticsBreakdownPoint[]>;
    scatter: Record<string, AnalyticsScatterPoint[]>;
    heatmaps: Record<string, AnalyticsHeatmapPoint[]>;
    insights: AnalyticsInsight[];
    permissions: Record<string, boolean>;
    generated_at: string;
};

export type AnalyticsFilters = {
    date_from: string;
    date_to: string;
    granularity?: "day" | "week" | "month";
    branch_id?: string;
};
