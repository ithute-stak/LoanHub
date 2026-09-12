"use client";

import {
    Building2,
    ChevronLeft,
    ChevronRight,
    Copy,
    Edit3,
    Eye,
    GitBranch,
    Loader2,
    Mail,
    MapPin,
    MoreHorizontal,
    Phone,
    Power,
    PowerOff,
    Trash2,
    Users,
} from "lucide-react";
import { displayReference } from "@/lib/display-reference";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { toast } from "@/utils/toast";

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type {
    BranchesPageModel,
} from "../_hooks/use-branches-page";

import {
    formatBranchDate,
} from "../_lib/branch-utils";

import {
    BranchStatusBadge,
} from "./branch-badges";

import {
    BranchFilters,
} from "./branch-filters";

type Props =
    BranchesPageModel["table"];

function BranchTableSkeleton() {
    return (
        <>
            {Array.from({
                length: 6,
            }).map((_, index) => (
                <tr
                    key={index}
                    className="border-t"
                >
                    {Array.from({
                        length: 8,
                    }).map(
                        (
                            __,
                            cellIndex,
                        ) => (
                            <td
                                key={
                                    cellIndex
                                }
                                className="px-4 py-4"
                            >
                                <div className="h-5 animate-pulse rounded bg-muted" />
                            </td>
                        ),
                    )}
                </tr>
            ))}
        </>
    );
}

async function copyBranchId(
    branchId: string,
) {
    try {
        await navigator.clipboard.writeText(
            branchId,
        );

        toast.success(
            "Branch ID copied",
        );
    } catch {
        toast.error(
            "Branch ID could not be copied",
        );
    }
}

export function BranchTable({
    branches,
    allBranches,
    companies,
    districtOptions,

    searchTerm,
    statusFilter,
    companyFilter,
    districtFilter,
    sortBy,
    pageSize,

    filteredCount,
    firstResult,
    lastResult,
    currentPage,
    totalPages,

    hasFilters,
    isLoading,
    actionBranchId,

    staffByBranch,
    activeStaffByBranch,

    getCompanyName,

    onSearchChange,
    onStatusFilterChange,
    onCompanyFilterChange,
    onDistrictFilterChange,
    onSortChange,
    onPageSizeChange,
    onPreviousPage,
    onNextPage,
    onResetFilters,

    onView,
    onEdit,
    onToggleStatus,
    onDelete,
}: Props) {
    return (
        <section className="overflow-visible rounded-3xl border bg-card shadow-sm">
            <StickyFilterBar
                ariaLabel="Branch directory search and filters"
                className="rounded-t-3xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
            >
            <BranchFilters
                branches={allBranches}
                companies={companies}
                districtOptions={
                    districtOptions
                }
                searchTerm={searchTerm}
                statusFilter={
                    statusFilter
                }
                companyFilter={
                    companyFilter
                }
                districtFilter={
                    districtFilter
                }
                sortBy={sortBy}
                pageSize={pageSize}
                filteredCount={
                    filteredCount
                }
                hasFilters={hasFilters}
                onSearchChange={
                    onSearchChange
                }
                onStatusFilterChange={
                    onStatusFilterChange
                }
                onCompanyFilterChange={
                    onCompanyFilterChange
                }
                onDistrictFilterChange={
                    onDistrictFilterChange
                }
                onSortChange={
                    onSortChange
                }
                onPageSizeChange={
                    onPageSizeChange
                }
                onResetFilters={
                    onResetFilters
                }
            />
            </StickyFilterBar>

            <div className="space-y-3 overflow-hidden rounded-b-3xl p-4 lg:hidden">
                {isLoading &&
                allBranches.length === 0 ? (
                    Array.from({
                        length: 4,
                    }).map((_, index) => (
                        <div
                            key={index}
                            className="h-52 animate-pulse rounded-2xl bg-muted"
                        />
                    ))
                ) : branches.length ===
                  0 ? (
                    <div className="py-14 text-center">
                        <GitBranch className="mx-auto h-10 w-10 text-muted-foreground" />

                        <h3 className="mt-4 font-black">
                            No branches found
                        </h3>

                        <p className="mt-1 text-sm text-muted-foreground">
                            No branch matches the
                            selected filters.
                        </p>
                    </div>
                ) : (
                    branches.map(
                        (branch) => {
                            const staffCount =
                                staffByBranch.get(
                                    branch.id,
                                ) ?? 0;

                            const activeStaffCount =
                                activeStaffByBranch.get(
                                    branch.id,
                                ) ?? 0;

                            const isWorking =
                                actionBranchId ===
                                branch.id;

                            return (
                                <article
                                    key={branch.id}
                                    className="rounded-2xl border bg-background p-4"
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex min-w-0 items-center gap-3">
                                            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                                <GitBranch className="h-5 w-5" />
                                            </div>

                                            <div className="min-w-0">
                                                <p className="truncate font-black">
                                                    {branch.name}
                                                </p>

                                                <p className="truncate text-xs text-muted-foreground">
                                                    {getCompanyName(
                                                        branch.company_id,
                                                    )}
                                                </p>
                                            </div>
                                        </div>

                                        <BranchStatusBadge
                                            active={
                                                branch.is_active
                                            }
                                        />
                                    </div>

                                    <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                                        <div className="rounded-xl bg-muted/60 p-3">
                                            <p className="text-xs text-muted-foreground">
                                                Location
                                            </p>

                                            <p className="mt-1 font-bold">
                                                {branch.town},{" "}
                                                {branch.district}
                                            </p>
                                        </div>

                                        <div className="rounded-xl bg-muted/60 p-3">
                                            <p className="text-xs text-muted-foreground">
                                                Staff
                                            </p>

                                            <p className="mt-1 font-bold">
                                                {staffCount} total ·{" "}
                                                {activeStaffCount} active
                                            </p>
                                        </div>
                                    </div>

                                    <div className="mt-4 flex items-center justify-end gap-2">
                                        <button
                                            type="button"
                                            onClick={() =>
                                                onView(
                                                    branch,
                                                )
                                            }
                                            className="inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-sm font-bold"
                                        >
                                            <Eye className="h-4 w-4" />
                                            View
                                        </button>

                                        <button
                                            type="button"
                                            onClick={() =>
                                                onEdit(
                                                    branch,
                                                )
                                            }
                                            className="inline-flex h-9 items-center gap-2 rounded-xl bg-primary px-3 text-sm font-bold text-primary-foreground"
                                        >
                                            <Edit3 className="h-4 w-4" />
                                            Edit
                                        </button>
                                    </div>
                                </article>
                            );
                        },
                    )
                )}
            </div>

            <div className="hidden overflow-x-auto lg:block">
                <table className="w-full min-w-[1280px] text-sm">
                    <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                        <tr>
                            <th className="px-5 py-4">
                                Branch
                            </th>

                            <th className="px-4 py-4">
                                Company
                            </th>

                            <th className="px-4 py-4">
                                Location
                            </th>

                            <th className="px-4 py-4">
                                Contact
                            </th>

                            <th className="px-4 py-4">
                                Staff
                            </th>

                            <th className="px-4 py-4">
                                Status
                            </th>

                            <th className="px-4 py-4">
                                Created
                            </th>

                            <th className="px-5 py-4 text-right">
                                Actions
                            </th>
                        </tr>
                    </thead>

                    <tbody>
                        {isLoading &&
                        allBranches.length ===
                            0 ? (
                            <BranchTableSkeleton />
                        ) : branches.length ===
                          0 ? (
                            <tr>
                                <td
                                    colSpan={8}
                                    className="px-5 py-16 text-center"
                                >
                                    <div className="mx-auto flex max-w-sm flex-col items-center">
                                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                            <GitBranch className="h-7 w-7" />
                                        </div>

                                        <h3 className="mt-4 font-black">
                                            No branches found
                                        </h3>

                                        <p className="mt-1 text-sm text-muted-foreground">
                                            No branches
                                            match the selected
                                            filters.
                                        </p>

                                        {hasFilters && (
                                            <button
                                                type="button"
                                                onClick={
                                                    onResetFilters
                                                }
                                                className="mt-4 text-sm font-black text-primary hover:underline"
                                            >
                                                Clear filters
                                            </button>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            branches.map(
                                (branch) => {
                                    const staffCount =
                                        staffByBranch.get(
                                            branch.id,
                                        ) ?? 0;

                                    const activeStaffCount =
                                        activeStaffByBranch.get(
                                            branch.id,
                                        ) ?? 0;

                                    const isWorking =
                                        actionBranchId ===
                                        branch.id;

                                    return (
                                        <tr
                                            key={branch.id}
                                            className="border-t transition hover:bg-muted/30"
                                        >
                                            <td className="px-5 py-4">
                                                <div className="flex min-w-56 items-center gap-3">
                                                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                                        <GitBranch className="h-5 w-5" />
                                                    </div>

                                                    <div className="min-w-0">
                                                        <p className="truncate font-black">
                                                            {branch.name}
                                                        </p>

                                                        <p className="truncate text-xs font-semibold text-muted-foreground">
                                                            {displayReference(
                                                                "BRN",
                                                                branch.id,
                                                                branch.created_at,
                                                            )}
                                                        </p>
                                                    </div>
                                                </div>
                                            </td>

                                            <td className="px-4 py-4">
                                                <div className="flex items-center gap-2">
                                                    <Building2 className="h-4 w-4 text-primary" />

                                                    <span className="font-bold">
                                                        {getCompanyName(
                                                            branch.company_id,
                                                        )}
                                                    </span>
                                                </div>
                                            </td>

                                            <td className="px-4 py-4">
                                                <div className="flex items-start gap-2">
                                                    <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" />

                                                    <div>
                                                        <p className="font-bold">
                                                            {branch.town}
                                                        </p>

                                                        <p className="text-xs text-muted-foreground">
                                                            {branch.district}
                                                        </p>
                                                    </div>
                                                </div>
                                            </td>

                                            <td className="px-4 py-4">
                                                <div className="space-y-1 text-xs">
                                                    <p className="flex items-center gap-1.5 font-semibold">
                                                        <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                                                        {branch.phone ||
                                                            "No phone"}
                                                    </p>

                                                    <p className="flex items-center gap-1.5 text-muted-foreground">
                                                        <Mail className="h-3.5 w-3.5" />
                                                        {branch.email ||
                                                            "No email"}
                                                    </p>
                                                </div>
                                            </td>

                                            <td className="px-4 py-4">
                                                <div className="inline-flex items-center gap-2 rounded-xl bg-muted/70 px-3 py-2">
                                                    <Users className="h-4 w-4 text-primary" />

                                                    <div>
                                                        <p className="font-black">
                                                            {staffCount}
                                                        </p>

                                                        <p className="text-[10px] text-muted-foreground">
                                                            {activeStaffCount} active
                                                        </p>
                                                    </div>
                                                </div>
                                            </td>

                                            <td className="px-4 py-4">
                                                <BranchStatusBadge
                                                    active={
                                                        branch.is_active
                                                    }
                                                />
                                            </td>

                                            <td className="px-4 py-4 font-semibold text-muted-foreground">
                                                {formatBranchDate(
                                                    branch.created_at,
                                                )}
                                            </td>

                                            <td className="px-5 py-4 text-right">
                                                {isWorking ? (
                                                    <Loader2 className="ml-auto h-5 w-5 animate-spin text-primary" />
                                                ) : (
                                                    <DropdownMenu>
                                                        <DropdownMenuTrigger
                                                            asChild
                                                        >
                                                            <button
                                                                type="button"
                                                                aria-label={`Actions for ${branch.name}`}
                                                                className="inline-flex h-9 w-10 items-center justify-center rounded-xl border bg-background transition hover:border-primary hover:text-primary"
                                                            >
                                                                <MoreHorizontal className="h-4 w-4" />
                                                            </button>
                                                        </DropdownMenuTrigger>

                                                        <DropdownMenuContent
                                                            align="end"
                                                            className="w-60"
                                                        >
                                                            <DropdownMenuLabel>
                                                                Branch actions
                                                            </DropdownMenuLabel>

                                                            <DropdownMenuSeparator />

                                                            <DropdownMenuItem
                                                                onClick={() =>
                                                                    onView(
                                                                        branch,
                                                                    )
                                                                }
                                                                className="cursor-pointer gap-2"
                                                            >
                                                                <Eye className="h-4 w-4" />
                                                                View details
                                                            </DropdownMenuItem>

                                                            <DropdownMenuItem
                                                                onClick={() =>
                                                                    onEdit(
                                                                        branch,
                                                                    )
                                                                }
                                                                className="cursor-pointer gap-2"
                                                            >
                                                                <Edit3 className="h-4 w-4" />
                                                                Edit branch
                                                            </DropdownMenuItem>

                                                            <DropdownMenuItem
                                                                onClick={() =>
                                                                    void copyBranchId(
                                                                        branch.id,
                                                                    )
                                                                }
                                                                className="cursor-pointer gap-2"
                                                            >
                                                                <Copy className="h-4 w-4" />
                                                                Copy branch ID
                                                            </DropdownMenuItem>

                                                            <DropdownMenuSeparator />

                                                            <DropdownMenuItem
                                                                onClick={() =>
                                                                    void onToggleStatus(
                                                                        branch,
                                                                    )
                                                                }
                                                                className={`cursor-pointer gap-2 ${
                                                                    branch.is_active
                                                                        ? "text-red-600 focus:text-red-600"
                                                                        : "text-green-600 focus:text-green-600"
                                                                }`}
                                                            >
                                                                {branch.is_active ? (
                                                                    <>
                                                                        <PowerOff className="h-4 w-4" />
                                                                        Deactivate branch
                                                                    </>
                                                                ) : (
                                                                    <>
                                                                        <Power className="h-4 w-4" />
                                                                        Activate branch
                                                                    </>
                                                                )}
                                                            </DropdownMenuItem>

                                                            <DropdownMenuSeparator />

                                                            <DropdownMenuItem
                                                                onClick={() => {
                                                                    if (
                                                                        staffCount >
                                                                        0
                                                                    ) {
                                                                        toast.error(
                                                                            "Reassign branch staff before deleting this branch",
                                                                        );

                                                                        return;
                                                                    }

                                                                    onDelete(
                                                                        branch,
                                                                    );
                                                                }}
                                                                className="cursor-pointer gap-2 text-red-600 focus:text-red-600"
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                                {staffCount > 0
                                                                    ? "Reassign staff before deletion"
                                                                    : "Delete branch"}
                                                            </DropdownMenuItem>
                                                        </DropdownMenuContent>
                                                    </DropdownMenu>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                },
                            )
                        )}
                    </tbody>
                </table>
            </div>

            <div className="flex flex-col gap-4 border-t px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-muted-foreground">
                    Showing{" "}
                    <strong className="text-foreground">
                        {firstResult}
                    </strong>{" "}
                    to{" "}
                    <strong className="text-foreground">
                        {lastResult}
                    </strong>{" "}
                    of{" "}
                    <strong className="text-foreground">
                        {filteredCount}
                    </strong>
                </p>

                {pageSize !== "all" && (
                    <div className="flex items-center justify-between gap-2 sm:justify-end">
                        <button
                            type="button"
                            onClick={onPreviousPage}
                            disabled={
                                currentPage === 1
                            }
                            className="inline-flex h-9 items-center gap-1 rounded-xl border bg-background px-3 text-sm font-bold transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            <ChevronLeft className="h-4 w-4" />
                            Previous
                        </button>

                        <span className="min-w-24 text-center text-sm text-muted-foreground">
                            Page{" "}
                            <strong className="text-foreground">
                                {currentPage}
                            </strong>{" "}
                            of{" "}
                            <strong className="text-foreground">
                                {totalPages}
                            </strong>
                        </span>

                        <button
                            type="button"
                            onClick={onNextPage}
                            disabled={
                                currentPage >=
                                totalPages
                            }
                            className="inline-flex h-9 items-center gap-1 rounded-xl border bg-background px-3 text-sm font-bold transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Next
                            <ChevronRight className="h-4 w-4" />
                        </button>
                    </div>
                )}
            </div>
        </section>
    );
}
