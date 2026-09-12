"use client";

import { MarketableQuickActions } from "@/components/dashboard/marketable-quick-actions";

import Link from "next/link";
import {
    AlertCircle,
    ArrowRight,
    Banknote,
    Building2,
    CreditCard,
    Gauge,
    GitBranch,
    HandCoins,
    PhoneCall,
    RefreshCcw,
    Store,
    Users,
    WalletCards,
} from "lucide-react";

import { ErrorPanel } from "@/components/portal/error-panel";
import { LoadingPanel } from "@/components/portal/loading-panel";
import { MetricCard } from "@/components/portal/metric-card";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";

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

    if (isLoading && !currentCompany) {
        return <LoadingPanel label="Preparing your company workspace..." />;
    }

    const primaryError = Object.values(errors).find(Boolean) ?? null;
    const recentLoans = loans.slice(0, 5);
    const recentPayments = payments.slice(0, 5);

    return (
        <div className="space-y-6">
            <MarketableQuickActions base="/company" />
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-full border bg-background px-4 py-2 text-xs font-black text-muted-foreground">
                            <Building2 className="h-4 w-4 text-primary" />
                            Tenant workspace
                        </div>
                        <h1 className="mt-5 text-3xl font-black tracking-tight md:text-4xl">
                            {currentCompany?.name ?? "Your loan company"}
                        </h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
                            Control lending operations, branches, staff, marketplace offers,
                            disbursements, collections and subscription billing from one place.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => void refreshAllData()}
                        disabled={isLoading}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground disabled:opacity-60"
                    >
                        <RefreshCcw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                        Refresh data
                    </button>
                </div>
            </section>

            <div className="grid gap-4 xl:grid-cols-2">
                <Link
                    href="/company/command-centre"
                    className="group flex flex-col gap-4 rounded-3xl border bg-card p-5 shadow-sm transition hover:border-primary/40 hover:shadow-md sm:flex-row sm:items-center sm:justify-between md:p-6"
                >
                    <div className="flex items-start gap-4">
                        <div className="rounded-2xl bg-primary/10 p-3 text-primary"><Gauge className="h-6 w-6" /></div>
                        <div>
                            <p className="text-lg font-black">Open Company Operating System</p>
                            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">Executive metrics, CRM, credit committee, risk, liquidity, collections, legal, compliance, planning, integrations, board packs and the governed Company Data Assistant.</p>
                        </div>
                    </div>
                    <span className="inline-flex items-center gap-1 text-sm font-black text-primary">Open command centre <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
                </Link>

                <Link
                    href="/company/calls"
                    className="group flex flex-col gap-4 rounded-3xl border bg-card p-5 shadow-sm transition hover:border-primary/40 hover:shadow-md sm:flex-row sm:items-center sm:justify-between md:p-6"
                >
                    <div className="flex items-start gap-4">
                        <div className="rounded-2xl bg-primary/10 p-3 text-primary"><PhoneCall className="h-6 w-6" /></div>
                        <div>
                            <p className="text-lg font-black">Open Calls & QA</p>
                            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">Track employee-client calls, review recordings, monitor permitted live calls, score quality and manage recording retention.</p>
                        </div>
                    </div>
                    <span className="inline-flex items-center gap-1 text-sm font-black text-primary">Open call management <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" /></span>
                </Link>
            </div>

            {hasError && primaryError && (
                <ErrorPanel message={primaryError} onRetry={() => void refreshAllData()} />
            )}

            {currentCompany && (!currentCompany.is_active || currentCompany.status !== "approved") && (
                <section className="flex items-start gap-3 rounded-3xl border border-amber-200 bg-amber-50 p-5 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
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

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
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

            <section className="grid gap-6 xl:grid-cols-2">
                <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                    <div className="flex items-center justify-between border-b p-5">
                        <div><h2 className="text-lg font-black">Recent loans</h2><p className="mt-1 text-sm text-muted-foreground">Latest accepted offers and balances.</p></div>
                        <Link href="/company/loans" className="inline-flex items-center gap-1 text-sm font-bold text-primary">View all <ArrowRight className="h-4 w-4" /></Link>
                    </div>
                    <div className="divide-y">
                        {recentLoans.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">No loans have been created yet.</p> : recentLoans.map((loan) => (
                            <Link key={loan.id} href={`/company/loans?loan=${loan.id}`} className="flex items-center justify-between gap-4 p-5 transition hover:bg-muted/40">
                                <div><p className="font-black">{loan.loan_reference}</p><p className="mt-1 text-xs text-muted-foreground">{formatMoney(loan.principal_amount)} · {loan.repayment_period} {titleCase(loan.repayment_type)} periods</p></div>
                                <div className="text-right"><StatusBadge value={loan.status} /><p className="mt-2 text-xs font-bold">{formatMoney(loan.balance)}</p></div>
                            </Link>
                        ))}
                    </div>
                </article>

                <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                    <div className="flex items-center justify-between border-b p-5">
                        <div><h2 className="text-lg font-black">Recent payments</h2><p className="mt-1 text-sm text-muted-foreground">Latest mobile-money and billing activity.</p></div>
                        <Link href="/company/payments" className="inline-flex items-center gap-1 text-sm font-bold text-primary">View all <ArrowRight className="h-4 w-4" /></Link>
                    </div>
                    <div className="divide-y">
                        {recentPayments.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">No payment transactions yet.</p> : recentPayments.map((payment) => (
                            <div key={payment.id} className="flex items-center justify-between gap-4 p-5">
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
