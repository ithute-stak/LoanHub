"use client";

import Link from "next/link";
import {
    ArrowRight,
    Banknote,
    Building2,
    FileBarChart,
    FileText,
    RefreshCcw,
    ShieldCheck,
    Users,
} from "lucide-react";

import { SuperAdminCompaniesTable } from "@/components/SuperAdminCompaniesTable";
import { MarketableQuickActions } from "@/components/dashboard/marketable-quick-actions";
import { MetricCard } from "@/components/portal/metric-card";
import { formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";

export default function SuperAdminDashboardPage() {
    const {
        companiesCount,
        approvedCompaniesCount,
        pendingCompaniesCount,
        companyStaffCount,
        borrowersCount,
        loanRequestsCount,
        openLoanRequestsCount,
        payments,
        successfulPaymentsTotal,
        isLoading,
        refreshAllData,
    } = useAppData();

    const platformRevenue = payments
        .filter(
            (payment) =>
                payment.status === "succeeded" &&
                [
                    "subscription",
                    "marketplace_unlock",
                    "platform_fee",
                ].includes(payment.purpose),
        )
        .reduce(
            (sum, payment) =>
                sum + Number(payment.amount),
            0,
        );

    const monitoredProfiles =
        companyStaffCount + borrowersCount;

    return (
        <main className="space-y-6">
            <MarketableQuickActions base="/superadmin" />

            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="absolute -bottom-32 -right-20 h-80 w-80 rounded-full bg-emerald-500/10 blur-3xl" />

                <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-full border bg-background px-4 py-2 text-xs font-black text-muted-foreground shadow-sm">
                            <ShieldCheck className="h-4 w-4 text-primary" />
                            LoanHub platform control centre
                        </div>

                        <h1 className="mt-5 text-3xl font-black tracking-tight md:text-4xl">
                            Live platform overview
                        </h1>

                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
                            Monitor verified lenders, users, loan demand,
                            payments, reports, system activity and operational
                            exceptions using live LoanHub records. No sample
                            totals are shown on this dashboard.
                        </p>
                    </div>

                    <div className="flex flex-col gap-3 sm:flex-row">
                        <button
                            type="button"
                            onClick={() => void refreshAllData()}
                            disabled={isLoading}
                            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black transition hover:border-primary hover:text-primary disabled:opacity-50"
                        >
                            <RefreshCcw
                                className={`h-4 w-4 ${
                                    isLoading ? "animate-spin" : ""
                                }`}
                            />
                            Refresh live data
                        </button>

                        <Link
                            href="/superadmin/reports"
                            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground"
                        >
                            <FileBarChart className="h-4 w-4" />
                            Open reports
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                    </div>
                </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                    title="Registered companies"
                    value={companiesCount.toLocaleString()}
                    description={`${approvedCompaniesCount.toLocaleString()} approved; ${pendingCompaniesCount.toLocaleString()} awaiting review`}
                    icon={Building2}
                />

                <MetricCard
                    title="Managed user profiles"
                    value={monitoredProfiles.toLocaleString()}
                    description={`${companyStaffCount.toLocaleString()} company staff and ${borrowersCount.toLocaleString()} borrowers`}
                    icon={Users}
                />

                <MetricCard
                    title="Loan requests"
                    value={loanRequestsCount.toLocaleString()}
                    description={`${openLoanRequestsCount.toLocaleString()} requests currently open`}
                    icon={FileText}
                />

                <MetricCard
                    title="Recorded platform revenue"
                    value={formatMoney(platformRevenue)}
                    description={`${formatMoney(successfulPaymentsTotal)} total successful transaction value`}
                    icon={Banknote}
                />
            </section>

            <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h2 className="text-xl font-black">
                            Company approval and oversight
                        </h2>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Review new lenders, verify legal information and
                            control tenant activation from one operational list.
                        </p>
                    </div>

                    <Link
                        href="/superadmin/companies"
                        className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-black transition hover:border-primary hover:text-primary"
                    >
                        View company analytics
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>

                <SuperAdminCompaniesTable />
            </section>
        </main>
    );
}
