"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import {
    AlertCircle,
    ChevronLeft,
    ChevronRight,
    Edit3,
    Mail,
    Phone,
    RefreshCw,
    Search,
    UserRound,
    Users,
} from "lucide-react";
import {
    useMemo,
    useState,
} from "react";


import type {
    CompanyStaff,
    UserRole,
} from "@/types/companyStuff";
import type { Person } from "@/types/person";

import {
    type SavedAdminResult,
    UserEditDialog,
} from "./userEditDialog";
import {useAppData} from "@/provider/appDataProvider";

type AdminOverride = {
    email: string | null;
    phone: string;
    accountIsActive: boolean;
    staffIsActive: boolean;
    person: Person;
};

function formatRole(role: UserRole): string {
    return String(role)
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) =>
            letter.toUpperCase(),
        );
}

function getInitials(
    person: Person | null,
): string {
    if (!person) {
        return "?";
    }

    const firstInitial =
        person.first_name?.charAt(0) ?? "";

    const lastInitial =
        person.last_name?.charAt(0) ?? "";

    return `${firstInitial}${lastInitial}`.toUpperCase();
}

function getFullName(
    person: Person | null,
): string {
    if (!person) {
        return "";
    }

    if (person.full_name?.trim()) {
        return person.full_name.trim();
    }

    return [
        person.first_name,
        person.middle_name,
        person.last_name,
    ]
        .filter(Boolean)
        .join(" ");
}

export function CompanyAdminTable() {
    const {
        companies,
        companyStaff,
        getCompanyName,

        isCompaniesLoading,
        isCompanyStaffLoading,

        errors,
        refreshAllData,
    } = useAppData();

    const [searchTerm, setSearchTerm] =
        useState("");

    const [
        companyFilter,
        setCompanyFilter,
    ] = useState("all");

    const [
        roleFilter,
        setRoleFilter,
    ] = useState("all");

    const [
        statusFilter,
        setStatusFilter,
    ] = useState("all");

    const [
        currentPage,
        setCurrentPage,
    ] = useState(1);

    const [
        itemsPerPage,
        setItemsPerPage,
    ] = useState(6);

    const [
        selectedAdmin,
        setSelectedAdmin,
    ] = useState<CompanyStaff | null>(
        null,
    );

    const [
        adminOverrides,
        setAdminOverrides,
    ] = useState<
        Record<string, AdminOverride>
    >({});

    /*
     * The AppDataProvider may return every company staff role.
     * This table displays company administrators only.
     */
    const admins = useMemo(() => {
        return companyStaff.filter(
            (staff) =>
                String(staff.role).toLowerCase() ===
                "company_admin",
        );
    }, [companyStaff]);

    const availableCompanies = useMemo(() => {
        const administratorCompanyIds =
            new Set(
                admins
                    .map(
                        (admin) =>
                            admin.company_id,
                    )
                    .filter(
                        (
                            companyId,
                        ): companyId is string =>
                            typeof companyId ===
                            "string" &&
                            companyId.length > 0,
                    ),
            );

        return companies
            .filter((company) =>
                administratorCompanyIds.has(
                    company.id,
                ),
            )
            .sort((first, second) =>
                first.name.localeCompare(
                    second.name,
                ),
            );
    }, [admins, companies]);

    const availableRoles =
        useMemo<UserRole[]>(() => {
            return Array.from(
                new Set(
                    admins.map(
                        (admin) =>
                            admin.role,
                    ),
                ),
            ).sort((first, second) =>
                String(first).localeCompare(
                    String(second),
                ),
            );
        }, [admins]);

    const filteredAdmins = useMemo(() => {
        const normalizedSearch =
            searchTerm
                .trim()
                .toLowerCase();

        return admins.filter((admin) => {
            const override =
                adminOverrides[
                    admin.user_id
                    ];

            const person =
                override?.person ??
                admin.user?.person ??
                null;

            const email =
                override?.email ??
                admin.user?.email ??
                "";

            const phone =
                override?.phone ??
                admin.user?.phone ??
                "";

            const companyName =
                getCompanyName(
                    admin.company_id,
                );

            const fullName =
                getFullName(person);

            const matchesSearch =
                normalizedSearch.length ===
                0 ||
                admin.user_id
                    .toLowerCase()
                    .includes(
                        normalizedSearch,
                    ) ||
                fullName
                    .toLowerCase()
                    .includes(
                        normalizedSearch,
                    ) ||
                email
                    .toLowerCase()
                    .includes(
                        normalizedSearch,
                    ) ||
                phone
                    .toLowerCase()
                    .includes(
                        normalizedSearch,
                    ) ||
                companyName
                    .toLowerCase()
                    .includes(
                        normalizedSearch,
                    ) ||
                String(admin.role)
                    .toLowerCase()
                    .includes(
                        normalizedSearch,
                    );

            const matchesCompany =
                companyFilter === "all" ||
                admin.company_id ===
                companyFilter;

            const matchesRole =
                roleFilter === "all" ||
                admin.role === roleFilter;

            const isActive =
                override?.staffIsActive ??
                admin.is_active;

            const matchesStatus =
                statusFilter === "all" ||
                (
                    statusFilter ===
                    "active" &&
                    isActive
                ) ||
                (
                    statusFilter ===
                    "inactive" &&
                    !isActive
                );

            return (
                matchesSearch &&
                matchesCompany &&
                matchesRole &&
                matchesStatus
            );
        });
    }, [
        adminOverrides,
        admins,
        companyFilter,
        getCompanyName,
        roleFilter,
        searchTerm,
        statusFilter,
    ]);

    const totalPages = Math.max(
        1,
        Math.ceil(
            filteredAdmins.length /
            itemsPerPage,
        ),
    );

    const safeCurrentPage = Math.min(
        Math.max(currentPage, 1),
        totalPages,
    );

    const paginatedAdmins = useMemo(() => {
        const startIndex =
            (safeCurrentPage - 1) *
            itemsPerPage;

        return filteredAdmins.slice(
            startIndex,
            startIndex + itemsPerPage,
        );
    }, [
        filteredAdmins,
        itemsPerPage,
        safeCurrentPage,
    ]);

    const firstResult =
        filteredAdmins.length === 0
            ? 0
            : (
                safeCurrentPage - 1
            ) *
            itemsPerPage +
            1;

    const lastResult = Math.min(
        safeCurrentPage * itemsPerPage,
        filteredAdmins.length,
    );

    const hasActiveFilters =
        searchTerm.trim().length > 0 ||
        companyFilter !== "all" ||
        roleFilter !== "all" ||
        statusFilter !== "all";

    const isLoading =
        isCompaniesLoading ||
        isCompanyStaffLoading;

    const loadingError =
        errors.companies ??
        errors.companyStaff;

    const selectedCompanyName =
        selectedAdmin
            ? getCompanyName(
                selectedAdmin.company_id,
            )
            : "";

    function clearFilters() {
        setSearchTerm("");
        setCompanyFilter("all");
        setRoleFilter("all");
        setStatusFilter("all");
        setCurrentPage(1);
    }

    function handleSavedAdmin(
        result: SavedAdminResult,
    ) {
        setAdminOverrides((current) => ({
            ...current,

            [result.userId]: {
                email: result.email,
                phone: result.phone,

                accountIsActive:
                result.accountIsActive,

                staffIsActive:
                result.staffIsActive,

                person: result.person,
            },
        }));

        setSelectedAdmin(null);

        /*
         * The local override updates the row immediately.
         * Refreshing then replaces it with the latest API data.
         */
        refreshAllData();
    }

    function goToPreviousPage() {
        setCurrentPage(
            Math.max(
                1,
                safeCurrentPage - 1,
            ),
        );
    }

    function goToNextPage() {
        setCurrentPage(
            Math.min(
                totalPages,
                safeCurrentPage + 1,
            ),
        );
    }

    return (
        <>
            <div className="overflow-visible rounded-2xl border bg-card shadow-sm">
                <StickyFilterBar
                    ariaLabel="Company administrator search and filters"
                    className="rounded-t-2xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
                >
                <div className="rounded-[inherit] border-b bg-card p-4 sm:p-5">
                    <div className="flex flex-col gap-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                                <div className="flex items-center gap-2">
                                    <Users className="h-5 w-5 text-primary" />

                                    <h2 className="text-lg font-semibold">
                                        Company administrators
                                    </h2>
                                </div>

                                <p className="mt-1 text-sm text-muted-foreground">
                                    View, complete and manage
                                    administrator profiles.
                                </p>
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                                <button
                                    type="button"
                                    onClick={
                                        refreshAllData
                                    }
                                    disabled={isLoading}
                                    className="inline-flex h-9 items-center gap-2 rounded-lg border bg-background px-3 text-sm font-semibold transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    <RefreshCw
                                        className={`h-4 w-4 ${
                                            isLoading
                                                ? "animate-spin"
                                                : ""
                                        }`}
                                    />

                                    Refresh
                                </button>

                                <div className="w-fit rounded-full bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary">
                                    {
                                        filteredAdmins.length
                                    }{" "}
                                    {filteredAdmins.length ===
                                    1
                                        ? "administrator"
                                        : "administrators"}
                                </div>
                            </div>
                        </div>

                        {loadingError && (
                            <div className="flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300 sm:flex-row sm:items-center sm:justify-between">
                                <div className="flex items-start gap-2">
                                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />

                                    <div>
                                        <p className="font-semibold">
                                            Administrator data
                                            could not be loaded
                                        </p>

                                        <p className="mt-1">
                                            {loadingError}
                                        </p>
                                    </div>
                                </div>

                                <button
                                    type="button"
                                    onClick={
                                        refreshAllData
                                    }
                                    disabled={isLoading}
                                    className="h-9 rounded-lg border border-red-300 bg-background px-4 font-semibold transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-800 dark:hover:bg-red-950"
                                >
                                    Try again
                                </button>
                            </div>
                        )}

                        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                            <SuggestionSearch
                                value={searchTerm}
                                onValueChange={(value) => {
                                    setSearchTerm(value);
                                    setCurrentPage(1);
                                }}
                                suggestions={admins.map((admin) => {
                                    const override = adminOverrides[admin.user_id];
                                    const person = override?.person ?? admin.user?.person ?? null;
                                    const name = getFullName(person) || override?.email || admin.user?.email || override?.phone || admin.user?.phone || admin.user_id;
                                    return {
                                        value: name,
                                        label: name,
                                        description: `${getCompanyName(admin.company_id)} · ${formatRole(admin.role)}`,
                                        keywords: [
                                            admin.user_id,
                                            override?.email ?? admin.user?.email ?? "",
                                            override?.phone ?? admin.user?.phone ?? "",
                                            admin.company_id,
                                        ],
                                    };
                                })}
                                placeholder="Type a name, company, email or phone..."
                                suggestionLabel="Company administrators"
                                emptyMessage="No administrator matches that text."
                                wrapperClassName="md:col-span-2 xl:col-span-1"
                                className="h-10 rounded-lg"
                            />

                            <NativeSelect
                                value={companyFilter}
                                onChange={(event) => {
                                    setCompanyFilter(
                                        event.target.value,
                                    );

                                    setCurrentPage(1);
                                }}
                                disabled={
                                    isCompaniesLoading &&
                                    companies.length ===
                                    0
                                }
                                aria-label="Filter by company"
                                className="h-10 rounded-lg border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                <option value="all">
                                    {isCompaniesLoading &&
                                    companies.length === 0
                                        ? "Loading companies..."
                                        : "All companies"}
                                </option>

                                {availableCompanies.map(
                                    (company) => (
                                        <option
                                            key={company.id}
                                            value={company.id}
                                        >
                                            {company.name}
                                        </option>
                                    ),
                                )}
                            </NativeSelect>

                            <NativeSelect
                                value={roleFilter}
                                onChange={(event) => {
                                    setRoleFilter(
                                        event.target.value,
                                    );

                                    setCurrentPage(1);
                                }}
                                aria-label="Filter by role"
                                className="h-10 rounded-lg border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                            >
                                <option value="all">
                                    All roles
                                </option>

                                {availableRoles.map(
                                    (role) => (
                                        <option
                                            key={role}
                                            value={role}
                                        >
                                            {formatRole(
                                                role,
                                            )}
                                        </option>
                                    ),
                                )}
                            </NativeSelect>

                            <NativeSelect
                                value={statusFilter}
                                onChange={(event) => {
                                    setStatusFilter(
                                        event.target.value,
                                    );

                                    setCurrentPage(1);
                                }}
                                aria-label="Filter by status"
                                className="h-10 rounded-lg border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
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
                        </div>

                        {hasActiveFilters && (
                            <div>
                                <button
                                    type="button"
                                    onClick={clearFilters}
                                    className="text-sm font-medium text-primary hover:underline"
                                >
                                    Clear all filters
                                </button>
                            </div>
                        )}
                    </div>
                </div>
                </StickyFilterBar>

                <div className="overflow-x-auto rounded-b-2xl">
                    <table className="w-full min-w-[1000px] text-sm">
                        <thead className="bg-muted/70">
                        <tr>
                            <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                                Administrator
                            </th>

                            <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                                Company
                            </th>

                            <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                                Role
                            </th>

                            <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                                Status
                            </th>

                            <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                                Profile
                            </th>

                            <th className="px-4 py-3 text-right font-semibold text-muted-foreground">
                                Actions
                            </th>
                        </tr>
                        </thead>

                        <tbody>
                        {isCompanyStaffLoading &&
                        admins.length === 0 ? (
                            Array.from({
                                length: 6,
                            }).map((_, index) => (
                                <tr
                                    key={index}
                                    className="border-t"
                                >
                                    <td className="px-4 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className="h-10 w-10 animate-pulse rounded-xl bg-muted" />

                                            <div className="space-y-2">
                                                <div className="h-3 w-36 animate-pulse rounded bg-muted" />
                                                <div className="h-3 w-24 animate-pulse rounded bg-muted" />
                                            </div>
                                        </div>
                                    </td>

                                    <td className="px-4 py-4">
                                        <div className="h-3 w-32 animate-pulse rounded bg-muted" />
                                    </td>

                                    <td className="px-4 py-4">
                                        <div className="h-6 w-28 animate-pulse rounded bg-muted" />
                                    </td>

                                    <td className="px-4 py-4">
                                        <div className="h-6 w-20 animate-pulse rounded-full bg-muted" />
                                    </td>

                                    <td className="px-4 py-4">
                                        <div className="h-6 w-20 animate-pulse rounded-full bg-muted" />
                                    </td>

                                    <td className="px-4 py-4 text-right">
                                        <div className="ml-auto h-9 w-24 animate-pulse rounded-lg bg-muted" />
                                    </td>
                                </tr>
                            ))
                        ) : paginatedAdmins.length ===
                        0 ? (
                            <tr>
                                <td
                                    colSpan={6}
                                    className="px-4 py-14 text-center"
                                >
                                    <div className="mx-auto flex max-w-sm flex-col items-center">
                                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                                            <Users className="h-6 w-6 text-muted-foreground" />
                                        </div>

                                        <h3 className="mt-3 font-semibold">
                                            No administrators
                                            found
                                        </h3>

                                        <p className="mt-1 text-sm text-muted-foreground">
                                            No records match
                                            the selected
                                            filters.
                                        </p>

                                        {hasActiveFilters && (
                                            <button
                                                type="button"
                                                onClick={
                                                    clearFilters
                                                }
                                                className="mt-4 text-sm font-semibold text-primary hover:underline"
                                            >
                                                Clear filters
                                            </button>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            paginatedAdmins.map(
                                (admin) => {
                                    const override =
                                        adminOverrides[
                                            admin.user_id
                                            ];

                                    const person =
                                        override?.person ??
                                        admin.user
                                            ?.person ??
                                        null;

                                    const email =
                                        override?.email ??
                                        admin.user
                                            ?.email ??
                                        null;

                                    const phone =
                                        override?.phone ??
                                        admin.user
                                            ?.phone ??
                                        "";

                                    const isActive =
                                        override?.staffIsActive ??
                                        admin.is_active;

                                    const hasProfile =
                                        Boolean(person);

                                    const fullName =
                                        getFullName(
                                            person,
                                        );

                                    const companyName =
                                        getCompanyName(
                                            admin.company_id,
                                        );

                                    return (
                                        <tr
                                            key={admin.id}
                                            className="border-t transition-colors hover:bg-muted/40"
                                        >
                                            <td className="px-4 py-3">
                                                <div className="flex min-w-64 items-center gap-3">
                                                    <div
                                                        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${
                                                            hasProfile
                                                                ? "bg-primary/10 text-primary"
                                                                : "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
                                                        }`}
                                                    >
                                                        {getInitials(
                                                            person,
                                                        )}
                                                    </div>

                                                    <div className="min-w-0">
                                                        <p className="truncate font-semibold">
                                                            {hasProfile
                                                                ? fullName
                                                                : "Profile not available"}
                                                        </p>

                                                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                                                            {email && (
                                                                <span className="inline-flex items-center gap-1">
                                                                        <Mail className="h-3 w-3" />

                                                                    {
                                                                        email
                                                                    }
                                                                    </span>
                                                            )}

                                                            {phone && (
                                                                <span className="inline-flex items-center gap-1">
                                                                        <Phone className="h-3 w-3" />

                                                                    {
                                                                        phone
                                                                    }
                                                                    </span>
                                                            )}

                                                            {!email &&
                                                                !phone && (
                                                                    <span>
                                                                            User
                                                                            ID:{" "}
                                                                        {
                                                                            admin.user_id
                                                                        }
                                                                        </span>
                                                                )}
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>

                                            <td className="px-4 py-3">
                                                {isCompaniesLoading &&
                                                companyName ===
                                                "Unknown company" ? (
                                                    <span className="inline-flex items-center gap-2 text-muted-foreground">
                                                            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground" />

                                                            Loading
                                                            company...
                                                        </span>
                                                ) : errors.companies &&
                                                companyName ===
                                                "Unknown company" ? (
                                                    <span className="inline-flex items-center gap-1.5 text-red-600">
                                                            <AlertCircle className="h-4 w-4" />

                                                            Unable to
                                                            load company
                                                        </span>
                                                ) : (
                                                    <span className="font-medium text-foreground">
                                                            {
                                                                companyName
                                                            }
                                                        </span>
                                                )}
                                            </td>

                                            <td className="px-4 py-3">
                                                    <span className="inline-flex rounded-md bg-muted px-2.5 py-1 text-xs font-medium">
                                                        {formatRole(
                                                            admin.role,
                                                        )}
                                                    </span>
                                            </td>

                                            <td className="px-4 py-3">
                                                    <span
                                                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                                                            isActive
                                                                ? "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400"
                                                                : "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"
                                                        }`}
                                                    >
                                                        <span
                                                            className={`h-1.5 w-1.5 rounded-full ${
                                                                isActive
                                                                    ? "bg-green-500"
                                                                    : "bg-red-500"
                                                            }`}
                                                        />

                                                        {isActive
                                                            ? "Active"
                                                            : "Inactive"}
                                                    </span>
                                            </td>

                                            <td className="px-4 py-3">
                                                {hasProfile ? (
                                                    <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-1 text-xs font-medium text-green-700 dark:bg-green-950/40 dark:text-green-400">
                                                            <UserRound className="h-3.5 w-3.5" />

                                                            Complete
                                                        </span>
                                                ) : (
                                                    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                                                            <AlertCircle className="h-3.5 w-3.5" />

                                                            Missing
                                                        </span>
                                                )}
                                            </td>

                                            <td className="px-4 py-3 text-right">
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        setSelectedAdmin(
                                                            admin,
                                                        )
                                                    }
                                                    className={`inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold transition ${
                                                        hasProfile
                                                            ? "border bg-background text-foreground hover:bg-muted"
                                                            : "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90"
                                                    }`}
                                                >
                                                    <Edit3 className="h-4 w-4" />

                                                    Edit user
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                },
                            )
                        )}
                        </tbody>
                    </table>
                </div>

                <div className="flex flex-col gap-4 border-t px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
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
                                {
                                    filteredAdmins.length
                                }
                            </strong>
                        </span>

                        <div className="flex items-center gap-2">
                            <label htmlFor="items-per-page">
                                Rows:
                            </label>

                            <NativeSelect
                                id="items-per-page"
                                value={itemsPerPage}
                                onChange={(event) => {
                                    setItemsPerPage(
                                        Number(
                                            event.target
                                                .value,
                                        ),
                                    );

                                    setCurrentPage(1);
                                }}
                                className="h-8 rounded-md border bg-background px-2 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                            >
                                <option value={6}>
                                    6
                                </option>

                                <option value={12}>
                                    12
                                </option>

                                <option value={24}>
                                    24
                                </option>
                            </NativeSelect>
                        </div>
                    </div>

                    <div className="flex items-center justify-between gap-2 sm:justify-end">
                        <button
                            type="button"
                            onClick={
                                goToPreviousPage
                            }
                            disabled={
                                safeCurrentPage === 1
                            }
                            className="inline-flex h-9 items-center gap-1 rounded-lg border bg-background px-3 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            <ChevronLeft className="h-4 w-4" />
                            Previous
                        </button>

                        <span className="min-w-24 text-center text-sm text-muted-foreground">
                            Page{" "}
                            <strong className="text-foreground">
                                {safeCurrentPage}
                            </strong>{" "}
                            of{" "}
                            <strong className="text-foreground">
                                {totalPages}
                            </strong>
                        </span>

                        <button
                            type="button"
                            onClick={goToNextPage}
                            disabled={
                                safeCurrentPage >=
                                totalPages
                            }
                            className="inline-flex h-9 items-center gap-1 rounded-lg border bg-background px-3 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Next
                            <ChevronRight className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </div>

            {selectedAdmin && (
                <UserEditDialog
                    key={selectedAdmin.id}
                    admin={selectedAdmin}
                    companyName={
                        selectedCompanyName
                    }
                    open={Boolean(
                        selectedAdmin,
                    )}
                    onOpenChange={(isOpen) => {
                        if (!isOpen) {
                            setSelectedAdmin(
                                null,
                            );
                        }
                    }}
                    onSaved={
                        handleSavedAdmin
                    }
                />
            )}
        </>
    );
}