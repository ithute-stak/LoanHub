"use client";

import Link from "next/link";
import {
    Activity,
    ArrowDownRight,
    ArrowUpRight,
    BarChart3,
    BrainCircuit,
    Building2,
    CalendarRange,
    CircleDollarSign,
    Download,
    FileBarChart,
    HandCoins,
    Landmark,
    Loader2,
    RefreshCw,
    ShieldAlert,
    Sparkles,
    Users,
    WalletCards,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { analyticsApi } from "@/api/analytics";
import {
    ActivityHeatmap,
    BubbleScatterChart,
    DonutChart,
    DualMetricBarChart,
    FunnelChart,
    HorizontalBarChart,
    MultiLineChart,
    RadarScoreChart,
    RadialGauge,
    StackedBarChart,
    TrendAreaChart,
} from "@/components/analytics/analytics-charts";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { useAppData } from "@/provider/appDataProvider";
import type {
    AnalyticsBreakdownPoint,
    AnalyticsDashboard as AnalyticsDashboardData,
    AnalyticsMetric,
    AnalyticsTimePoint,
} from "@/types/analytics";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";


type Scope = "company" | "platform" | "borrower";
type Preset = "30d" | "90d" | "6m" | "12m" | "24m";

const PRESETS: Array<{ value: Preset; label: string; days: number }> = [
    { value: "30d", label: "Last 30 days", days: 30 },
    { value: "90d", label: "Last 90 days", days: 90 },
    { value: "6m", label: "Last 6 months", days: 183 },
    { value: "12m", label: "Last 12 months", days: 365 },
    { value: "24m", label: "Last 24 months", days: 730 },
];

function isoDate(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function presetRange(preset: Preset): { dateFrom: string; dateTo: string } {
    const item = PRESETS.find((entry) => entry.value === preset) ?? PRESETS[3];
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - (item.days - 1));
    return { dateFrom: isoDate(start), dateTo: isoDate(end) };
}

function formatMetric(metric: AnalyticsMetric): string {
    if (metric.format === "money") {
        return new Intl.NumberFormat("en-LS", {
            style: "currency",
            currency: "LSL",
            maximumFractionDigits: 0,
        }).format(metric.value);
    }
    if (metric.format === "percent") return `${metric.value.toFixed(1)}%`;
    if (metric.format === "integer") return Math.round(metric.value).toLocaleString("en-LS");
    return metric.value.toLocaleString("en-LS", { maximumFractionDigits: 2 });
}

function metricIcon(key: string) {
    if (key.includes("company") || key.includes("branch")) return Building2;
    if (key.includes("borrower") || key.includes("staff")) return Users;
    if (key.includes("collection") || key.includes("payment")) return WalletCards;
    if (key.includes("arrears") || key.includes("overdue")) return ShieldAlert;
    if (key.includes("revenue") || key.includes("cashflow")) return CircleDollarSign;
    if (key.includes("loan") || key.includes("principal")) return HandCoins;
    return BarChart3;
}

function AnalyticsMetricCard({ metric }: { metric: AnalyticsMetric }) {
    const Icon = metricIcon(metric.key);
    const change = metric.change_percent;
    const positive = typeof change === "number" && change >= 0;
    return (
        <Card className="rounded-3xl shadow-sm">
            <CardContent className="p-5">
                <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                        <p className="text-xs font-black uppercase tracking-[0.14em] text-muted-foreground">{metric.label}</p>
                        <p className="mt-3 truncate text-2xl font-black tracking-tight">{formatMetric(metric)}</p>
                    </div>
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                        <Icon className="h-5 w-5" />
                    </div>
                </div>
                <div className="mt-3 flex min-h-6 items-center gap-2 text-xs">
                    {typeof change === "number" ? (
                        <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-1 font-black", positive ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-red-500/10 text-red-700 dark:text-red-300")}>
                            {positive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                            {Math.abs(change).toFixed(1)}%
                        </span>
                    ) : null}
                    <span className="line-clamp-2 text-muted-foreground">{metric.description ?? (typeof change === "number" ? "Compared with the previous equivalent period" : "Current measured position")}</span>
                </div>
            </CardContent>
        </Card>
    );
}

function Insights({ data }: { data: AnalyticsDashboardData }) {
    if (data.insights.length === 0) return null;
    const tones = {
        positive: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200",
        warning: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200",
        critical: "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200",
        neutral: "border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-200",
    };
    return (
        <section className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {data.insights.map((insight) => (
                <article key={`${insight.title}-${insight.message}`} className={cn("rounded-3xl border p-5", tones[insight.tone])}>
                    <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-background/70">
                            <BrainCircuit className="h-5 w-5" />
                        </div>
                        <div>
                            <h3 className="font-black">{insight.title}</h3>
                            <p className="mt-1 text-sm leading-6 opacity-90">{insight.message}</p>
                            {insight.action_url ? <Link href={insight.action_url} className="mt-3 inline-flex text-xs font-black underline underline-offset-4">Open related records</Link> : null}
                        </div>
                    </div>
                </article>
            ))}
        </section>
    );
}

function metricValue(data: AnalyticsDashboardData, key: string): number {
    return data.metrics.find((metric) => metric.key === key)?.value ?? 0;
}

function breakdown(data: AnalyticsDashboardData, key: string): AnalyticsBreakdownPoint[] {
    return data.breakdowns[key] ?? [];
}

function series(data: AnalyticsDashboardData, key: string): AnalyticsTimePoint[] {
    return data.series[key] ?? [];
}

function downloadJson(data: AnalyticsDashboardData) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `loanhub-${data.scope.scope}-analytics-${data.scope.date_to}.json`;
    link.click();
    URL.revokeObjectURL(url);
}

export function AnalyticsDashboard({ scope }: { scope: Scope }) {
    const { branches, currentCompany } = useAppData();
    const defaultRange = useMemo(() => presetRange("12m"), []);
    const [preset, setPreset] = useState<Preset>("12m");
    const [dateFrom, setDateFrom] = useState(defaultRange.dateFrom);
    const [dateTo, setDateTo] = useState(defaultRange.dateTo);
    const [granularity, setGranularity] = useState<"day" | "week" | "month" | "auto">("auto");
    const [branchId, setBranchId] = useState("");
    const [data, setData] = useState<AnalyticsDashboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const filters = {
                date_from: dateFrom,
                date_to: dateTo,
                granularity: granularity === "auto" ? undefined : granularity,
                branch_id: scope === "company" ? branchId || undefined : undefined,
            };
            const response = scope === "company"
                ? await analyticsApi.company(filters)
                : scope === "platform"
                    ? await analyticsApi.platform(filters)
                    : await analyticsApi.borrower(filters);
            setData(response);
        } catch (requestError: unknown) {
            const message = getErrorMessage(requestError, "Analytics could not be loaded.");
            setError(message);
            toast.error(message);
        } finally {
            setLoading(false);
        }
    }, [branchId, dateFrom, dateTo, granularity, scope]);

    useEffect(() => {
        void load();
    }, [load]);

    function changePreset(value: Preset) {
        const range = presetRange(value);
        setPreset(value);
        setDateFrom(range.dateFrom);
        setDateTo(range.dateTo);
    }

    const title = scope === "platform" ? "Platform analytics intelligence" : scope === "borrower" ? "My borrowing analytics" : "Company analytics intelligence";
    const subtitle = scope === "platform"
        ? "Understand tenant growth, marketplace conversion, lending, payments, revenue, system health and operational risk."
        : scope === "borrower"
            ? "Understand your requests, loan balances, repayment progress and payment behaviour in one private view."
            : `Understand ${currentCompany?.name ?? "the company"} across lending, collections, finance, branches, people and controls.`;

    return (
        <div className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-16 -top-20 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-full border bg-background px-4 py-2 text-xs font-black uppercase tracking-[0.15em] text-primary">
                            <Sparkles className="h-4 w-4" /> Decision intelligence
                        </div>
                        <h1 className="mt-5 text-3xl font-black tracking-tight md:text-4xl">{title}</h1>
                        <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">{subtitle}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="lg" onClick={() => data && downloadJson(data)} disabled={!data}>
                            <Download className="h-4 w-4" /> Export data
                        </Button>
                        <Button size="lg" onClick={() => void load()} disabled={loading}>
                            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                            Refresh analytics
                        </Button>
                    </div>
                </div>
            </section>

            <section className="rounded-3xl border bg-card p-4 shadow-sm sm:p-5">
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
                    <label className="space-y-2 xl:col-span-2">
                        <span className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">Period preset</span>
                        <NativeSelect value={preset} onChange={(event) => changePreset(event.target.value as Preset)} className="h-11 w-full rounded-xl border bg-background px-3 font-bold">
                            {PRESETS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                        </NativeSelect>
                    </label>
                    <label className="space-y-2">
                        <span className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">From</span>
                        <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold" />
                    </label>
                    <label className="space-y-2">
                        <span className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">To</span>
                        <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold" />
                    </label>
                    <label className="space-y-2">
                        <span className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">Chart interval</span>
                        <NativeSelect value={granularity} onChange={(event) => setGranularity(event.target.value as typeof granularity)} className="h-11 w-full rounded-xl border bg-background px-3 font-bold">
                            <option value="auto">Automatic</option>
                            <option value="day">Daily</option>
                            <option value="week">Weekly</option>
                            <option value="month">Monthly</option>
                        </NativeSelect>
                    </label>
                    {scope === "company" ? (
                        <label className="space-y-2">
                            <span className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">Branch scope</span>
                            <NativeSelect value={branchId} onChange={(event) => setBranchId(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 font-bold">
                                <option value="">All permitted branches</option>
                                {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
                            </NativeSelect>
                        </label>
                    ) : (
                        <div className="flex items-end">
                            <div className="flex h-11 w-full items-center gap-2 rounded-xl border bg-muted/30 px-3 text-xs font-bold text-muted-foreground"><CalendarRange className="h-4 w-4" /> Scope secured by your role</div>
                        </div>
                    )}
                </div>
            </section>

            {error ? (
                <section className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
                    <p className="font-black">Analytics failed to load</p>
                    <p className="mt-1 text-sm">{error}</p>
                    <Button className="mt-4" variant="outline" onClick={() => void load()}>Try again</Button>
                </section>
            ) : null}

            {loading && !data ? (
                <section className="flex min-h-96 items-center justify-center rounded-3xl border bg-card">
                    <div className="text-center"><Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" /><p className="mt-3 text-sm font-bold text-muted-foreground">Calculating secure analytics…</p></div>
                </section>
            ) : null}

            {data ? (
                <>
                    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                        {data.metrics.map((metric) => <AnalyticsMetricCard key={metric.key} metric={metric} />)}
                    </section>

                    <Insights data={data} />

                    <Tabs defaultValue="overview" className="space-y-5">
                        <div className="overflow-x-auto rounded-2xl border bg-card p-2">
                            <TabsList className="h-11 min-w-max bg-muted/60">
                                <TabsTrigger value="overview" className="px-4"><BarChart3 /> Overview</TabsTrigger>
                                {data.permissions.lending ? <TabsTrigger value="lending" className="px-4"><HandCoins /> Lending</TabsTrigger> : null}
                                {data.permissions.marketplace ? <TabsTrigger value="marketplace" className="px-4"><FileBarChart /> Marketplace</TabsTrigger> : null}
                                {data.permissions.finance ? <TabsTrigger value="finance" className="px-4"><Landmark /> Finance</TabsTrigger> : null}
                                {data.permissions.people ? <TabsTrigger value="people" className="px-4"><Users /> People</TabsTrigger> : null}
                                {data.permissions.operations ? <TabsTrigger value="operations" className="px-4"><Activity /> Operations</TabsTrigger> : null}
                            </TabsList>
                        </div>

                        <TabsContent value="overview" className="space-y-5">
                            <OverviewAnalytics data={data} scope={scope} />
                        </TabsContent>
                        <TabsContent value="lending" className="space-y-5">
                            <LendingAnalytics data={data} scope={scope} />
                        </TabsContent>
                        <TabsContent value="marketplace" className="space-y-5">
                            <MarketplaceAnalytics data={data} scope={scope} />
                        </TabsContent>
                        <TabsContent value="finance" className="space-y-5">
                            <FinanceAnalytics data={data} />
                        </TabsContent>
                        <TabsContent value="people" className="space-y-5">
                            <PeopleAnalytics data={data} />
                        </TabsContent>
                        <TabsContent value="operations" className="space-y-5">
                            <OperationsAnalytics data={data} />
                        </TabsContent>
                    </Tabs>
                </>
            ) : null}
        </div>
    );
}

function OverviewAnalytics({ data, scope }: { data: AnalyticsDashboardData; scope: Scope }) {
    if (scope === "platform") {
        return (
            <>
                <div className="grid gap-5 xl:grid-cols-2">
                    <TrendAreaChart title="Tenant growth" description="New and approved lending companies by period." points={series(data, "company_growth")} series={[{ key: "companies", label: "Registered" }, { key: "approved", label: "Approved" }]} />
                    <TrendAreaChart title="Platform transaction value" description="Successful transactions, platform revenue and failed attempts." points={series(data, "payments")} series={[{ key: "transaction_value", label: "Transaction value" }, { key: "platform_revenue", label: "Platform revenue" }]} valueKind="money" />
                    <DonutChart title="Company approval position" description="Current distribution of registered lender status." points={breakdown(data, "company_status")} centreLabel="Companies" />
                    <DualMetricBarChart title="Company portfolio comparison" description="Outstanding balance and collected value by lender." points={breakdown(data, "company_performance")} primaryLabel="Outstanding" secondaryLabel="Collected" />
                </div>
                <div className="grid gap-5 xl:grid-cols-3">
                    <DonutChart title="Subscription status" description="Value and count of company subscriptions by status." points={breakdown(data, "subscription_status")} valueKind="money" />
                    <HorizontalBarChart title="Geographic lender coverage" description="Registered loan companies by Lesotho district." points={breakdown(data, "company_district")} />
                    <RadialGauge title="Approval coverage" description="Share of companies that are approved." value={metricValue(data, "companies") ? (metricValue(data, "approved_companies") / metricValue(data, "companies")) * 100 : 0} label="Approved tenants" />
                </div>
            </>
        );
    }
    if (scope === "borrower") {
        return (
            <>
                <div className="grid gap-5 xl:grid-cols-2">
                    <TrendAreaChart title="Borrowing and repayment movement" description="New principal, repayments and instalments due over time." points={series(data, "borrower_cashflow")} series={[{ key: "principal", label: "Principal borrowed" }, { key: "repayments", label: "Repayments" }, { key: "instalments_due", label: "Instalments due" }]} valueKind="money" />
                    <TrendAreaChart title="Request and offer activity" description="Loan requests, offers received and accepted requests." points={series(data, "borrower_requests")} series={[{ key: "requests", label: "Requests" }, { key: "offers", label: "Offers" }, { key: "accepted", label: "Accepted" }]} />
                    <DonutChart title="Loan status" description="Your facilities grouped by current status." points={breakdown(data, "loan_status")} valueKind="money" />
                    <HorizontalBarChart title="Repayment progress by loan" description="Percentage of each loan already repaid." points={breakdown(data, "loan_progress")} valueKind="percent" />
                </div>
                <div className="grid gap-5 xl:grid-cols-3">
                    <RadialGauge title="Payment completion" description="Payments captured against instalments due in the selected period." value={metricValue(data, "payment_rate")} label="Paid against due" />
                    <DonutChart title="Lender exposure" description="Outstanding balance grouped by lending company." points={breakdown(data, "lender_exposure")} valueKind="money" />
                    <DonutChart title="Payment methods" description="Successful repayments grouped by channel." points={breakdown(data, "payment_method")} valueKind="money" />
                </div>
            </>
        );
    }
    return (
        <>
            <div className="grid gap-5 xl:grid-cols-2">
                <TrendAreaChart title="Loan origination trend" description="Loan count, approved count and principal originated over time." points={series(data, "loan_volume")} series={[{ key: "loan_count", label: "Loans" }, { key: "approved_count", label: "Approved" }]} />
                <MultiLineChart title="Collections versus disbursements" description="Successful lending cash movement and net position." points={series(data, "cashflow")} series={[{ key: "collections", label: "Collections" }, { key: "disbursements", label: "Disbursements" }, { key: "net", label: "Net" }]} valueKind="money" />
                <DonutChart title="Portfolio status" description="Current loan balance grouped by status." points={breakdown(data, "loan_status")} valueKind="money" />
                <DualMetricBarChart title="Branch portfolio performance" description="Outstanding balances compared with collected amounts." points={breakdown(data, "branch_performance")} primaryLabel="Outstanding" secondaryLabel="Collected" />
            </div>
            <div className="grid gap-5 xl:grid-cols-3">
                <RadialGauge title="Collection effectiveness" description="Paid amount against instalments due in the selected period." value={metricValue(data, "collection_rate")} label="Collection rate" />
                <DonutChart title="Portfolio risk" description="Outstanding exposure grouped by risk level." points={breakdown(data, "risk_level")} valueKind="money" />
                <HorizontalBarChart title="Arrears ageing" description="Unpaid instalment exposure grouped by days overdue." points={breakdown(data, "arrears_aging")} valueKind="money" />
            </div>
        </>
    );
}

function LendingAnalytics({ data, scope }: { data: AnalyticsDashboardData; scope: Scope }) {
    return (
        <>
            <div className="grid gap-5 xl:grid-cols-2">
                {scope === "borrower" ? (
                    <BubbleScatterChart title="My loan pricing" description="Relationship between interest rate, repayment term and principal size." points={data.scatter.loan_terms ?? []} xLabel="Interest rate" yLabel="Term" xKind="percent" />
                ) : (
                    <BubbleScatterChart title="Loan pricing distribution" description="Relationship between interest rate, term and principal size across the portfolio." points={data.scatter.loan_pricing ?? data.scatter.company_portfolio ?? []} xLabel={scope === "platform" ? "Collection rate" : "Interest rate"} yLabel={scope === "platform" ? "Outstanding" : "Term"} xKind="percent" yKind={scope === "platform" ? "money" : "number"} />
                )}
                <MultiLineChart title="Instalments due, paid and overdue" description="Repayment obligations and settlement performance by period." points={series(data, scope === "borrower" ? "borrower_cashflow" : "repayments")} series={scope === "borrower" ? [{ key: "instalments_due", label: "Due" }, { key: "repayments", label: "Paid" }] : [{ key: "due", label: "Due" }, { key: "paid", label: "Paid" }, { key: "overdue", label: "Overdue" }]} valueKind="money" />
                <DonutChart title="Interest calculation methods" description="Principal exposure by the calculation method saved on each loan." points={breakdown(data, "calculation_method")} valueKind="money" />
                <DonutChart title="Origination channels" description="Principal exposure by marketplace, internal and other origination channels." points={breakdown(data, "origination_channel")} valueKind="money" />
            </div>
            <div className="grid gap-5 xl:grid-cols-3">
                <HorizontalBarChart title="Loan size distribution" description="Principal grouped into understandable lending bands." points={breakdown(data, "loan_size_bands")} valueKind="money" />
                <HorizontalBarChart title="Repayment term distribution" description="Principal grouped by repayment period." points={breakdown(data, "term_bands")} valueKind="money" />
                <DonutChart title="Instalment status" description="Scheduled instalments grouped by current settlement status." points={breakdown(data, "installment_status")} valueKind="money" />
            </div>
        </>
    );
}

function MarketplaceAnalytics({ data, scope }: { data: AnalyticsDashboardData; scope: Scope }) {
    const trendKey = scope === "borrower" ? "borrower_requests" : scope === "platform" ? "marketplace" : "applications";
    return (
        <>
            <div className="grid gap-5 xl:grid-cols-2">
                <TrendAreaChart title="Marketplace activity" description="Movement from request/application creation to offers and approvals." points={series(data, trendKey)} series={scope === "borrower" ? [{ key: "requests", label: "Requests" }, { key: "offers", label: "Offers" }, { key: "accepted", label: "Accepted" }] : scope === "platform" ? [{ key: "requests", label: "Requests" }, { key: "offers", label: "Offers" }, { key: "accepted", label: "Accepted" }] : [{ key: "submitted", label: "Applications" }, { key: "offers", label: "Offers" }, { key: "approved", label: "Approved" }, { key: "accepted_offers", label: "Accepted offers" }]} />
                <FunnelChart title="Marketplace conversion funnel" description="Where opportunities progress or drop out of the lending process." points={breakdown(data, "marketplace_funnel")} />
                <DonutChart title="Application/request status" description="Current value grouped by decision status." points={breakdown(data, scope === "platform" ? "request_status" : scope === "borrower" ? "request_status" : "application_status")} valueKind="money" />
                <DonutChart title="Offer decisions" description="Offers grouped by pending, accepted, rejected, expired or withdrawn status." points={breakdown(data, "offer_status")} valueKind="money" />
            </div>
        </>
    );
}

function FinanceAnalytics({ data }: { data: AnalyticsDashboardData }) {
    return (
        <>
            <div className="grid gap-5 xl:grid-cols-2">
                <MultiLineChart title="Financial cash movement" description="Collections, disbursements and net lending cash flow." points={series(data, "cashflow").length ? series(data, "cashflow") : series(data, "payments")} series={series(data, "cashflow").length ? [{ key: "collections", label: "Collections" }, { key: "disbursements", label: "Disbursements" }, { key: "net", label: "Net" }] : [{ key: "transaction_value", label: "Transaction value" }, { key: "platform_revenue", label: "Platform revenue" }]} valueKind="money" />
                <StackedBarChart title="Accounting postings" description="Debit and credit movement from posted and draft journal entries." points={series(data, "accounting")} series={[{ key: "debits", label: "Debits" }, { key: "credits", label: "Credits" }]} valueKind="money" />
                <DonutChart title="Payment channels" description="Successful value grouped by the recorded payment method." points={breakdown(data, "payment_method")} valueKind="money" />
                <DonutChart title="Payment outcomes" description="Attempted transaction value grouped by processing status." points={breakdown(data, "payment_status")} valueKind="money" />
            </div>
            <div className="grid gap-5 xl:grid-cols-3">
                <HorizontalBarChart title="Payment purposes" description="Transaction value by subscription, lending, repayment and platform charge purpose." points={breakdown(data, "payment_purpose")} valueKind="money" />
                <RadarScoreChart title="Chart of accounts coverage" description="Relative account counts by accounting classification." points={breakdown(data, "account_types")} />
                <HorizontalBarChart title="Subscription plan mix" description="Subscription value grouped by plan." points={breakdown(data, "subscription_plan")} valueKind="money" />
            </div>
        </>
    );
}

function PeopleAnalytics({ data }: { data: AnalyticsDashboardData }) {
    return (
        <>
            <div className="grid gap-5 xl:grid-cols-3">
                <DonutChart title="Borrower gender" description="Borrower portfolio distribution by recorded gender." points={breakdown(data, "borrower_gender")} />
                <HorizontalBarChart title="Borrower age groups" description="Borrowers grouped into age bands for responsible portfolio monitoring." points={breakdown(data, "borrower_age")} />
                <HorizontalBarChart title="Borrower employment" description="Borrower portfolio grouped by employment status." points={breakdown(data, "borrower_employment")} />
            </div>
            <div className="grid gap-5 xl:grid-cols-2">
                <HorizontalBarChart title="Borrower districts" description="Geographic distribution of customers represented in the portfolio." points={breakdown(data, "borrower_district")} />
                <DonutChart title="Staff role mix" description="Active and inactive company memberships grouped by assigned role." points={breakdown(data, "staff_roles")} />
                <HorizontalBarChart title="Department headcount" description="Employee profiles grouped by department." points={breakdown(data, "departments")} />
                <RadarScoreChart title="Performance ratings" description="Relative performance-review scores by rating category." points={breakdown(data, "performance_ratings")} />
            </div>
            <div className="grid gap-5 xl:grid-cols-2">
                <TrendAreaChart title="Performance review trend" description="Average review scores and review volume over time." points={series(data, "performance")} series={[{ key: "average_score", label: "Average score" }, { key: "review_count", label: "Review count" }]} />
                <DonutChart title="Goal progress status" description="Performance goals grouped by current status." points={breakdown(data, "goal_status")} />
            </div>
        </>
    );
}

function OperationsAnalytics({ data }: { data: AnalyticsDashboardData }) {
    return (
        <>
            <div className="grid gap-5 xl:grid-cols-2">
                <TrendAreaChart title="File activity" description="Secure uploads and storage volume over time." points={series(data, "files")} series={[{ key: "uploads", label: "Uploads" }, { key: "megabytes", label: "Megabytes" }]} />
                <MultiLineChart title="Audit activity" description="Recorded audit events, failures and critical events over time." points={series(data, "audit")} series={[{ key: "events", label: "Events" }, { key: "failures", label: "Failures" }, { key: "critical", label: "Critical" }]} />
                <HorizontalBarChart title="Document categories" description="Managed file storage grouped by category." points={breakdown(data, "file_categories")} valueKind="number" />
                <DonutChart title="File visibility" description="File records grouped by private, company, branch, platform and conversation visibility." points={breakdown(data, "file_visibility")} />
            </div>
            <div className="grid gap-5 xl:grid-cols-3">
                <HorizontalBarChart title="Most active entities" description="Audit events grouped by business entity." points={breakdown(data, "audit_entities")} />
                <HorizontalBarChart title="Most common actions" description="Audit records grouped by create, update, delete and workflow action." points={breakdown(data, "audit_actions")} />
                <DonutChart title="Audit severity" description="Transparency events grouped by severity." points={breakdown(data, "audit_severity")} />
            </div>
            <ActivityHeatmap title="Operational activity heatmap" description="When staff and system changes occur by weekday and hour." points={data.heatmaps.activity ?? []} />
            {series(data, "errors").length ? (
                <div className="grid gap-5 xl:grid-cols-2">
                    <TrendAreaChart title="System incident trend" description="Error fingerprints, total occurrences and resolved incidents." points={series(data, "errors")} series={[{ key: "errors", label: "Error fingerprints" }, { key: "occurrences", label: "Occurrences" }, { key: "resolved", label: "Resolved" }]} />
                    <DonutChart title="System error severity" description="Incident occurrences grouped by severity." points={breakdown(data, "error_severity")} />
                </div>
            ) : null}
        </>
    );
}
