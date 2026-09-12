"use client";

import {
    Building2,
    GitBranch,
    MapPin,
    Users,
} from "lucide-react";

import type {
    BranchesPageModel,
} from "../_hooks/use-branches-page";

import {
    formatBranchDate,
    getPercentage,
} from "../_lib/branch-utils";

import {
    BranchStatusBadge,
} from "./branch-badges";

import {
    BranchStats,
} from "./branch-stats";


type Props =
    BranchesPageModel["overview"];

export function BranchAnalytics({
    stats,
    districtAnalytics,
    companyAnalytics,
    recentBranches,
    getCompanyName,
    staffByBranch,
    pageError,
}: Props) {
    const largestDistrict =
        Math.max(
            1,
            ...districtAnalytics.map(
                (item) =>
                    item.branches,
            ),
        );

    const largestCompany =
        Math.max(
            1,
            ...companyAnalytics.map(
                (item) =>
                    item.branches,
            ),
        );

    return (
        <div className="space-y-6">
            {pageError && (
                <section className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                    <p className="font-black">
                        Some branch data could not be loaded
                    </p>

                    <p className="mt-1">
                        {pageError}
                    </p>
                </section>
            )}

            <BranchStats stats={stats} />

            <section className="grid gap-6 xl:grid-cols-2">
                <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                    <div className="flex items-start justify-between gap-4 border-b p-5 sm:p-6">
                        <div>
                            <h2 className="text-lg font-black">
                                District coverage
                            </h2>

                            <p className="mt-1 text-sm text-muted-foreground">
                                Branch, company and staff distribution
                                by district.
                            </p>
                        </div>

                        <MapPin className="h-5 w-5 text-primary" />
                    </div>

                    <div className="max-h-[380px] overflow-auto">
                        <table className="w-full min-w-[650px] text-sm">
                            <thead className="sticky top-0 bg-muted/90 text-left text-xs uppercase text-muted-foreground backdrop-blur">
                                <tr>
                                    <th className="px-5 py-3">
                                        District
                                    </th>

                                    <th className="px-4 py-3">
                                        Branches
                                    </th>

                                    <th className="px-4 py-3">
                                        Active
                                    </th>

                                    <th className="px-4 py-3">
                                        Companies
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
                                            key={item.district}
                                            className="border-t"
                                        >
                                            <td className="px-5 py-4">
                                                <p className="font-bold">
                                                    {item.district}
                                                </p>

                                                <div className="mt-2 h-1.5 w-36 overflow-hidden rounded-full bg-muted">
                                                    <div
                                                        className="h-full rounded-full bg-primary"
                                                        style={{
                                                            width: `${getPercentage(
                                                                item.branches,
                                                                largestDistrict,
                                                            )}%`,
                                                        }}
                                                    />
                                                </div>
                                            </td>

                                            <td className="px-4 py-4 font-black">
                                                {item.branches}
                                            </td>

                                            <td className="px-4 py-4 font-bold text-green-600 dark:text-green-400">
                                                {item.activeBranches}
                                            </td>

                                            <td className="px-4 py-4 font-bold">
                                                {item.companies}
                                            </td>

                                            <td className="px-4 py-4 font-bold">
                                                {item.staff}
                                            </td>
                                        </tr>
                                    ),
                                )}

                                {districtAnalytics.length ===
                                    0 && (
                                    <tr>
                                        <td
                                            colSpan={5}
                                            className="px-5 py-12 text-center text-muted-foreground"
                                        >
                                            No district analytics are
                                            available.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </article>

                <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                    <div className="flex items-start justify-between gap-4 border-b p-5 sm:p-6">
                        <div>
                            <h2 className="text-lg font-black">
                                Company branch footprint
                            </h2>

                            <p className="mt-1 text-sm text-muted-foreground">
                                Companies with the largest branch
                                networks.
                            </p>
                        </div>

                        <Building2 className="h-5 w-5 text-primary" />
                    </div>

                    <div className="max-h-[380px] space-y-4 overflow-auto p-5 sm:p-6">
                        {companyAnalytics
                            .slice(0, 10)
                            .map((item) => (
                                <div
                                    key={item.companyId}
                                    className="rounded-2xl border bg-background p-4"
                                >
                                    <div className="flex items-start justify-between gap-4">
                                        <div>
                                            <p className="font-black">
                                                {item.companyName}
                                            </p>

                                            <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                                                <span className="inline-flex items-center gap-1">
                                                    <GitBranch className="h-3.5 w-3.5" />
                                                    {item.activeBranches} active
                                                </span>

                                                <span className="inline-flex items-center gap-1">
                                                    <Users className="h-3.5 w-3.5" />
                                                    {item.staff} staff
                                                </span>
                                            </div>
                                        </div>

                                        <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-black text-primary">
                                            {item.branches}
                                        </span>
                                    </div>

                                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
                                        <div
                                            className="h-full rounded-full bg-primary"
                                            style={{
                                                width: `${getPercentage(
                                                    item.branches,
                                                    largestCompany,
                                                )}%`,
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}

                        {companyAnalytics.length ===
                            0 && (
                            <p className="py-10 text-center text-sm text-muted-foreground">
                                No company branch data is available.
                            </p>
                        )}
                    </div>
                </article>
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="border-b p-5 sm:p-6">
                    <h2 className="text-lg font-black">
                        Recent branches
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">
                        The newest branches registered on LoanHub.
                    </p>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[900px] text-sm">
                        <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                            <tr>
                                <th className="px-5 py-3">
                                    Branch
                                </th>

                                <th className="px-4 py-3">
                                    Company
                                </th>

                                <th className="px-4 py-3">
                                    Location
                                </th>

                                <th className="px-4 py-3">
                                    Staff
                                </th>

                                <th className="px-4 py-3">
                                    Status
                                </th>

                                <th className="px-4 py-3">
                                    Created
                                </th>
                            </tr>
                        </thead>

                        <tbody>
                            {recentBranches.map(
                                (branch) => (
                                    <tr
                                        key={branch.id}
                                        className="border-t transition hover:bg-muted/30"
                                    >
                                        <td className="px-5 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                                    <GitBranch className="h-5 w-5" />
                                                </div>

                                                <div>
                                                    <p className="font-black hover:text-primary">
                                                        {branch.name}
                                                    </p>

                                                    <p className="text-xs text-muted-foreground">
                                                        {branch.phone}
                                                    </p>
                                                </div>
                                            </div>
                                        </td>

                                        <td className="px-4 py-4 font-semibold">
                                            {getCompanyName(
                                                branch.company_id,
                                            )}
                                        </td>

                                        <td className="px-4 py-4">
                                            <p className="font-semibold">
                                                {branch.town}
                                            </p>

                                            <p className="text-xs text-muted-foreground">
                                                {branch.district}
                                            </p>
                                        </td>

                                        <td className="px-4 py-4 font-black">
                                            {staffByBranch.get(
                                                branch.id,
                                            ) ?? 0}
                                        </td>

                                        <td className="px-4 py-4">
                                            <BranchStatusBadge
                                                active={
                                                    branch.is_active
                                                }
                                            />
                                        </td>

                                        <td className="px-4 py-4 text-muted-foreground">
                                            {formatBranchDate(
                                                branch.created_at,
                                            )}
                                        </td>
                                    </tr>
                                ),
                            )}

                            {recentBranches.length ===
                                0 && (
                                <tr>
                                    <td
                                        colSpan={6}
                                        className="px-5 py-12 text-center text-muted-foreground"
                                    >
                                        No branches are available.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}

