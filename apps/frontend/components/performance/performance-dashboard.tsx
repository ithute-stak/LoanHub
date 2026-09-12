"use client";

import {
    Activity,
    AlertTriangle,
    Building2,
    GitBranch,
    HandCoins,
    Loader2,
    RefreshCcw,
    Trophy,
    Users,
    WalletCards,
} from "lucide-react";
import {
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import {
    getPerformanceOverview,
} from "@/api/performance";
import type {
    PerformanceOverview,
} from "@/types/performance";
import {
    getErrorMessage,
} from "@/utils/apiError";

function money(value: string | number): string {
    return new Intl.NumberFormat("en-LS", {
        style: "currency",
        currency: "LSL",
        maximumFractionDigits: 2,
    }).format(Number(value ?? 0));
}

function titleCase(value: string): string {
    return value
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) =>
            letter.toUpperCase(),
        );
}

function scoreTone(score: number): string {
    if (score >= 80) {
        return "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400";
    }
    if (score >= 60) {
        return "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400";
    }
    if (score >= 40) {
        return "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400";
    }
    return "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400";
}

export function PerformanceDashboard({
    mode,
}: {
    mode: "company" | "platform";
}) {
    const [data, setData] =
        useState<PerformanceOverview | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] =
        useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            setData(await getPerformanceOverview());
        } catch (requestError: unknown) {
            setError(
                getErrorMessage(
                    requestError,
                    "Could not load performance analytics.",
                ),
            );
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    const topEmployees = useMemo(
        () => data?.employees.slice(0, 10) ?? [],
        [data],
    );

    if (loading && !data) {
        return (
            <div className="flex min-h-[55vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                            Performance intelligence
                        </p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight">
                            {mode === "platform"
                                ? "Platform performance"
                                : "Company performance"}
                        </h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Compare employee output, branch
                            health, loan operations, repayment
                            quality and company-level performance.
                        </p>
                    </div>

                    <button
                        type="button"
                        onClick={() => void load()}
                        disabled={loading}
                        className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50"
                    >
                        <RefreshCcw
                            className={`h-4 w-4 ${
                                loading ? "animate-spin" : ""
                            }`}
                        />
                        Refresh analytics
                    </button>
                </div>
            </section>

            {error && (
                <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                    {error}
                </div>
            )}

            {data && (
                <>
                    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                        <Metric
                            icon={Users}
                            label="Employees"
                            value={data.employee_count.toLocaleString()}
                            note={`${data.average_employee_score.toFixed(1)} average score`}
                        />
                        <Metric
                            icon={GitBranch}
                            label="Branches"
                            value={data.branch_count.toLocaleString()}
                            note={`${data.company_count} companies in scope`}
                        />
                        <Metric
                            icon={HandCoins}
                            label="Active loans"
                            value={data.active_loans.toLocaleString()}
                            note={`${data.overdue_loans} currently overdue`}
                        />
                        <Metric
                            icon={WalletCards}
                            label="Successful payments"
                            value={money(
                                data.successful_payments,
                            )}
                            note={`${money(data.total_outstanding)} outstanding`}
                        />
                    </section>

                    {mode === "platform" && (
                        <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                            <SectionHeader
                                icon={Building2}
                                title="Company performance ranking"
                                description="Operational health across every tenant."
                            />
                            <div className="overflow-x-auto">
                                <table className="w-full min-w-[900px] text-sm">
                                    <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                                        <tr>
                                            <th className="px-5 py-4">Company</th>
                                            <th className="px-4 py-4">People</th>
                                            <th className="px-4 py-4">Loans</th>
                                            <th className="px-4 py-4">Outstanding</th>
                                            <th className="px-4 py-4">Payments</th>
                                            <th className="px-5 py-4">Score</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.companies.map((company, index) => (
                                            <tr key={company.company_id} className="border-t hover:bg-muted/30">
                                                <td className="px-5 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 font-black text-primary">
                                                            {index + 1}
                                                        </span>
                                                        <div>
                                                            <p className="font-black">{company.company_name}</p>
                                                            <p className="text-xs text-muted-foreground">{company.branch_count} branches</p>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4 font-bold">{company.employee_count}</td>
                                                <td className="px-4 py-4">
                                                    <p className="font-bold">{company.active_loans} active</p>
                                                    <p className="text-xs text-red-600">{company.overdue_loans} overdue</p>
                                                </td>
                                                <td className="px-4 py-4 font-bold">{money(company.outstanding_balance)}</td>
                                                <td className="px-4 py-4 font-bold">{money(company.successful_payments)}</td>
                                                <td className="px-5 py-4">
                                                    <Score value={company.operational_score} />
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    )}

                    <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                        <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                            <SectionHeader
                                icon={Trophy}
                                title="Employee leaderboard"
                                description="A blended score from activity, conversions, goals and reviews."
                            />
                            <div className="overflow-x-auto">
                                <table className="w-full min-w-[720px] text-sm">
                                    <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                                        <tr>
                                            <th className="px-5 py-3">Employee</th>
                                            <th className="px-4 py-3">Offers</th>
                                            <th className="px-4 py-3">Loans</th>
                                            <th className="px-4 py-3">Goals</th>
                                            <th className="px-5 py-3">Score</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {topEmployees.map((employee, index) => (
                                            <tr key={employee.staff_id} className="border-t hover:bg-muted/30">
                                                <td className="px-5 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-muted font-black">
                                                            {index + 1}
                                                        </span>
                                                        <div>
                                                            <p className="font-black">{employee.employee_name}</p>
                                                            <p className="text-xs text-muted-foreground">{employee.job_title ?? titleCase(employee.role)}</p>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <p className="font-bold">{employee.offers_created}</p>
                                                    <p className="text-xs text-muted-foreground">{employee.offers_accepted} accepted</p>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <p className="font-bold">{employee.loans_approved} approved</p>
                                                    <p className="text-xs text-muted-foreground">{employee.loans_disbursed} disbursed</p>
                                                </td>
                                                <td className="px-4 py-4 font-bold">
                                                    {employee.goal_completion_percent.toFixed(0)}%
                                                </td>
                                                <td className="px-5 py-4"><Score value={employee.performance_score} /></td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </article>

                        <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                            <SectionHeader
                                icon={GitBranch}
                                title="Branch comparison"
                                description="Branch workforce and portfolio performance."
                            />
                            <div className="divide-y">
                                {data.branches.map((branch) => (
                                    <div key={branch.branch_id ?? branch.branch_name} className="p-5">
                                        <div className="flex items-start justify-between gap-4">
                                            <div>
                                                <p className="font-black">{branch.branch_name}</p>
                                                <p className="mt-1 text-xs text-muted-foreground">
                                                    {branch.employee_count} employees · {branch.active_loans} active loans
                                                </p>
                                            </div>
                                            <Score value={branch.average_employee_score} />
                                        </div>
                                        <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                                            <div className="rounded-xl bg-muted/60 p-3">
                                                <p className="text-muted-foreground">Loan principal</p>
                                                <p className="mt-1 font-black">{money(branch.loan_principal)}</p>
                                            </div>
                                            <div className="rounded-xl bg-muted/60 p-3">
                                                <p className="text-muted-foreground">Payments</p>
                                                <p className="mt-1 font-black">{money(branch.payments_received)}</p>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                                {data.branches.length === 0 && (
                                    <div className="p-10 text-center text-sm text-muted-foreground">
                                        No branch performance data is available.
                                    </div>
                                )}
                            </div>
                        </article>
                    </section>
                </>
            )}
        </main>
    );
}

function Metric({ icon: Icon, label, value, note }: { icon: typeof Users; label: string; value: string; note: string }) {
    return (
        <article className="rounded-3xl border bg-card p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-sm font-bold text-muted-foreground">{label}</p>
                    <p className="mt-2 text-2xl font-black tracking-tight">{value}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{note}</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                </div>
            </div>
        </article>
    );
}

function SectionHeader({ icon: Icon, title, description }: { icon: typeof Activity; title: string; description: string }) {
    return (
        <div className="flex items-start gap-3 border-b p-5 sm:p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="h-5 w-5" />
            </div>
            <div>
                <h2 className="text-lg font-black">{title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{description}</p>
            </div>
        </div>
    );
}

function Score({ value }: { value: number }) {
    return (
        <span className={`inline-flex min-w-16 items-center justify-center rounded-full px-2.5 py-1 text-xs font-black ${scoreTone(value)}`}>
            {value.toFixed(1)}
        </span>
    );
}
