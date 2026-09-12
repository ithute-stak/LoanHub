"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import {
    Filter,
    RotateCcw,
    Search,
} from "lucide-react";

import type {
    LoanCompany,
} from "@/store/slices/companiesSlice";
import type { Branch } from "@/types/branch";

import type {
    BranchPageSize,
    BranchSort,
    BranchStatusFilter,
} from "../_types/branch-page";

type Props = {
    branches: Branch[];
    companies: LoanCompany[];
    districtOptions: string[];

    searchTerm: string;
    statusFilter: BranchStatusFilter;
    companyFilter: string;
    districtFilter: string;
    sortBy: BranchSort;
    pageSize: BranchPageSize;

    filteredCount: number;
    hasFilters: boolean;

    onSearchChange: (value: string) => void;
    onStatusFilterChange: (
        value: BranchStatusFilter,
    ) => void;
    onCompanyFilterChange: (
        value: string,
    ) => void;
    onDistrictFilterChange: (
        value: string,
    ) => void;
    onSortChange: (
        value: BranchSort,
    ) => void;
    onPageSizeChange: (
        value: BranchPageSize,
    ) => void;
    onResetFilters: () => void;
};

const PAGE_SIZE_OPTIONS: BranchPageSize[] = [
    6,
    12,
    24,
    48,
    "all",
];

export function BranchFilters({
    branches,
    companies,
    districtOptions,

    searchTerm,
    statusFilter,
    companyFilter,
    districtFilter,
    sortBy,
    pageSize,

    filteredCount,
    hasFilters,

    onSearchChange,
    onStatusFilterChange,
    onCompanyFilterChange,
    onDistrictFilterChange,
    onSortChange,
    onPageSizeChange,
    onResetFilters,
}: Props) {
    return (
        <div className="border-b p-5 sm:p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <Filter className="h-5 w-5 text-primary" />

                        <h2 className="text-xl font-black">
                            Branch directory
                        </h2>
                    </div>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Search, filter and manage every
                        registered branch.
                    </p>
                </div>

                <span className="w-fit rounded-full bg-primary/10 px-3 py-1.5 text-sm font-black text-primary">
                    {filteredCount.toLocaleString()} result
                    {filteredCount === 1 ? "" : "s"}
                </span>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-[1.4fr_0.7fr_0.9fr_0.8fr_0.8fr_0.6fr_auto]">
                <SuggestionSearch
                    value={searchTerm}
                    onValueChange={onSearchChange}
                    suggestions={branches.map((branch) => {
                        const company = companies.find((item) => item.id === branch.company_id);
                        return {
                            value: branch.name,
                            label: branch.name,
                            description: [company?.name, branch.district, branch.town].filter(Boolean).join(" · "),
                            keywords: [branch.id, branch.address ?? "", branch.phone ?? "", branch.email ?? "", company?.registration_number ?? ""],
                        };
                    })}
                    placeholder="Type a branch, company, location or phone..."
                    suggestionLabel="Registered branches"
                    emptyMessage="No branch matches that text."
                    wrapperClassName="md:col-span-2 xl:col-span-1"
                />

                <NativeSelect
                    value={statusFilter}
                    onChange={(event) =>
                        onStatusFilterChange(
                            event.target
                                .value as BranchStatusFilter,
                        )
                    }
                    aria-label="Filter branches by status"
                    className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                    <option value="all">
                        All statuses
                    </option>

                    <option value="active">
                        Active
                    </option>

                    <option value="inactive">
                        Inactive
                    </option>
                </NativeSelect>

                <NativeSelect
                    value={companyFilter}
                    onChange={(event) =>
                        onCompanyFilterChange(
                            event.target.value,
                        )
                    }
                    aria-label="Filter branches by company"
                    className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                    <option value="all">
                        All companies
                    </option>

                    {[...companies]
                        .sort((first, second) =>
                            first.name.localeCompare(
                                second.name,
                            ),
                        )
                        .map((company) => (
                            <option
                                key={company.id}
                                value={company.id}
                            >
                                {company.name}
                            </option>
                        ))}
                </NativeSelect>

                <NativeSelect
                    value={districtFilter}
                    onChange={(event) =>
                        onDistrictFilterChange(
                            event.target.value,
                        )
                    }
                    aria-label="Filter branches by district"
                    className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
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

                <NativeSelect
                    value={sortBy}
                    onChange={(event) =>
                        onSortChange(
                            event.target
                                .value as BranchSort,
                        )
                    }
                    aria-label="Sort branches"
                    className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                    <option value="newest">
                        Newest first
                    </option>

                    <option value="oldest">
                        Oldest first
                    </option>

                    <option value="name_asc">
                        Name A–Z
                    </option>

                    <option value="name_desc">
                        Name Z–A
                    </option>

                    <option value="company_asc">
                        Company A–Z
                    </option>

                    <option value="district_asc">
                        District A–Z
                    </option>
                </NativeSelect>

                <NativeSelect
                    value={pageSize}
                    onChange={(event) => {
                        const value =
                            event.target.value;

                        onPageSizeChange(
                            value === "all"
                                ? "all"
                                : (Number(
                                      value,
                                  ) as BranchPageSize),
                        );
                    }}
                    aria-label="Rows per page"
                    className="h-11 rounded-xl border bg-background px-3 text-sm font-semibold outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                    {PAGE_SIZE_OPTIONS.map(
                        (option) => (
                            <option
                                key={String(option)}
                                value={option}
                            >
                                {option === "all"
                                    ? "All rows"
                                    : `${option} rows`}
                            </option>
                        ),
                    )}
                </NativeSelect>

                <button
                    type="button"
                    onClick={onResetFilters}
                    disabled={!hasFilters}
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                >
                    <RotateCcw className="h-4 w-4" />
                    Reset
                </button>
            </div>
        </div>
    );
}
