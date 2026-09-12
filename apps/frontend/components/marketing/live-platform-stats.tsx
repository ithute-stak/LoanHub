"use client";

import { useEffect, useMemo, useState } from "react";
import {
    BadgeCheck,
    BriefcaseBusiness,
    Building2,
    FileCheck2,
    FileText,
    GitBranch,
    HandCoins,
    Landmark,
    ListChecks,
    Users,
    WalletCards,
    Workflow,
} from "lucide-react";

type PublicPlatformStats = {
    approved_institutions: number;
    active_branches: number;
    borrower_profiles: number;
    company_client_accounts: number;
    loan_requests: number;
    loan_offers: number;
    loan_accounts: number;
    active_loans: number;
    completed_loans: number;
    employee_profiles: number;
    managed_files: number;
    generated_reports: number;
    updated_at: string;
};

const iconByKey = {
    approved_institutions: Landmark,
    active_branches: GitBranch,
    borrower_profiles: Users,
    company_client_accounts: BriefcaseBusiness,
    loan_requests: ListChecks,
    loan_offers: HandCoins,
    loan_accounts: WalletCards,
    active_loans: Workflow,
    completed_loans: BadgeCheck,
    employee_profiles: Building2,
    managed_files: FileCheck2,
    generated_reports: FileText,
};

const labels: Record<keyof typeof iconByKey, string> = {
    approved_institutions: "Approved institutions",
    active_branches: "Active branches",
    borrower_profiles: "Borrower profiles",
    company_client_accounts: "Client relationships",
    loan_requests: "Loan requests",
    loan_offers: "Lender offers",
    loan_accounts: "Loan accounts",
    active_loans: "Active loans",
    completed_loans: "Completed loans",
    employee_profiles: "Employee profiles",
    managed_files: "Managed files",
    generated_reports: "Generated reports",
};

const keys = Object.keys(iconByKey) as Array<keyof typeof iconByKey>;

function formatValue(value: number): string {
    return new Intl.NumberFormat("en-LS").format(value);
}

export function LivePlatformStats({ compact = false }: { compact?: boolean }) {
    const [stats, setStats] = useState<PublicPlatformStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [unavailable, setUnavailable] = useState(false);

    useEffect(() => {
        const controller = new AbortController();
        const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

        fetch(`${baseUrl}/public/stats`, {
            method: "GET",
            cache: "no-store",
            credentials: "omit",
            signal: controller.signal,
        })
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error(`Public statistics request failed with ${response.status}`);
                }
                return (await response.json()) as PublicPlatformStats;
            })
            .then((payload) => {
                setStats(payload);
                setUnavailable(false);
            })
            .catch((error: unknown) => {
                if (error instanceof DOMException && error.name === "AbortError") {
                    return;
                }
                setUnavailable(true);
            })
            .finally(() => setLoading(false));

        return () => controller.abort();
    }, []);

    const visibleKeys = useMemo(
        () => (compact ? keys.slice(0, 4) : keys),
        [compact],
    );

    return (
        <section aria-label="Live LoanHub platform activity">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.22em] text-emerald-600 dark:text-emerald-400">
                        Live platform activity
                    </p>
                    {!compact && (
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            Privacy-safe platform-wide counts. No personal or tenant financial details are published.
                        </p>
                    )}
                </div>
                <span className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
                    <span className={`h-2 w-2 rounded-full ${unavailable ? "bg-amber-500" : loading ? "animate-pulse bg-sky-500" : "bg-emerald-500"}`} />
                    {unavailable ? "Temporarily unavailable" : loading ? "Connecting" : "Connected"}
                </span>
            </div>

            <div className={`grid gap-3 ${compact ? "grid-cols-2 lg:grid-cols-4" : "grid-cols-2 md:grid-cols-3 xl:grid-cols-4"}`}>
                {visibleKeys.map((key) => {
                    const Icon = iconByKey[key];
                    return (
                        <article
                            key={key}
                            className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <p className="text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">
                                        {stats ? formatValue(stats[key]) : "—"}
                                    </p>
                                    <p className="mt-1 text-xs font-semibold leading-5 text-slate-500 dark:text-slate-400 sm:text-sm">
                                        {labels[key]}
                                    </p>
                                </div>
                                <span className="rounded-xl bg-slate-100 p-2 text-slate-600 transition group-hover:bg-emerald-50 group-hover:text-emerald-700 dark:bg-slate-800 dark:text-slate-300 dark:group-hover:bg-emerald-950/60 dark:group-hover:text-emerald-300">
                                    <Icon className="h-4 w-4 sm:h-5 sm:w-5" />
                                </span>
                            </div>
                        </article>
                    );
                })}
            </div>

            {!compact && stats?.updated_at && (
                <p className="mt-3 text-right text-xs text-slate-400">
                    Snapshot refreshed {new Date(stats.updated_at).toLocaleString("en-LS")}
                </p>
            )}
        </section>
    );
}
