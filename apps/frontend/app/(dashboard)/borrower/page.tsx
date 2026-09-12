"use client";

import { MarketableQuickActions } from "@/components/dashboard/marketable-quick-actions";

import Link from "next/link";
import {
    ArrowRight,
    Banknote,
    FileText,
    Gauge,
    HandCoins,
    Plus,
    ShieldCheck,
    WalletCards,
} from "lucide-react";

import { MetricCard } from "@/components/portal/metric-card";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDate, formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";

export default function BorrowerDashboardPage() {
    const {
        user,
        currentBorrower,
        myLoanRequests,
        loans,
        payments,
        outstandingBalanceTotal,
        successfulPaymentsTotal,
    } = useAppData();

    const firstName = user?.person?.first_name ?? "Borrower";
    const openRequests = myLoanRequests.filter((request) => ["open", "offered", "submitted"].includes(request.status));
    const activeLoans = loans.filter((loan) => loan.status === "active");

    return (
        <div className="space-y-6">
            <MarketableQuickActions base="/borrower" />
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="text-sm font-bold text-primary">Welcome back, {firstName}</p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight md:text-4xl">Your LoanHub account</h1>
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                            Understand your complete borrowing position, compare transparent offers, track every installment and request lender assistance without leaving LoanHub.
                        </p>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row">
                        <Link href="/borrower/financial-centre" className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black">
                            <Gauge className="h-4 w-4" /> Financial centre
                        </Link>
                        <Link href="/borrower/requests" className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">
                            <Plus className="h-4 w-4" /> Request a loan
                        </Link>
                    </div>
                </div>
            </section>

            <Link href="/borrower/financial-centre" className="group grid gap-4 rounded-3xl border border-primary/20 bg-primary/5 p-5 transition hover:border-primary/40 sm:grid-cols-[auto_1fr_auto] sm:items-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground"><ShieldCheck className="h-5 w-5" /></div>
                <div><p className="font-black">Borrower Financial Command Centre</p><p className="mt-1 text-sm leading-6 text-muted-foreground">Financial health, LoanHub readiness, product eligibility, offer comparison, repayment calendar, payoff planning, lender requests, consent and profile-access history.</p></div>
                <ArrowRight className="hidden h-5 w-5 text-primary transition group-hover:translate-x-1 sm:block" />
            </Link>

            {!currentBorrower?.consent_to_share_profile && (
                <section className="rounded-3xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300">
                    <p className="font-black">Complete consent settings before broadcasting</p>
                    <p className="mt-1">Lenders can only assess requests when your sharing and credit-check preferences are correctly configured. You can now review these under Financial centre → Trust & security.</p>
                </section>
            )}

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard title="Loan requests" value={myLoanRequests.length.toLocaleString()} description={`${openRequests.length} currently open or under review`} icon={FileText} />
                <MetricCard title="Active loans" value={activeLoans.length.toLocaleString()} description="Accepted loans currently in repayment" icon={HandCoins} />
                <MetricCard title="Outstanding balance" value={formatMoney(outstandingBalanceTotal)} description="Total remaining across your loans" icon={WalletCards} />
                <MetricCard title="Successful payments" value={formatMoney(successfulPaymentsTotal)} description={`${payments.filter((item) => item.status === "succeeded").length} completed transactions`} icon={Banknote} />
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
                <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                    <div className="flex items-center justify-between border-b p-5"><div><h2 className="text-lg font-black">Recent requests</h2><p className="mt-1 text-sm text-muted-foreground">Track lender interest and selected offers.</p></div><Link href="/borrower/financial-centre?tab=applications" className="inline-flex items-center gap-1 text-sm font-bold text-primary">Track all <ArrowRight className="h-4 w-4" /></Link></div>
                    <div className="divide-y">
                        {myLoanRequests.slice(0, 5).map((request) => <div key={request.id} className="flex items-center justify-between gap-4 p-5"><div><p className="font-black">{formatMoney(request.requested_amount)}</p><p className="mt-1 text-xs text-muted-foreground">{request.loan_purpose || "General purpose"} · {formatDate(request.created_at)}</p></div><StatusBadge value={request.status} /></div>)}
                        {myLoanRequests.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">You have not created a loan request yet.</p>}
                    </div>
                </article>
                <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                    <div className="flex items-center justify-between border-b p-5"><div><h2 className="text-lg font-black">Loan balances</h2><p className="mt-1 text-sm text-muted-foreground">Your latest accepted facilities.</p></div><Link href="/borrower/financial-centre?tab=repayments" className="inline-flex items-center gap-1 text-sm font-bold text-primary">Repayment centre <ArrowRight className="h-4 w-4" /></Link></div>
                    <div className="divide-y">
                        {loans.slice(0, 5).map((loan) => <div key={loan.id} className="flex items-center justify-between gap-4 p-5"><div><p className="font-black">{loan.loan_reference}</p><p className="mt-1 text-xs text-muted-foreground">Next installment {formatMoney(loan.installment_amount)}</p></div><div className="text-right"><p className="font-black">{formatMoney(loan.balance)}</p><div className="mt-1"><StatusBadge value={loan.is_overdue ? "overdue" : loan.status} /></div></div></div>)}
                        {loans.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">No accepted loans yet.</p>}
                    </div>
                </article>
            </section>
        </div>
    );
}
