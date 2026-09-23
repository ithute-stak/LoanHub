"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertCircle,
    ArrowRight,
    Banknote,
    Building2,
    CalendarDays,
    Clock,
    CreditCard,
    Gauge,
    GitBranch,
    HandCoins,
    PhoneCall,
    RefreshCcw,
    Store,
    TrendingDown,
    TrendingUp,
    Users,
    WalletCards,
} from "lucide-react";

import {
    cdasDashboardApi,
    type CdasBranchBookKpi,
    type CdasDashboardKpis,
    type CdasMovement,
    type CdasOfficerBookKpi,
} from "@/api/cdasDashboard";
import { MarketableQuickActions } from "@/components/dashboard/marketable-quick-actions";
import { ErrorPanel } from "@/components/portal/error-panel";
import { LoadingPanel } from "@/components/portal/loading-panel";
import { MetricCard } from "@/components/portal/metric-card";
import { StatusBadge } from "@/components/portal/status-badge";
import { InterfaceDensityControl } from "@/components/system/interface-density-control";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";

function movementLabel(movement?: CdasMovement | null) {
    if (!movement) return "No comparison yet";
    if (movement.direction === "new_book") return "New deduction book";
    const percentage = movement.percent === null ? "—" : `${Math.abs(movement.percent).toFixed(1)}%`;
    if (movement.direction === "growth") return `+${percentage} growth`;
    if (movement.direction === "decay") return `-${percentage} decay`;
    return "Stable";
}

function monthLabel(value: string) {
    const parsed = new Date(`${value}-01T00:00:00`);
    return Number.isNaN(parsed.getTime())
        ? value
        : parsed.toLocaleDateString("en-ZA", { month: "short", year: "2-digit" });
}

type ActiveBookItem = CdasBranchBookKpi | CdasOfficerBookKpi;

function ActiveBookList({
    title,
    description,
    items,
}: {
    title: string;
    description: string;
    items: ActiveBookItem[];
}) {
    return (
        <div className="loanhub-density-panel rounded-xl border bg-muted/20 p-3 2xl:p-4">
            <div>
                <p className="text-sm font-black">{title}</p>
                <p className="mt-0.5 text-xs leading-4 text-muted-foreground">{description}</p>
            </div>
            {items.length === 0 ? (
                <p className="mt-3 rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
                    No active CDAS book is available for this view yet.
                </p>
            ) : (
                <div className="mt-3 divide-y rounded-lg border bg-background/70">
                    {items.map((item, index) => {
                        const key = "branch_id" in item ? item.branch_id ?? item.name : item.user_id;
                        return (
                            <div
                                key={key}
                                className="grid grid-cols-[1.75rem_minmax(0,1fr)_auto] items-center gap-2 p-2.5 text-xs"
                            >
                                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 font-black text-primary">
                                    {index + 1}
                                </span>
                                <div className="min-w-0">
                                    <p className="truncate font-black" title={item.name}>{item.name}</p>
                                    <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                                        {item.active_deduction_count.toLocaleString()} deductions · {item.active_client_count.toLocaleString()} clients
                                    </p>
                                </div>
                                <strong className="whitespace-nowrap text-right">{formatMoney(item.monthly_amount)}</strong>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export default function CompanyDashboardPage() {
    const {
        currentCompany,
        currentSubscription,
        branchesCount,
        activeBranchesCount,
        companyStaffCount,
        activeStaffCount,
        marketplaceRequests,
        loans,
        payments,
        activeLoansCount,
        overdueLoansCount,
        outstandingBalanceTotal,
        successfulPaymentsTotal,
        isLoading,
        hasError,
        errors,
        refreshAllData,
    } = useAppData();
    const [cdasKpis, setCdasKpis] = useState<CdasDashboardKpis | null>(null);
    const [cdasLoading, setCdasLoading] = useState(false);
    const [cdasError, setCdasError] = useState("");

    const refreshCdasKpis = useCallback(async () => {
        if (!currentCompany?.id) return;
        setCdasLoading(true);
        setCdasError("");
        try {
            setCdasKpis(await cdasDashboardApi.getKpis());
        } catch {
            setCdasError("CDAS payroll KPIs could not be loaded for this workspace.");
        } finally {
            setCdasLoading(false);
        }
    }, [currentCompany?.id]);

    useEffect(() => {
        void refreshCdasKpis();
    }, [refreshCdasKpis]);

    const forecastSeries = useMemo(() => {
        if (!cdasKpis) return [];
        return [
            ...cdasKpis.run_rate_history.map((item) => ({ ...item, projected: false })),
            {
                month: cdasKpis.projected_next_month.month,
                amount: cdasKpis.projected_next_month.monthly_amount,
                projected: true,
            },
        ];
    }, [cdasKpis]);

    const historyMax = useMemo(
        () => Math.max(1, ...forecastSeries.map((item) => item.amount)),
        [forecastSeries],
    );

    if (isLoading && !currentCompany) {
        return <LoadingPanel label="Preparing your company workspace..." />;
    }

    const primaryError = Object.values(errors).find(Boolean) ?? null;
    const recentLoans = loans.slice(0, 5);
    const recentPayments = payments.slice(0, 5);
    const environmentLabel = String(cdasKpis?.environment || "test").toUpperCase();
    const movementIcon = cdasKpis?.month_movement.direction === "decay" ? TrendingDown : TrendingUp;

    async function refreshDashboard() {
        await Promise.allSettled([refreshAllData(), refreshCdasKpis()]);
    }

    return (
        <div className="loanhub-dashboard loanhub-page space-y-4 2xl:space-y-6">
            <MarketableQuickActions base="/company" />
            <section className="loanhub-hero loanhub-density-panel overflow-hidden rounded-2xl border bg-card p-4 shadow-sm sm:p-5 2xl:rounded-3xl 2xl:p-8">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between 2xl:gap-6">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground 2xl:px-4 2xl:py-2">
                            <Building2 className="h-4 w-4 text-primary" />
                            Tenant workspace
                        </div>
                        <h1 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl 2xl:mt-5 2xl:text-4xl">
                            {currentCompany?.name ?? "Your loan company"}
                        </h1>
                        <p className="mt-1.5 max-w-3xl text-sm leading-5 text-muted-foreground 2xl:mt-2 2xl:text-base 2xl:leading-6">
                            Control lending operations, branches, staff, marketplace offers,
                            disbursements, collections and subscription billing from one place.
                        </p>
                    </div>
                    <div className="loanhub-dashboard-actionbar flex flex-wrap items-center gap-2">
                        <InterfaceDensityControl />
                        <button
                            type="button"
                            onClick={() => void refreshDashboard()}
                            disabled={isLoading || cdasLoading}
                            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground disabled:opacity-60 2xl:h-11"
                        >
                            <RefreshCcw className={`h-4 w-4 ${isLoading || cdasLoading ? "animate-spin" : ""}`} />
                            Refresh data
                        </button>
                    </div>
                </div>
            </section>

            <div className="loanhub-density-grid grid gap-3 xl:grid-cols-2 2xl:gap-4">
                <Link
                    href="/company/command-centre"
                    className="group flex flex-col gap-3 rounded-2xl border bg-card p-4 shadow-sm transition hover:border-primary/40 sm:flex-row sm:items-center sm:justify-between 2xl:rounded-3xl 2xl:p-6"
                >
                    <div className="flex items-start gap-3 2xl:gap-4">
                        <div className="rounded-xl bg-primary/10 p-2.5 text-primary 2xl:rounded-2xl 2xl:p-3"><Gauge className="h-5 w-5 2xl:h-6 2xl:w-6" /></div>
                        <div>
                            <p className="font-black 2xl:text-lg">Open Company Operating System</p>
                            <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground 2xl:text-sm 2xl:leading-6">Executive metrics, CRM, credit committee, risk, liquidity, collections, legal, compliance, planning, integrations, board packs and the governed Company Data Assistant.</p>
                        </div>
                    </div>
                    <span className="inline-flex items-center gap-1 text-xs font-black text-primary 2xl:text-sm">Open command centre <ArrowRight className="h-4 w-4" /></span>
                </Link>

                <Link
                    href="/company/calls"
                    className="group flex flex-col gap-3 rounded-2xl border bg-card p-4 shadow-sm transition hover:border-primary/40 sm:flex-row sm:items-center sm:justify-between 2xl:rounded-3xl 2xl:p-6"
                >
                    <div className="flex items-start gap-3 2xl:gap-4">
                        <div className="rounded-xl bg-primary/10 p-2.5 text-primary 2xl:rounded-2xl 2xl:p-3"><PhoneCall className="h-5 w-5 2xl:h-6 2xl:w-6" /></div>
                        <div>
                            <p className="font-black 2xl:text-lg">Open Calls & QA</p>
                            <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground 2xl:text-sm 2xl:leading-6">Track employee-client calls, review recordings, monitor permitted live calls, score quality and manage recording retention.</p>
                        </div>
                    </div>
                    <span className="inline-flex items-center gap-1 text-xs font-black text-primary 2xl:text-sm">Open call management <ArrowRight className="h-4 w-4" /></span>
                </Link>
            </div>

            {hasError && primaryError && (
                <ErrorPanel message={primaryError} onRetry={() => void refreshDashboard()} />
            )}

            {currentCompany && (!currentCompany.is_active || currentCompany.status !== "approved") && (
                <section className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300 2xl:rounded-3xl 2xl:p-5">
                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
                    <div>
                        <p className="font-black">Company approval is still required</p>
                        <p className="mt-1 text-sm">
                            Marketplace, payments and lending operations become available after
                            the platform administrator approves and activates the company.
                        </p>
                    </div>
                </section>
            )}

            <section className="loanhub-density-grid grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 2xl:gap-4">
                <MetricCard title="Active loans" value={activeLoansCount.toLocaleString()} description={`${overdueLoansCount} loans currently overdue`} icon={HandCoins} />
                <MetricCard title="Outstanding balance" value={formatMoney(outstandingBalanceTotal)} description="Total remaining principal and charges" icon={WalletCards} />
                <MetricCard title="Branches" value={branchesCount.toLocaleString()} description={`${activeBranchesCount} branches are active`} icon={GitBranch} />
                <MetricCard title="Company staff" value={companyStaffCount.toLocaleString()} description={`${activeStaffCount} active staff accounts`} icon={Users} />
                <MetricCard title="Marketplace opportunities" value={marketplaceRequests.length.toLocaleString()} description="Open borrower requests visible to your company" icon={Store} />
                <MetricCard title="Successful cash flow" value={formatMoney(successfulPaymentsTotal)} description="Completed payments recorded by LoanHub" icon={Banknote} />
                <MetricCard title="Payment records" value={payments.length.toLocaleString()} description="Disbursements, repayments and platform charges" icon={CreditCard} />
                <MetricCard
                    title="Subscription"
                    value={currentSubscription?.plan_name ?? "No active plan"}
                    description={currentSubscription ? `Valid until ${formatDate(currentSubscription.end_date)}` : "Select monthly, annual or pay-per-transaction access"}
                    icon={Building2}
                />
            </section>

            <section className="loanhub-panel loanhub-density-panel rounded-2xl border bg-card p-4 shadow-sm 2xl:rounded-3xl 2xl:p-5">
                <div className="flex flex-col gap-2 border-b pb-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                        <div className="flex flex-wrap items-center gap-2">
                            <h2 className="text-lg font-black">CDAS Payroll Intelligence</h2>
                            {cdasKpis && (
                                <span className={`rounded-full border px-2.5 py-1 text-[11px] font-black ${cdasKpis.environment === "live" ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300" : "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300"}`}>
                                    {environmentLabel}
                                </span>
                            )}
                        </div>
                        <p className="mt-1 text-xs leading-5 text-muted-foreground 2xl:text-sm">
                            Company-linked payroll deductions, forward schedules, active-book performance and exact-ID collection opportunities.
                        </p>
                    </div>
                    <Link href="/company/cdas-booking/management-dashboard" className="inline-flex shrink-0 items-center gap-1 text-xs font-black text-primary 2xl:text-sm">
                        Open CDAS management <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>

                {cdasLoading && !cdasKpis ? (
                    <div className="py-8 text-center text-sm text-muted-foreground">Loading CDAS payroll intelligence…</div>
                ) : cdasError && !cdasKpis ? (
                    <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300">{cdasError}</div>
                ) : cdasKpis ? (
                    <div className="mt-4 space-y-4">
                        {cdasKpis.environment !== "live" && (
                            <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-900 dark:border-amber-900/70 dark:bg-amber-950/20 dark:text-amber-200">
                                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                                <span>These figures are from the CDAS Test environment and must not be treated as production payroll cash collections.</span>
                            </div>
                        )}

                        <div className="loanhub-density-grid grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                            <MetricCard
                                title="Monthly CDAS deductions"
                                value={formatMoney(cdasKpis.monthly_active_deductions)}
                                description={`${cdasKpis.active_deduction_count} active deductions across ${cdasKpis.active_client_count} clients`}
                                icon={HandCoins}
                            />
                            <MetricCard
                                title="Growth / decay"
                                value={movementLabel(cdasKpis.month_movement)}
                                description={`Previous monthly run-rate ${formatMoney(cdasKpis.previous_month_deductions)}`}
                                icon={movementIcon}
                            />
                            <MetricCard
                                title="Soon commencing"
                                value={cdasKpis.soon_commencing.count.toLocaleString()}
                                description={`${formatMoney(cdasKpis.soon_commencing.monthly_amount)} monthly value${cdasKpis.soon_commencing.nearest_date ? ` · next ${formatDate(cdasKpis.soon_commencing.nearest_date)}` : ""}`}
                                icon={CalendarDays}
                            />
                            <MetricCard
                                title="Soon expiring"
                                value={cdasKpis.soon_expiring.count.toLocaleString()}
                                description={`${formatMoney(cdasKpis.soon_expiring.monthly_amount)} monthly value at risk${cdasKpis.soon_expiring.nearest_date ? ` · nearest ${formatDate(cdasKpis.soon_expiring.nearest_date)}` : ""}`}
                                icon={Clock}
                            />
                            <MetricCard
                                title={`Projected ${monthLabel(cdasKpis.projected_next_month.month)}`}
                                value={formatMoney(cdasKpis.projected_next_month.monthly_amount)}
                                description={`${movementLabel(cdasKpis.projected_next_month.movement)} versus current run-rate`}
                                icon={TrendingUp}
                            />
                            <MetricCard
                                title="Ready for collection review"
                                value={cdasKpis.ready_for_collection_review.toLocaleString()}
                                description="Exact-ID borrowers with debt and positive CDAS affordability"
                                icon={Gauge}
                            />
                            <MetricCard
                                title="No-capacity monitor"
                                value={cdasKpis.monitor_no_capacity.toLocaleString()}
                                description="Outstanding LoanHub debt currently without additional CDAS capacity"
                                icon={AlertCircle}
                            />
                            <MetricCard
                                title="Potential additional capacity"
                                value={formatMoney(cdasKpis.potential_additional_monthly_deduction)}
                                description="Possible extra monthly collection identified by daily affordability checks"
                                icon={WalletCards}
                            />
                        </div>

                        <div className="loanhub-density-grid grid gap-3 xl:grid-cols-[1.2fr_0.8fr]">
                            <div className="loanhub-density-panel rounded-xl border bg-muted/20 p-3 2xl:p-4">
                                <div className="flex flex-wrap items-start justify-between gap-2">
                                    <div>
                                        <p className="text-sm font-black">6-month run-rate + next-month forecast</p>
                                        <p className="mt-0.5 text-xs text-muted-foreground">Historical contracted run-rate with a lightweight projected next-month bar.</p>
                                    </div>
                                    <span className="text-xs font-bold text-muted-foreground">LSL / month</span>
                                </div>
                                <div className="loanhub-density-chart mt-4 grid h-28 grid-cols-7 items-end gap-1 sm:h-32 sm:gap-2">
                                    {forecastSeries.map((item) => {
                                        const height = item.amount <= 0 ? 4 : Math.max(10, Math.round((item.amount / historyMax) * 100));
                                        return (
                                            <div key={`${item.month}-${item.projected ? "forecast" : "actual"}`} className="flex h-full min-w-0 flex-col justify-end gap-1">
                                                <div className="truncate text-center text-[9px] font-bold text-muted-foreground sm:text-[10px]" title={formatMoney(item.amount)}>
                                                    {item.amount > 0 ? formatMoney(item.amount) : "M0"}
                                                </div>
                                                <div className={`flex h-16 items-end rounded-md sm:h-20 ${item.projected ? "border border-dashed border-primary/60 bg-primary/5" : "bg-muted/50"}`}>
                                                    <div
                                                        className={`w-full rounded-md ${item.projected ? "bg-primary/35" : "bg-primary/75"}`}
                                                        style={{ height: `${height}%` }}
                                                    />
                                                </div>
                                                <div className={`truncate text-center text-[9px] sm:text-[10px] ${item.projected ? "font-black text-primary" : "text-muted-foreground"}`}>
                                                    {monthLabel(item.month)}{item.projected ? "*" : ""}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-[11px]">
                                    <span className="text-muted-foreground">* Dashed final column is the forecast, not a confirmed payroll receipt.</span>
                                    <strong>{movementLabel(cdasKpis.projected_next_month.movement)}</strong>
                                </div>
                            </div>

                            <div className="loanhub-density-panel rounded-xl border bg-muted/20 p-3 2xl:p-4">
                                <p className="text-sm font-black">Daily intelligence health</p>
                                <div className="mt-3 grid gap-2 text-xs">
                                    <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Scheduled check</span><strong>03:45</strong></div>
                                    <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Latest daily check</span><strong>{cdasKpis.latest_daily_check ? formatDate(cdasKpis.latest_daily_check) : "No run yet"}</strong></div>
                                    <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Check issues today</span><strong>{cdasKpis.daily_check_failures_today.toLocaleString()}</strong></div>
                                    <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Reporting environment</span><strong>{environmentLabel}</strong></div>
                                </div>
                                <p className="mt-3 border-t pt-3 text-[11px] leading-4 text-muted-foreground">
                                    Contracted run-rate is a portfolio forecast, not proof that cash was received. Actual payroll receipts remain subject to remittance and LoanHub payment reconciliation.
                                </p>
                            </div>
                        </div>

                        <div className="loanhub-density-grid grid gap-3 xl:grid-cols-2">
                            <ActiveBookList
                                title="Top branches by active CDAS book"
                                description="Ranked by current contracted monthly deduction value within the active company/branch scope."
                                items={cdasKpis.top_branches ?? []}
                            />
                            <ActiveBookList
                                title="Top officers by active CDAS book"
                                description="Mandates grouped by the staff member who registered them; this is operational book attribution, not a staff score."
                                items={cdasKpis.top_officers ?? []}
                            />
                        </div>
                    </div>
                ) : null}
            </section>

            <section className="loanhub-density-grid grid gap-4 xl:grid-cols-2 2xl:gap-6">
                <article className="overflow-hidden rounded-2xl border bg-card shadow-sm 2xl:rounded-3xl">
                    <div className="flex items-center justify-between border-b p-4 2xl:p-5">
                        <div><h2 className="font-black 2xl:text-lg">Recent loans</h2><p className="mt-1 text-xs text-muted-foreground 2xl:text-sm">Latest accepted offers and balances.</p></div>
                        <Link href="/company/loans" className="inline-flex items-center gap-1 text-xs font-bold text-primary 2xl:text-sm">View all <ArrowRight className="h-4 w-4" /></Link>
                    </div>
                    <div className="divide-y">
                        {recentLoans.length === 0 ? <p className="p-6 text-center text-sm text-muted-foreground 2xl:p-8">No loans have been created yet.</p> : recentLoans.map((loan) => (
                            <Link key={loan.id} href={`/company/loans?loan=${loan.id}`} className="flex items-center justify-between gap-4 p-4 transition hover:bg-muted/40 2xl:p-5">
                                <div><p className="font-black">{loan.loan_reference}</p><p className="mt-1 text-xs text-muted-foreground">{formatMoney(loan.principal_amount)} · {loan.repayment_period} {titleCase(loan.repayment_type)} periods</p></div>
                                <div className="text-right"><StatusBadge value={loan.status} /><p className="mt-2 text-xs font-bold">{formatMoney(loan.balance)}</p></div>
                            </Link>
                        ))}
                    </div>
                </article>

                <article className="overflow-hidden rounded-2xl border bg-card shadow-sm 2xl:rounded-3xl">
                    <div className="flex items-center justify-between border-b p-4 2xl:p-5">
                        <div><h2 className="font-black 2xl:text-lg">Recent payments</h2><p className="mt-1 text-xs text-muted-foreground 2xl:text-sm">Latest mobile-money and billing activity.</p></div>
                        <Link href="/company/payments" className="inline-flex items-center gap-1 text-xs font-bold text-primary 2xl:text-sm">View all <ArrowRight className="h-4 w-4" /></Link>
                    </div>
                    <div className="divide-y">
                        {recentPayments.length === 0 ? <p className="p-6 text-center text-sm text-muted-foreground 2xl:p-8">No payment transactions yet.</p> : recentPayments.map((payment) => (
                            <div key={payment.id} className="flex items-center justify-between gap-4 p-4 2xl:p-5">
                                <div><p className="font-black">{titleCase(payment.purpose)}</p><p className="mt-1 text-xs text-muted-foreground">{titleCase(payment.provider)} · {formatDate(payment.created_at)}</p></div>
                                <div className="text-right"><p className="font-black">{formatMoney(payment.amount)}</p><div className="mt-1"><StatusBadge value={payment.status} /></div></div>
                            </div>
                        ))}
                    </div>
                </article>
            </section>
        </div>
    );
}
