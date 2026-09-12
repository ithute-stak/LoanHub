"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import Link from "next/link";
import {
    Building2,
    CheckCircle2,
    ChevronLeft,
    ChevronRight,
    Copy,
    Eye,
    GitBranch,
    KeyRound,
    Loader2,
    MoreHorizontal,
    Pencil,
    Power,
    PowerOff,
    Search,
    Trash2,
    UserRoundCog,
    XCircle,
} from "lucide-react";

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type {
    CompaniesPageModel,
} from "../_hooks/use-companies-page";

import type {
    CompanyActivityFilter,
    CompanyStatusFilter,
} from "../_types/company-page";

import {
    CompanyActivityBadge,
    CompanyStatusBadge,
} from "./company-badges";

import {
    formatCompanyDate,
    normalizeCompanyStatus,
} from "../_lib/company-utils";

type Props =
    CompaniesPageModel["table"];

const PAGE_SIZE_OPTIONS = [
    8,
    16,
    24,
];

function TableSkeleton() {
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

export function CompaniesTable({
                                   companies,
                                   allCompanies,
                                   filteredCount,
                                   districtOptions,

                                   branchesByCompany,
                                   activeBranchesByCompany,
                                   staffByCompany,
                                   activeStaffByCompany,

                                   searchTerm,
                                   statusFilter,
                                   activityFilter,
                                   districtFilter,

                                   hasFilters,
                                   isLoading,
                                   workingCompanyId,

                                   firstResult,
                                   lastResult,
                                   currentPage,
                                   totalPages,
                                   itemsPerPage,

                                   onSearchChange,
                                   onStatusFilterChange,
                                   onActivityFilterChange,
                                   onDistrictFilterChange,
                                   onItemsPerPageChange,

                                   onPreviousPage,
                                   onNextPage,
                                   onResetFilters,

                                   onRunAction,
                                   onCopyCompanyId,
                                   onRequestDelete,
                                   onRequestEdit,
                                   onManageOwnerAccess,
                               }: Props) {
    return (
        <section className="overflow-visible rounded-3xl border bg-card shadow-sm">
            <StickyFilterBar
                ariaLabel="Company management search and filters"
                className="rounded-t-3xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
            >
            <div className="rounded-[inherit] border-b bg-card p-5 sm:p-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h2 className="text-xl font-black">
                            Company management
                        </h2>

                        <p className="mt-1 text-sm text-muted-foreground">
                            Search, review and manage
                            every registered company.
                        </p>
                    </div>

                    <span className="w-fit rounded-full bg-primary/10 px-3 py-1.5 text-sm font-bold text-primary">
                        {filteredCount} results
                    </span>
                </div>

                <div className="mt-5 grid gap-3 lg:grid-cols-2 xl:grid-cols-[1.4fr_0.7fr_0.7fr_0.8fr_auto]">
                    <SuggestionSearch
                        value={searchTerm}
                        onValueChange={onSearchChange}
                        suggestions={allCompanies.map((company) => ({
                            value: company.name,
                            label: company.name,
                            description: `${company.registration_number} · ${company.district}`,
                            keywords: [
                                company.id,
                                company.license_number,
                                company.phone,
                                company.email,
                                company.website,
                                company.address,
                                company.status,
                                company.is_active ? "active" : "inactive",
                            ],
                        }))}
                        placeholder="Type a company, registration, contact or district..."
                        suggestionLabel="Registered companies"
                        emptyMessage="No company matches that text."
                    />

                    <NativeSelect
                        value={statusFilter}
                        onChange={(event) =>
                            onStatusFilterChange(
                                event.target
                                    .value as CompanyStatusFilter,
                            )
                        }
                        className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold"
                    >
                        <option value="all">
                            All statuses
                        </option>
                        <option value="pending">
                            Pending
                        </option>
                        <option value="approved">
                            Approved
                        </option>
                        <option value="rejected">
                            Rejected
                        </option>
                    </NativeSelect>

                    <NativeSelect
                        value={activityFilter}
                        onChange={(event) =>
                            onActivityFilterChange(
                                event.target
                                    .value as CompanyActivityFilter,
                            )
                        }
                        className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold"
                    >
                        <option value="all">
                            All activity
                        </option>
                        <option value="active">
                            Active
                        </option>
                        <option value="inactive">
                            Inactive
                        </option>
                    </NativeSelect>

                    <NativeSelect
                        value={districtFilter}
                        onChange={(event) =>
                            onDistrictFilterChange(
                                event.target.value,
                            )
                        }
                        className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold"
                    >
                        <option value="all">
                            All districts
                        </option>

                        {districtOptions.map(
                            (district) => (
                                <option
                                    key={district}
                                    value={district}
                                >
                                    {district}
                                </option>
                            ),
                        )}
                    </NativeSelect>

                    <button
                        type="button"
                        onClick={onResetFilters}
                        disabled={!hasFilters}
                        className="h-11 rounded-xl border bg-background px-4 text-sm font-bold transition hover:border-primary hover:text-primary disabled:opacity-50"
                    >
                        Reset
                    </button>
                </div>
            </div>
            </StickyFilterBar>

            <div className="overflow-x-auto rounded-b-3xl">
                <table className="w-full min-w-[1250px] text-sm">
                    <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                    <tr>
                        <th className="px-5 py-4">
                            Company
                        </th>
                        <th className="px-4 py-4">
                            Registration
                        </th>
                        <th className="px-4 py-4">
                            Contact
                        </th>
                        <th className="px-4 py-4">
                            Footprint
                        </th>
                        <th className="px-4 py-4">
                            Status
                        </th>
                        <th className="px-4 py-4">
                            Activity
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
                    allCompanies.length ===
                    0 ? (
                        <TableSkeleton />
                    ) : companies.length ===
                    0 ? (
                        <tr>
                            <td
                                colSpan={8}
                                className="px-5 py-16 text-center"
                            >
                                <Building2 className="mx-auto h-10 w-10 text-muted-foreground" />

                                <h3 className="mt-4 font-black">
                                    No companies found
                                </h3>

                                <p className="mt-1 text-sm text-muted-foreground">
                                    No companies match
                                    the current filters.
                                </p>
                            </td>
                        </tr>
                    ) : (
                        companies.map(
                            (company) => {
                                const status =
                                    normalizeCompanyStatus(
                                        company.status,
                                    );

                                const isWorking =
                                    workingCompanyId ===
                                    company.id;

                                return (
                                    <tr
                                        key={company.id}
                                        className="border-t hover:bg-muted/30"
                                    >
                                        <td className="px-5 py-4">
                                            <Link
                                                href={`/superadmin/companies/${company.id}`}
                                                className="flex min-w-56 items-center gap-3"
                                            >
                                                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                                    <Building2 className="h-5 w-5" />
                                                </div>

                                                <div>
                                                    <p className="font-black hover:text-primary">
                                                        {
                                                            company.name
                                                        }
                                                    </p>

                                                    <p className="text-xs text-muted-foreground">
                                                        {company.district ||
                                                            "Not specified"}
                                                    </p>
                                                </div>
                                            </Link>
                                        </td>

                                        <td className="px-4 py-4">
                                            <p className="font-bold">
                                                {company.registration_number ||
                                                    "Not available"}
                                            </p>

                                            <p className="mt-1 text-xs text-muted-foreground">
                                                License:{" "}
                                                {company.license_number ||
                                                    "Not available"}
                                            </p>
                                        </td>

                                        <td className="px-4 py-4">
                                            <p className="font-semibold">
                                                {company.phone ||
                                                    "No phone"}
                                            </p>

                                            <p className="mt-1 text-xs text-muted-foreground">
                                                {company.email ||
                                                    "No email"}
                                            </p>
                                        </td>

                                        <td className="px-4 py-4">
                                            <div className="flex gap-3">
                                                <div className="rounded-xl bg-muted/70 px-3 py-2">
                                                    <div className="flex items-center gap-1.5">
                                                        <GitBranch className="h-3.5 w-3.5 text-primary" />
                                                        <strong>
                                                            {branchesByCompany.get(
                                                                    company.id,
                                                                ) ??
                                                                0}
                                                        </strong>
                                                    </div>

                                                    <p className="mt-1 text-[11px] text-muted-foreground">
                                                        {activeBranchesByCompany.get(
                                                                company.id,
                                                            ) ??
                                                            0}{" "}
                                                        active
                                                    </p>
                                                </div>

                                                <div className="rounded-xl bg-muted/70 px-3 py-2">
                                                    <div className="flex items-center gap-1.5">
                                                        <UserRoundCog className="h-3.5 w-3.5 text-primary" />
                                                        <strong>
                                                            {staffByCompany.get(
                                                                    company.id,
                                                                ) ??
                                                                0}
                                                        </strong>
                                                    </div>

                                                    <p className="mt-1 text-[11px] text-muted-foreground">
                                                        {activeStaffByCompany.get(
                                                                company.id,
                                                            ) ??
                                                            0}{" "}
                                                        active
                                                    </p>
                                                </div>
                                            </div>
                                        </td>

                                        <td className="px-4 py-4">
                                            <CompanyStatusBadge
                                                status={
                                                    company.status
                                                }
                                            />
                                        </td>

                                        <td className="px-4 py-4">
                                            <CompanyActivityBadge
                                                active={
                                                    company.is_active
                                                }
                                            />
                                        </td>

                                        <td className="px-4 py-4 text-muted-foreground">
                                            {formatCompanyDate(
                                                company.created_at,
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
                                                            className="inline-flex h-9 w-10 items-center justify-center rounded-xl border bg-background hover:border-primary"
                                                        >
                                                            <MoreHorizontal className="h-4 w-4" />
                                                        </button>
                                                    </DropdownMenuTrigger>

                                                    <DropdownMenuContent
                                                        align="end"
                                                        className="w-56"
                                                    >
                                                        <DropdownMenuLabel>
                                                            Company
                                                            actions
                                                        </DropdownMenuLabel>

                                                        <DropdownMenuSeparator />

                                                        <DropdownMenuItem
                                                            asChild
                                                        >
                                                            <Link
                                                                href={`/superadmin/companies/${company.id}`}
                                                                className="cursor-pointer gap-2"
                                                            >
                                                                <Eye className="h-4 w-4" />
                                                                View
                                                                company
                                                            </Link>
                                                        </DropdownMenuItem>

                                                        <DropdownMenuItem
                                                            onClick={() =>
                                                                void onCopyCompanyId(
                                                                    company,
                                                                )
                                                            }
                                                            className="cursor-pointer gap-2"
                                                        >
                                                            <Copy className="h-4 w-4" />
                                                            Copy
                                                            ID
                                                        </DropdownMenuItem>

                                                        <DropdownMenuItem
                                                            onClick={() => onRequestEdit(company)}
                                                            className="cursor-pointer gap-2"
                                                        >
                                                            <Pencil className="h-4 w-4" />
                                                            Edit company
                                                        </DropdownMenuItem>

                                                        <DropdownMenuItem
                                                            onClick={() => onManageOwnerAccess(company)}
                                                            className="cursor-pointer gap-2"
                                                        >
                                                            <KeyRound className="h-4 w-4" />
                                                            Manage owner login
                                                        </DropdownMenuItem>

                                                        <DropdownMenuSeparator />

                                                        {status !==
                                                            "approved" && (
                                                                <DropdownMenuItem
                                                                    onClick={() =>
                                                                        void onRunAction(
                                                                            company,
                                                                            "approve",
                                                                        )
                                                                    }
                                                                    className="cursor-pointer gap-2 text-green-600"
                                                                >
                                                                    <CheckCircle2 className="h-4 w-4" />
                                                                    Approve
                                                                </DropdownMenuItem>
                                                            )}

                                                        {status ===
                                                            "pending" && (
                                                                <DropdownMenuItem
                                                                    onClick={() =>
                                                                        void onRunAction(
                                                                            company,
                                                                            "reject",
                                                                        )
                                                                    }
                                                                    className="cursor-pointer gap-2 text-red-600"
                                                                >
                                                                    <XCircle className="h-4 w-4" />
                                                                    Reject
                                                                </DropdownMenuItem>
                                                            )}

                                                        {status ===
                                                            "approved" &&
                                                            company.is_active && (
                                                                <DropdownMenuItem
                                                                    onClick={() =>
                                                                        void onRunAction(
                                                                            company,
                                                                            "deactivate",
                                                                        )
                                                                    }
                                                                    className="cursor-pointer gap-2 text-red-600"
                                                                >
                                                                    <PowerOff className="h-4 w-4" />
                                                                    Deactivate
                                                                </DropdownMenuItem>
                                                            )}

                                                        {status ===
                                                            "approved" &&
                                                            !company.is_active && (
                                                                <DropdownMenuItem
                                                                    onClick={() =>
                                                                        void onRunAction(
                                                                            company,
                                                                            "activate",
                                                                        )
                                                                    }
                                                                    className="cursor-pointer gap-2 text-green-600"
                                                                >
                                                                    <Power className="h-4 w-4" />
                                                                    Activate
                                                                </DropdownMenuItem>
                                                            )}

                                                        <DropdownMenuSeparator />

                                                        <DropdownMenuItem
                                                            onClick={() =>
                                                                onRequestDelete(
                                                                    company,
                                                                )
                                                            }
                                                            className="cursor-pointer gap-2 text-red-600"
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                            Delete
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
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span>
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
                    </span>

                    <NativeSelect
                        value={itemsPerPage}
                        onChange={(event) =>
                            onItemsPerPageChange(
                                Number(
                                    event.target.value,
                                ),
                            )
                        }
                        className="h-8 rounded-lg border bg-background px-2"
                    >
                        {PAGE_SIZE_OPTIONS.map(
                            (option) => (
                                <option
                                    key={option}
                                    value={option}
                                >
                                    {option} rows
                                </option>
                            ),
                        )}
                    </NativeSelect>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={onPreviousPage}
                        disabled={
                            currentPage === 1
                        }
                        className="inline-flex h-9 items-center gap-1 rounded-xl border px-3 text-sm font-semibold disabled:opacity-50"
                    >
                        <ChevronLeft className="h-4 w-4" />
                        Previous
                    </button>

                    <span className="min-w-24 text-center text-sm">
                        Page {currentPage} of{" "}
                        {totalPages}
                    </span>

                    <button
                        type="button"
                        onClick={onNextPage}
                        disabled={
                            currentPage >=
                            totalPages
                        }
                        className="inline-flex h-9 items-center gap-1 rounded-xl border px-3 text-sm font-semibold disabled:opacity-50"
                    >
                        Next
                        <ChevronRight className="h-4 w-4" />
                    </button>
                </div>
            </div>
        </section>
    );
}
