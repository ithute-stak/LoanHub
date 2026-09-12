"use client";

import Link from "next/link";
import {
    Activity,
    AlertCircle,
    Building2,
    CheckCircle2,
    Download,
    GitBranch,
    MapPin,
    RefreshCcw,
    ShieldCheck,
    TrendingUp,
    Users,
    XCircle,
    type LucideIcon,
} from "lucide-react";

import type {
    CompaniesPageModel,
} from "../_hooks/use-companies-page";

import {
    CompanyStatusBadge,
} from "./company-badges";

import {
    formatCompanyDate,
    formatPercentage,
    getPercentage,
} from "../_lib/company-utils";

type Props =
    CompaniesPageModel["overview"];

function MetricCard({
                        title,
                        value,
                        description,
                        icon: Icon,
                    }: {
    title: string;
    value: string;
    description: string;
    icon: LucideIcon;
}) {
    return (
        <article className="rounded-3xl border bg-card p-5 shadow-sm transition hover:border-primary/30 hover:shadow-md">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-sm font-semibold text-muted-foreground">
                        {title}
                    </p>

                    <p className="mt-3 text-3xl font-black tracking-tight">
                        {value}
                    </p>

                    <p className="mt-2 text-xs leading-5 text-muted-foreground">
                        {description}
                    </p>
                </div>

                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Icon className="h-6 w-6" />
                </div>
            </div>
        </article>
    );
}

export function CompaniesOverview({
                                      stats,
                                      districtAnalytics,
                                      recentCompanies,
                                      branchesByCompany,
                                      staffByCompany,
                                      isLoading,
                                      pageError,
                                      onRefresh,
                                      onExport,
                                  }: Props) {
    const largestDistrictCount =
        Math.max(
            1,
            ...districtAnalytics.map(
                (item) => item.companies,
            ),
        );

    const statusItems = [
        {
            label: "Approved",
            count:
            stats.approvedCompanies,
            className: "bg-green-500",
        },
        {
            label: "Pending",
            count:
            stats.pendingCompanies,
            className: "bg-amber-500",
        },
        {
            label: "Rejected",
            count:
            stats.rejectedCompanies,
            className: "bg-red-500",
        },
    ];

    return (
        <div className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />

                <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-full border bg-background px-4 py-2 text-xs font-bold text-muted-foreground">
                            <ShieldCheck className="h-4 w-4 text-primary" />
                            Super administrator
                        </div>

                        <h1 className="mt-5 text-3xl font-black tracking-tight md:text-4xl">
                            Loan companies
                        </h1>

                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
                            Monitor registrations,
                            approvals, branches, staff
                            coverage and company activity
                            across LoanHub.
                        </p>
                    </div>

                    <div className="flex flex-wrap gap-3">
                        <button
                            type="button"
                            onClick={onExport}
                            disabled={
                                stats.totalCompanies ===
                                0
                            }
                            className="inline-flex h-11 items-center gap-2 rounded-xl border bg-background px-4 text-sm font-bold transition hover:border-primary hover:text-primary disabled:opacity-50"
                        >
                            <Download className="h-4 w-4" />
                            Export CSV
                        </button>

                        <button
                            type="button"
                            onClick={onRefresh}
                            disabled={isLoading}
                            className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground transition hover:bg-primary/90 disabled:opacity-60"
                        >
                            <RefreshCcw
                                className={`h-4 w-4 ${
                                    isLoading
                                        ? "animate-spin"
                                        : ""
                                }`}
                            />
                            Refresh
                        </button>
                    </div>
                </div>
            </section>

            {pageError && (
                <section className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />

                    <div>
                        <p className="font-bold">
                            Some company data could
                            not be loaded
                        </p>

                        <p className="mt-1">
                            {pageError}
                        </p>
                    </div>
                </section>
            )}

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                    title="Registered companies"
                    value={stats.totalCompanies.toLocaleString()}
                    description={`${stats.newCompaniesLast30Days} added in the last 30 days`}
                    icon={Building2}
                />

                <MetricCard
                    title="Approved companies"
                    value={stats.approvedCompanies.toLocaleString()}
                    description={`${formatPercentage(
                        stats.approvalRate,
                    )} approval rate`}
                    icon={CheckCircle2}
                />

                <MetricCard
                    title="Pending review"
                    value={stats.pendingCompanies.toLocaleString()}
                    description="Applications awaiting review"
                    icon={TrendingUp}
                />

                <MetricCard
                    title="Active companies"
                    value={stats.activeCompanies.toLocaleString()}
                    description={`${formatPercentage(
                        stats.activeRate,
                    )} operational rate`}
                    icon={Activity}
                />

                <MetricCard
                    title="Branches"
                    value={stats.totalBranches.toLocaleString()}
                    description={`${stats.activeBranches} active branches`}
                    icon={GitBranch}
                />

                <MetricCard
                    title="Company staff"
                    value={stats.totalStaff.toLocaleString()}
                    description={`${stats.activeStaff} active staff accounts`}
                    icon={Users}
                />

                <MetricCard
                    title="Rejected"
                    value={stats.rejectedCompanies.toLocaleString()}
                    description={`${stats.inactiveCompanies} companies inactive`}
                    icon={XCircle}
                />

                <MetricCard
                    title="Average footprint"
                    value={`${stats.averageBranches.toFixed(
                        1,
                    )} branches`}
                    description={`${stats.averageStaff.toFixed(
                        1,
                    )} staff per company`}
                    icon={MapPin}
                />
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
                <article className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
                    <h2 className="text-lg font-black">
                        Registration status
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Company application
                        distribution.
                    </p>

                    <div className="mt-6 space-y-5">
                        {statusItems.map((item) => {
                            const percentage =
                                getPercentage(
                                    item.count,
                                    stats.totalCompanies,
                                );

                            return (
                                <div key={item.label}>
                                    <div className="mb-2 flex justify-between text-sm">
                                        <span className="font-bold">
                                            {item.label}
                                        </span>

                                        <span className="font-black">
                                            {item.count}{" "}
                                            <span className="font-medium text-muted-foreground">
                                                (
                                                {formatPercentage(
                                                    percentage,
                                                )}
                                                )
                                            </span>
                                        </span>
                                    </div>

                                    <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                                        <div
                                            className={`h-full rounded-full ${item.className}`}
                                            style={{
                                                width: `${percentage}%`,
                                            }}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </article>

                <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                    <div className="border-b p-5 sm:p-6">
                        <h2 className="text-lg font-black">
                            District coverage
                        </h2>

                        <p className="mt-1 text-sm text-muted-foreground">
                            Company presence by
                            district.
                        </p>
                    </div>

                    <div className="max-h-80 overflow-auto">
                        <table className="w-full min-w-[520px] text-sm">
                            <thead className="sticky top-0 bg-muted/90 text-left text-xs uppercase text-muted-foreground">
                            <tr>
                                <th className="px-5 py-3">
                                    District
                                </th>

                                <th className="px-4 py-3">
                                    Companies
                                </th>

                                <th className="px-4 py-3">
                                    Branches
                                </th>

                                <th className="px-4 py-3">
                                    Staff
                                </th>
                            </tr>
                            </thead>

                            <tbody>
                            {districtAnalytics.map(
                                (item) => (
                                    <tr
                                        key={
                                            item.district
                                        }
                                        className="border-t"
                                    >
                                        <td className="px-5 py-4">
                                            <p className="font-bold">
                                                {
                                                    item.district
                                                }
                                            </p>

                                            <div className="mt-2 h-1.5 w-32 overflow-hidden rounded-full bg-muted">
                                                <div
                                                    className="h-full rounded-full bg-primary"
                                                    style={{
                                                        width: `${getPercentage(
                                                            item.companies,
                                                            largestDistrictCount,
                                                        )}%`,
                                                    }}
                                                />
                                            </div>
                                        </td>

                                        <td className="px-4 py-4 font-black">
                                            {
                                                item.companies
                                            }
                                        </td>

                                        <td className="px-4 py-4 font-bold">
                                            {
                                                item.branches
                                            }
                                        </td>

                                        <td className="px-4 py-4 font-bold">
                                            {
                                                item.staff
                                            }
                                        </td>
                                    </tr>
                                ),
                            )}

                            {districtAnalytics.length ===
                                0 && (
                                    <tr>
                                        <td
                                            colSpan={4}
                                            className="px-5 py-10 text-center text-muted-foreground"
                                        >
                                            No district data
                                            available.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </article>
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="border-b p-5 sm:p-6">
                    <h2 className="text-lg font-black">
                        Recent registrations
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">
                        The newest lending companies
                        added to LoanHub.
                    </p>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[800px] text-sm">
                        <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                        <tr>
                            <th className="px-5 py-3">
                                Company
                            </th>

                            <th className="px-4 py-3">
                                District
                            </th>

                            <th className="px-4 py-3">
                                Status
                            </th>

                            <th className="px-4 py-3">
                                Branches
                            </th>

                            <th className="px-4 py-3">
                                Staff
                            </th>

                            <th className="px-4 py-3">
                                Registered
                            </th>
                        </tr>
                        </thead>

                        <tbody>
                        {recentCompanies.map(
                            (company) => (
                                <tr
                                    key={company.id}
                                    className="border-t hover:bg-muted/30"
                                >
                                    <td className="px-5 py-4">
                                        <Link
                                            href={`/superadmin/companies/${company.id}`}
                                            className="flex items-center gap-3"
                                        >
                                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                                <Building2 className="h-5 w-5" />
                                            </div>

                                            <div>
                                                <p className="font-bold hover:text-primary">
                                                    {
                                                        company.name
                                                    }
                                                </p>

                                                <p className="text-xs text-muted-foreground">
                                                    {
                                                        company.email
                                                    }
                                                </p>
                                            </div>
                                        </Link>
                                    </td>

                                    <td className="px-4 py-4 font-semibold">
                                        {company.district ||
                                            "Not specified"}
                                    </td>

                                    <td className="px-4 py-4">
                                        <CompanyStatusBadge
                                            status={
                                                company.status
                                            }
                                        />
                                    </td>

                                    <td className="px-4 py-4 font-bold">
                                        {branchesByCompany.get(
                                            company.id,
                                        ) ?? 0}
                                    </td>

                                    <td className="px-4 py-4 font-bold">
                                        {staffByCompany.get(
                                            company.id,
                                        ) ?? 0}
                                    </td>

                                    <td className="px-4 py-4 text-muted-foreground">
                                        {formatCompanyDate(
                                            company.created_at,
                                        )}
                                    </td>
                                </tr>
                            ),
                        )}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}