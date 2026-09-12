"use client";

import {
    useCallback,
    useMemo,
    useState,
} from "react";
import { toast } from "@/utils/toast";


import {
    useAppDispatch,
} from "@/store/hooks";

import {
    activateCompany,
    approveCompany,
    deactivateCompany,
    deleteCompany,
    rejectCompany,
    type LoanCompany,
    type LoanCompanyPayload,
    updateCompany,
} from "@/store/slices/companiesSlice";

import type {
    CompanyAction,
    CompanyActivityFilter,
    CompanyPageStats,
    CompanyStatusFilter,
    DistrictAnalytics,
} from "../_types/company-page";

import {
    countByCompany,
    exportCompaniesToCsv,
    getPercentage,
    getRequestError,
    getTimestamp,
    normalizeCompanyStatus,
} from "../_lib/company-utils";
import {useAppData} from "@/provider/appDataProvider";

const DEFAULT_PAGE_SIZE = 8;

export function useCompaniesPage() {
    const dispatch = useAppDispatch();

    const {
        companies,
        branches,
        companyStaff,

        isCompaniesLoading,
        isBranchesLoading,
        isCompanyStaffLoading,

        errors,
        refreshAllData,
    } = useAppData();

    const [searchTerm, setSearchTerm] =
        useState("");

    const [
        statusFilter,
        setStatusFilter,
    ] = useState<CompanyStatusFilter>("all");

    const [
        activityFilter,
        setActivityFilter,
    ] = useState<CompanyActivityFilter>("all");

    const [
        districtFilter,
        setDistrictFilter,
    ] = useState("all");

    const [
        currentPage,
        setCurrentPage,
    ] = useState(1);

    const [
        itemsPerPage,
        setItemsPerPage,
    ] = useState(DEFAULT_PAGE_SIZE);

    const [
        workingCompanyId,
        setWorkingCompanyId,
    ] = useState<string | null>(null);

    const [
        companyToDelete,
        setCompanyToDelete,
    ] = useState<LoanCompany | null>(null);

    const [
        companyToEdit,
        setCompanyToEdit,
    ] = useState<LoanCompany | null>(null);

    const [
        companyForOwnerAccess,
        setCompanyForOwnerAccess,
    ] = useState<LoanCompany | null>(null);

    const [
        isSavingCompany,
        setIsSavingCompany,
    ] = useState(false);

    const isLoading =
        isCompaniesLoading ||
        isBranchesLoading ||
        isCompanyStaffLoading;

    const pageError = useMemo(() => {
        return (
            errors.companies ??
            errors.branches ??
            errors.companyStaff ??
            null
        );
    }, [
        errors.branches,
        errors.companies,
        errors.companyStaff,
    ]);

    const branchesByCompany = useMemo(
        () => countByCompany(branches),
        [branches],
    );

    const activeBranchesByCompany = useMemo(
        () =>
            countByCompany(
                branches,
                (branch) => branch.is_active,
            ),
        [branches],
    );

    const staffByCompany = useMemo(
        () => countByCompany(companyStaff),
        [companyStaff],
    );

    const activeStaffByCompany = useMemo(
        () =>
            countByCompany(
                companyStaff,
                (staff) => staff.is_active,
            ),
        [companyStaff],
    );

    const stats = useMemo<CompanyPageStats>(() => {
        const approvedCompanies =
            companies.filter(
                (company) =>
                    normalizeCompanyStatus(
                        company.status,
                    ) === "approved",
            ).length;

        const pendingCompanies =
            companies.filter(
                (company) =>
                    normalizeCompanyStatus(
                        company.status,
                    ) === "pending",
            ).length;

        const rejectedCompanies =
            companies.filter(
                (company) =>
                    normalizeCompanyStatus(
                        company.status,
                    ) === "rejected",
            ).length;

        const activeCompanies =
            companies.filter(
                (company) => company.is_active,
            ).length;

        const activeBranches =
            branches.filter(
                (branch) => branch.is_active,
            ).length;

        const activeStaff =
            companyStaff.filter(
                (staff) => staff.is_active,
            ).length;

        const thirtyDaysAgo = new Date();

        thirtyDaysAgo.setDate(
            thirtyDaysAgo.getDate() - 30,
        );

        const newCompaniesLast30Days =
            companies.filter(
                (company) =>
                    getTimestamp(
                        company.created_at,
                    ) >= thirtyDaysAgo.getTime(),
            ).length;

        return {
            totalCompanies: companies.length,

            approvedCompanies,
            pendingCompanies,
            rejectedCompanies,

            activeCompanies,
            inactiveCompanies:
                companies.length - activeCompanies,

            totalBranches: branches.length,
            activeBranches,

            totalStaff: companyStaff.length,
            activeStaff,

            newCompaniesLast30Days,

            approvalRate: getPercentage(
                approvedCompanies,
                companies.length,
            ),

            activeRate: getPercentage(
                activeCompanies,
                companies.length,
            ),

            averageBranches:
                companies.length > 0
                    ? branches.length /
                    companies.length
                    : 0,

            averageStaff:
                companies.length > 0
                    ? companyStaff.length /
                    companies.length
                    : 0,
        };
    }, [
        branches,
        companies,
        companyStaff,
    ]);

    const districtOptions = useMemo(() => {
        return Array.from(
            new Set(
                companies
                    .map(
                        (company) =>
                            company.district?.trim(),
                    )
                    .filter(
                        (
                            district,
                        ): district is string =>
                            Boolean(district),
                    ),
            ),
        ).sort((first, second) =>
            first.localeCompare(second),
        );
    }, [companies]);

    const districtAnalytics =
        useMemo<DistrictAnalytics[]>(() => {
            const result =
                new Map<
                    string,
                    DistrictAnalytics
                >();

            for (const company of companies) {
                const district =
                    company.district?.trim() ||
                    "Not specified";

                const current =
                    result.get(district) ?? {
                        district,
                        companies: 0,
                        activeCompanies: 0,
                        branches: 0,
                        staff: 0,
                    };

                current.companies += 1;

                if (company.is_active) {
                    current.activeCompanies += 1;
                }

                current.branches +=
                    branchesByCompany.get(
                        company.id,
                    ) ?? 0;

                current.staff +=
                    staffByCompany.get(
                        company.id,
                    ) ?? 0;

                result.set(
                    district,
                    current,
                );
            }

            return Array.from(
                result.values(),
            ).sort(
                (first, second) =>
                    second.companies -
                    first.companies,
            );
        }, [
            branchesByCompany,
            companies,
            staffByCompany,
        ]);

    const recentCompanies = useMemo(() => {
        return [...companies]
            .sort(
                (first, second) =>
                    getTimestamp(
                        second.created_at,
                    ) -
                    getTimestamp(
                        first.created_at,
                    ),
            )
            .slice(0, 6);
    }, [companies]);

    const filteredCompanies = useMemo(() => {
        const search =
            searchTerm.trim().toLowerCase();

        return [...companies]
            .filter((company) => {
                const searchableValues = [
                    company.name,
                    company.email,
                    company.phone,
                    company.website,
                    company.address,
                    company.district,
                    company.status,
                    company.registration_number,
                    company.license_number,
                ].map((value) =>
                    String(value ?? "")
                        .toLowerCase(),
                );

                const matchesSearch =
                    search.length === 0 ||
                    searchableValues.some(
                        (value) =>
                            value.includes(search),
                    );

                const matchesStatus =
                    statusFilter === "all" ||
                    normalizeCompanyStatus(
                        company.status,
                    ) === statusFilter;

                const matchesActivity =
                    activityFilter === "all" ||
                    (
                        activityFilter ===
                        "active" &&
                        company.is_active
                    ) ||
                    (
                        activityFilter ===
                        "inactive" &&
                        !company.is_active
                    );

                const matchesDistrict =
                    districtFilter === "all" ||
                    company.district ===
                    districtFilter;

                return (
                    matchesSearch &&
                    matchesStatus &&
                    matchesActivity &&
                    matchesDistrict
                );
            })
            .sort(
                (first, second) =>
                    getTimestamp(
                        second.created_at,
                    ) -
                    getTimestamp(
                        first.created_at,
                    ),
            );
    }, [
        activityFilter,
        companies,
        districtFilter,
        searchTerm,
        statusFilter,
    ]);

    const totalPages = Math.max(
        1,
        Math.ceil(
            filteredCompanies.length /
            itemsPerPage,
        ),
    );

    const safeCurrentPage = Math.min(
        Math.max(currentPage, 1),
        totalPages,
    );

    const paginatedCompanies = useMemo(() => {
        const start =
            (
                safeCurrentPage - 1
            ) * itemsPerPage;

        return filteredCompanies.slice(
            start,
            start + itemsPerPage,
        );
    }, [
        filteredCompanies,
        itemsPerPage,
        safeCurrentPage,
    ]);

    const firstResult =
        filteredCompanies.length === 0
            ? 0
            : (
                safeCurrentPage - 1
            ) *
            itemsPerPage +
            1;

    const lastResult = Math.min(
        safeCurrentPage * itemsPerPage,
        filteredCompanies.length,
    );

    const hasFilters =
        searchTerm.trim().length > 0 ||
        statusFilter !== "all" ||
        activityFilter !== "all" ||
        districtFilter !== "all";

    const updateSearch = useCallback(
        (value: string) => {
            setSearchTerm(value);
            setCurrentPage(1);
        },
        [],
    );

    const updateStatusFilter = useCallback(
        (value: CompanyStatusFilter) => {
            setStatusFilter(value);
            setCurrentPage(1);
        },
        [],
    );

    const updateActivityFilter =
        useCallback(
            (
                value:
                CompanyActivityFilter,
            ) => {
                setActivityFilter(value);
                setCurrentPage(1);
            },
            [],
        );

    const updateDistrictFilter =
        useCallback((value: string) => {
            setDistrictFilter(value);
            setCurrentPage(1);
        }, []);

    const updateItemsPerPage =
        useCallback((value: number) => {
            setItemsPerPage(value);
            setCurrentPage(1);
        }, []);

    const resetFilters = useCallback(() => {
        setSearchTerm("");
        setStatusFilter("all");
        setActivityFilter("all");
        setDistrictFilter("all");
        setCurrentPage(1);
    }, []);

    const copyCompanyId = useCallback(
        async (company: LoanCompany) => {
            try {
                await navigator.clipboard.writeText(
                    company.id,
                );

                toast.success(
                    "Company ID copied",
                );
            } catch {
                toast.error(
                    "Company ID could not be copied",
                );
            }
        },
        [],
    );

    const runCompanyAction = useCallback(
        async (
            company: LoanCompany,
            action: CompanyAction,
        ) => {
            setWorkingCompanyId(company.id);

            try {
                switch (action) {
                    case "approve":
                        await dispatch(
                            approveCompany(company.id),
                        ).unwrap();
                        break;

                    case "reject":
                        await dispatch(
                            rejectCompany(company.id),
                        ).unwrap();
                        break;

                    case "activate":
                        await dispatch(
                            activateCompany(company.id),
                        ).unwrap();
                        break;

                    case "deactivate":
                        await dispatch(
                            deactivateCompany(
                                company.id,
                            ),
                        ).unwrap();
                        break;
                }

                toast.success(
                    `${company.name} updated successfully`,
                );

                refreshAllData();
            } catch (error: unknown) {
                toast.error(
                    getRequestError(error),
                );
            } finally {
                setWorkingCompanyId(null);
            }
        },
        [
            dispatch,
            refreshAllData,
        ],
    );

    const confirmDeleteCompany =
        useCallback(async () => {
            if (!companyToDelete) {
                return;
            }

            const company =
                companyToDelete;

            setWorkingCompanyId(company.id);

            try {
                await dispatch(
                    deleteCompany(company.id),
                ).unwrap();

                toast.success(
                    `${company.name} deleted successfully`,
                );

                setCompanyToDelete(null);
                refreshAllData();
            } catch (error: unknown) {
                toast.error(
                    getRequestError(error),
                );
            } finally {
                setWorkingCompanyId(null);
            }
        }, [
            companyToDelete,
            dispatch,
            refreshAllData,
        ]);

    const exportCompanies =
        useCallback(() => {
            exportCompaniesToCsv({
                companies:
                filteredCompanies,
                branchesByCompany,
                staffByCompany,
            });
        }, [
            branchesByCompany,
            filteredCompanies,
            staffByCompany,
        ]);

    const saveCompany = useCallback(
        async (payload: Partial<LoanCompanyPayload>) => {
            if (!companyToEdit || isSavingCompany) return;
            setIsSavingCompany(true);
            try {
                await dispatch(
                    updateCompany({
                        id: companyToEdit.id,
                        payload,
                    }),
                ).unwrap();
                toast.success(`${companyToEdit.name} updated successfully`);
                setCompanyToEdit(null);
                await refreshAllData();
            } catch (error: unknown) {
                toast.error(getRequestError(error));
                throw error;
            } finally {
                setIsSavingCompany(false);
            }
        },
        [companyToEdit, dispatch, isSavingCompany, refreshAllData],
    );

    return {
        overview: {
            stats,
            districtAnalytics,
            recentCompanies,

            branchesByCompany,
            staffByCompany,

            isLoading,
            pageError,

            onRefresh: refreshAllData,
            onExport: exportCompanies,
        },

        table: {
            companies:
            paginatedCompanies,

            allCompanies:
            companies,

            filteredCount:
            filteredCompanies.length,

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
            isLoading:
            isCompaniesLoading,

            workingCompanyId,

            firstResult,
            lastResult,
            currentPage:
            safeCurrentPage,
            totalPages,
            itemsPerPage,

            onSearchChange:
            updateSearch,

            onStatusFilterChange:
            updateStatusFilter,

            onActivityFilterChange:
            updateActivityFilter,

            onDistrictFilterChange:
            updateDistrictFilter,

            onItemsPerPageChange:
            updateItemsPerPage,

            onPreviousPage: () =>
                setCurrentPage(
                    Math.max(
                        1,
                        safeCurrentPage - 1,
                    ),
                ),

            onNextPage: () =>
                setCurrentPage(
                    Math.min(
                        totalPages,
                        safeCurrentPage + 1,
                    ),
                ),

            onResetFilters:
            resetFilters,

            onRunAction:
            runCompanyAction,

            onCopyCompanyId:
            copyCompanyId,

            onRequestDelete:
            setCompanyToDelete,

            onRequestEdit:
            setCompanyToEdit,

            onManageOwnerAccess:
            setCompanyForOwnerAccess,
        },

        editDialog: {
            company: companyToEdit,
            open: Boolean(companyToEdit),
            isSaving: isSavingCompany,
            onOpenChange: (open: boolean) => {
                if (!open && !isSavingCompany) setCompanyToEdit(null);
            },
            onSave: saveCompany,
        },

        ownerAccessDialog: {
            company: companyForOwnerAccess,
            open: Boolean(companyForOwnerAccess),
            onOpenChange: (open: boolean) => {
                if (!open) setCompanyForOwnerAccess(null);
            },
        },

        deleteDialog: {
            company:
            companyToDelete,

            isDeleting:
                Boolean(
                    companyToDelete &&
                    workingCompanyId ===
                    companyToDelete.id,
                ),

            onOpenChange: (
                open: boolean,
            ) => {
                if (
                    !open &&
                    !workingCompanyId
                ) {
                    setCompanyToDelete(null);
                }
            },

            onConfirm:
            confirmDeleteCompany,
        },
    };
}

export type CompaniesPageModel =
    ReturnType<
        typeof useCompaniesPage
    >;
