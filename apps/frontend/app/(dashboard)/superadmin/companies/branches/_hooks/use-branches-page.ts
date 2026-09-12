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
    activateBranchThunk,
    createBranchThunk,
    deactivateBranchThunk,
    deleteBranchThunk,
    updateBranchThunk,
} from "@/store/features/thunks/branchThunks";

import type {
    Branch,
    BranchCreatePayload,
} from "@/types/branch";

import type {
    BranchDialogState,
    BranchPageSize,
    BranchPageStats,
    BranchSort,
    BranchStatusFilter,
    CompanyBranchAnalytics,
    DistrictBranchAnalytics,
} from "../_types/branch-page";

import {
    exportBranchesToCsv,
    getPercentage,
    getRequestError,
    getTimestamp,
} from "../_lib/branch-utils";
import {useAppData} from "@/provider/appDataProvider";

const DEFAULT_PAGE_SIZE: BranchPageSize = 12;

export function useBranchesPage() {
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
        getCompanyName,
    } = useAppData();

    const [searchTerm, setSearchTerm] =
        useState("");

    const [
        statusFilter,
        setStatusFilter,
    ] = useState<BranchStatusFilter>("all");

    const [
        companyFilter,
        setCompanyFilter,
    ] = useState("all");

    const [
        districtFilter,
        setDistrictFilter,
    ] = useState("all");

    const [
        sortBy,
        setSortBy,
    ] = useState<BranchSort>("newest");

    const [
        currentPage,
        setCurrentPage,
    ] = useState(1);

    const [
        pageSize,
        setPageSize,
    ] = useState<BranchPageSize>(
        DEFAULT_PAGE_SIZE,
    );

    const [
        formDialog,
        setFormDialog,
    ] = useState<BranchDialogState | null>(
        null,
    );

    const [
        branchToView,
        setBranchToView,
    ] = useState<Branch | null>(null);

    const [
        branchToDelete,
        setBranchToDelete,
    ] = useState<Branch | null>(null);

    const [
        actionBranchId,
        setActionBranchId,
    ] = useState<string | null>(null);

    const isLoading =
        isCompaniesLoading ||
        isBranchesLoading ||
        isCompanyStaffLoading;

    const pageError =
        errors.branches ??
        errors.companies ??
        errors.companyStaff ??
        null;

    const companyMap = useMemo(() => {
        return new Map(
            companies.map((company) => [
                company.id,
                company,
            ]),
        );
    }, [companies]);

    const staffByBranch = useMemo(() => {
        const result =
            new Map<string, number>();

        for (const staff of companyStaff) {
            if (!staff.branch_id) {
                continue;
            }

            result.set(
                staff.branch_id,
                (
                    result.get(
                        staff.branch_id,
                    ) ?? 0
                ) + 1,
            );
        }

        return result;
    }, [companyStaff]);

    const activeStaffByBranch =
        useMemo(() => {
            const result =
                new Map<string, number>();

            for (const staff of companyStaff) {
                if (
                    !staff.branch_id ||
                    !staff.is_active
                ) {
                    continue;
                }

                result.set(
                    staff.branch_id,
                    (
                        result.get(
                            staff.branch_id,
                        ) ?? 0
                    ) + 1,
                );
            }

            return result;
        }, [companyStaff]);

    const districtOptions = useMemo(() => {
        return Array.from(
            new Set(
                branches
                    .map(
                        (branch) =>
                            branch.district?.trim(),
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
    }, [branches]);

    const stats = useMemo<BranchPageStats>(() => {
        const activeBranches =
            branches.filter(
                (branch) =>
                    branch.is_active,
            ).length;

        const companiesWithBranches =
            new Set(
                branches.map(
                    (branch) =>
                        branch.company_id,
                ),
            ).size;

        const districtsCovered =
            new Set(
                branches
                    .map(
                        (branch) =>
                            branch.district?.trim(),
                    )
                    .filter(Boolean),
            ).size;

        const branchesWithStaff =
            branches.filter(
                (branch) =>
                    (
                        staffByBranch.get(
                            branch.id,
                        ) ?? 0
                    ) > 0,
            ).length;

        let assignedStaff = 0;
        for (const count of staffByBranch.values()) {
            assignedStaff += Number(count);
        }

        const thirtyDaysAgo =
            new Date();

        thirtyDaysAgo.setDate(
            thirtyDaysAgo.getDate() - 30,
        );

        const newBranchesLast30Days =
            branches.filter(
                (branch) =>
                    getTimestamp(
                        branch.created_at,
                    ) >=
                    thirtyDaysAgo.getTime(),
            ).length;

        return {
            totalBranches:
                branches.length,

            activeBranches,

            inactiveBranches:
                branches.length -
                activeBranches,

            companiesWithBranches,

            companiesWithoutBranches:
                Math.max(
                    0,
                    companies.length -
                        companiesWithBranches,
                ),

            districtsCovered,

            assignedStaff,

            branchesWithStaff,

            branchesWithoutStaff:
                branches.length -
                branchesWithStaff,

            newBranchesLast30Days,

            activeRate: getPercentage(
                activeBranches,
                branches.length,
            ),

            averageBranchesPerCompany:
                companiesWithBranches > 0
                    ? branches.length /
                      companiesWithBranches
                    : 0,

            averageStaffPerBranch:
                branches.length > 0
                    ? assignedStaff /
                      branches.length
                    : 0,
        };
    }, [
        branches,
        companies.length,
        staffByBranch,
    ]);

    const districtAnalytics =
        useMemo<DistrictBranchAnalytics[]>(
            () => {
                const result =
                    new Map<
                        string,
                        DistrictBranchAnalytics
                    >();

                const companyIdsByDistrict =
                    new Map<
                        string,
                        Set<string>
                    >();

                for (const branch of branches) {
                    const district =
                        branch.district?.trim() ||
                        "Not specified";

                    const current =
                        result.get(
                            district,
                        ) ?? {
                            district,
                            branches: 0,
                            activeBranches: 0,
                            companies: 0,
                            staff: 0,
                        };

                    current.branches += 1;

                    if (branch.is_active) {
                        current.activeBranches +=
                            1;
                    }

                    current.staff +=
                        staffByBranch.get(
                            branch.id,
                        ) ?? 0;

                    result.set(
                        district,
                        current,
                    );

                    const districtCompanies =
                        companyIdsByDistrict.get(
                            district,
                        ) ??
                        new Set<string>();

                    districtCompanies.add(
                        branch.company_id,
                    );

                    companyIdsByDistrict.set(
                        district,
                        districtCompanies,
                    );
                }

                for (
                    const [
                        district,
                        item,
                    ] of result
                ) {
                    item.companies =
                        companyIdsByDistrict.get(
                            district,
                        )?.size ?? 0;
                }

                return Array.from(
                    result.values(),
                ).sort(
                    (first, second) =>
                        second.branches -
                        first.branches,
                );
            },
            [
                branches,
                staffByBranch,
            ],
        );

    const companyAnalytics =
        useMemo<CompanyBranchAnalytics[]>(
            () => {
                return companies
                    .map((company) => {
                        const companyBranches =
                            branches.filter(
                                (branch) =>
                                    branch.company_id ===
                                    company.id,
                            );

                        return {
                            companyId:
                                company.id,

                            companyName:
                                company.name,

                            branches:
                                companyBranches.length,

                            activeBranches:
                                companyBranches.filter(
                                    (branch) =>
                                        branch.is_active,
                                ).length,

                            staff:
                                companyBranches.reduce(
                                    (
                                        total,
                                        branch,
                                    ) =>
                                        total +
                                        (
                                            staffByBranch.get(
                                                branch.id,
                                            ) ?? 0
                                        ),
                                    0,
                                ),
                        };
                    })
                    .filter(
                        (item) =>
                            item.branches > 0,
                    )
                    .sort(
                        (first, second) =>
                            second.branches -
                            first.branches,
                    );
            },
            [
                branches,
                companies,
                staffByBranch,
            ],
        );

    const recentBranches = useMemo(() => {
        return [...branches]
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
    }, [branches]);

    const filteredBranches = useMemo(() => {
        const search =
            searchTerm
                .trim()
                .toLowerCase();

        const result = branches.filter(
            (branch) => {
                const companyName =
                    getCompanyName(
                        branch.company_id,
                    );

                const values = [
                    branch.name,
                    branch.district,
                    branch.town,
                    branch.address,
                    branch.phone,
                    branch.email,
                    companyName,
                ].map((value) =>
                    String(value ?? "")
                        .toLowerCase(),
                );

                const matchesSearch =
                    search.length === 0 ||
                    values.some((value) =>
                        value.includes(search),
                    );

                const matchesStatus =
                    statusFilter === "all" ||
                    (
                        statusFilter ===
                            "active" &&
                        branch.is_active
                    ) ||
                    (
                        statusFilter ===
                            "inactive" &&
                        !branch.is_active
                    );

                const matchesCompany =
                    companyFilter === "all" ||
                    branch.company_id ===
                        companyFilter;

                const matchesDistrict =
                    districtFilter === "all" ||
                    branch.district ===
                        districtFilter;

                return (
                    matchesSearch &&
                    matchesStatus &&
                    matchesCompany &&
                    matchesDistrict
                );
            },
        );

        result.sort((first, second) => {
            switch (sortBy) {
                case "oldest":
                    return (
                        getTimestamp(
                            first.created_at,
                        ) -
                        getTimestamp(
                            second.created_at,
                        )
                    );

                case "name_asc":
                    return first.name.localeCompare(
                        second.name,
                    );

                case "name_desc":
                    return second.name.localeCompare(
                        first.name,
                    );

                case "company_asc":
                    return getCompanyName(
                        first.company_id,
                    ).localeCompare(
                        getCompanyName(
                            second.company_id,
                        ),
                    );

                case "district_asc":
                    return first.district.localeCompare(
                        second.district,
                    );

                case "newest":
                default:
                    return (
                        getTimestamp(
                            second.created_at,
                        ) -
                        getTimestamp(
                            first.created_at,
                        )
                    );
            }
        });

        return result;
    }, [
        branches,
        companyFilter,
        districtFilter,
        getCompanyName,
        searchTerm,
        sortBy,
        statusFilter,
    ]);

    const totalPages =
        pageSize === "all"
            ? 1
            : Math.max(
                  1,
                  Math.ceil(
                      filteredBranches.length /
                          pageSize,
                  ),
              );

    const safeCurrentPage = Math.min(
        Math.max(currentPage, 1),
        totalPages,
    );

    const paginatedBranches =
        useMemo(() => {
            if (pageSize === "all") {
                return filteredBranches;
            }

            const start =
                (
                    safeCurrentPage - 1
                ) * pageSize;

            return filteredBranches.slice(
                start,
                start + pageSize,
            );
        }, [
            filteredBranches,
            pageSize,
            safeCurrentPage,
        ]);

    const firstResult =
        filteredBranches.length === 0
            ? 0
            : pageSize === "all"
              ? 1
              : (
                    safeCurrentPage - 1
                ) *
                    pageSize +
                1;

    const lastResult =
        pageSize === "all"
            ? filteredBranches.length
            : Math.min(
                  safeCurrentPage *
                      pageSize,
                  filteredBranches.length,
              );

    const hasFilters =
        searchTerm.trim().length > 0 ||
        statusFilter !== "all" ||
        companyFilter !== "all" ||
        districtFilter !== "all" ||
        sortBy !== "newest";

    const updateSearch =
        useCallback((value: string) => {
            setSearchTerm(value);
            setCurrentPage(1);
        }, []);

    const updateStatusFilter =
        useCallback(
            (
                value:
                    BranchStatusFilter,
            ) => {
                setStatusFilter(value);
                setCurrentPage(1);
            },
            [],
        );

    const updateCompanyFilter =
        useCallback((value: string) => {
            setCompanyFilter(value);
            setCurrentPage(1);
        }, []);

    const updateDistrictFilter =
        useCallback((value: string) => {
            setDistrictFilter(value);
            setCurrentPage(1);
        }, []);

    const updateSort =
        useCallback(
            (value: BranchSort) => {
                setSortBy(value);
                setCurrentPage(1);
            },
            [],
        );

    const updatePageSize =
        useCallback(
            (
                value:
                    BranchPageSize,
            ) => {
                setPageSize(value);
                setCurrentPage(1);
            },
            [],
        );

    const resetFilters = useCallback(() => {
        setSearchTerm("");
        setStatusFilter("all");
        setCompanyFilter("all");
        setDistrictFilter("all");
        setSortBy("newest");
        setCurrentPage(1);
    }, []);

    const openCreateDialog =
        useCallback(() => {
            setFormDialog({
                mode: "create",
                branch: null,
            });
        }, []);

    const openEditDialog =
        useCallback((branch: Branch) => {
            setFormDialog({
                mode: "edit",
                branch,
            });
        }, []);

    const closeFormDialog =
        useCallback(() => {
            setFormDialog(null);
        }, []);

    const saveBranch = useCallback(
        async ({
            mode,
            branch,
            payload,
        }: {
            mode: "create" | "edit";
            branch: Branch | null;
            payload: BranchCreatePayload;
        }) => {
            try {
                if (mode === "create") {
                    await dispatch(
                        createBranchThunk(
                            payload,
                        ),
                    ).unwrap();

                    toast.success(
                        "Branch created successfully",
                    );
                } else {
                    if (!branch) {
                        throw new Error(
                            "No branch was selected for editing",
                        );
                    }

                    await dispatch(
                        updateBranchThunk({
                            id: branch.id,
                            data: payload,
                        }),
                    ).unwrap();

                    toast.success(
                        "Branch updated successfully",
                    );
                }

                setFormDialog(null);
                refreshAllData();
            } catch (error: unknown) {
                throw new Error(
                    getRequestError(
                        error,
                        mode === "create"
                            ? "Failed to create branch"
                            : "Failed to update branch",
                    ),
                );
            }
        },
        [
            dispatch,
            refreshAllData,
        ],
    );

    const toggleBranchStatus =
        useCallback(
            async (branch: Branch) => {
                setActionBranchId(
                    branch.id,
                );

                try {
                    if (branch.is_active) {
                        await dispatch(
                            deactivateBranchThunk(
                                branch.id,
                            ),
                        ).unwrap();

                        toast.success(
                            `${branch.name} deactivated`,
                        );
                    } else {
                        await dispatch(
                            activateBranchThunk(
                                branch.id,
                            ),
                        ).unwrap();

                        toast.success(
                            `${branch.name} activated`,
                        );
                    }

                    refreshAllData();
                } catch (error: unknown) {
                    toast.error(
                        getRequestError(
                            error,
                            "Failed to update branch status",
                        ),
                    );
                } finally {
                    setActionBranchId(
                        null,
                    );
                }
            },
            [
                dispatch,
                refreshAllData,
            ],
        );

    const confirmDelete =
        useCallback(async () => {
            if (!branchToDelete) {
                return;
            }

            const branch =
                branchToDelete;

            setActionBranchId(branch.id);

            try {
                await dispatch(
                    deleteBranchThunk(
                        branch.id,
                    ),
                ).unwrap();

                toast.success(
                    `${branch.name} deleted successfully`,
                );

                setBranchToDelete(null);
                refreshAllData();
            } catch (error: unknown) {
                toast.error(
                    getRequestError(
                        error,
                        "Failed to delete branch",
                    ),
                );
            } finally {
                setActionBranchId(null);
            }
        }, [
            branchToDelete,
            dispatch,
            refreshAllData,
        ]);

    const exportBranches =
        useCallback(() => {
            exportBranchesToCsv({
                branches:
                    filteredBranches,

                getCompanyName: (
                    companyId,
                ) =>
                    getCompanyName(
                        companyId,
                    ),

                staffByBranch,
            });
        }, [
            filteredBranches,
            getCompanyName,
            staffByBranch,
        ]);

    return {
        header: {
            totalBranches:
                stats.totalBranches,

            isLoading,
            onRefresh:
                refreshAllData,

            onExport:
                exportBranches,

            onCreate:
                openCreateDialog,
        },

        overview: {
            stats,
            districtAnalytics,
            companyAnalytics,
            recentBranches,
            getCompanyName,
            staffByBranch,
            pageError,
        },

        table: {
            branches:
                paginatedBranches,

            allBranches:
                branches,

            companies,

            districtOptions,

            searchTerm,
            statusFilter,
            companyFilter,
            districtFilter,
            sortBy,
            pageSize,

            filteredCount:
                filteredBranches.length,

            firstResult,
            lastResult,
            currentPage:
                safeCurrentPage,
            totalPages,

            hasFilters,
            isLoading:
                isBranchesLoading,

            actionBranchId,

            staffByBranch,
            activeStaffByBranch,

            getCompanyName,

            onSearchChange:
                updateSearch,

            onStatusFilterChange:
                updateStatusFilter,

            onCompanyFilterChange:
                updateCompanyFilter,

            onDistrictFilterChange:
                updateDistrictFilter,

            onSortChange:
                updateSort,

            onPageSizeChange:
                updatePageSize,

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

            onView:
                setBranchToView,

            onEdit:
                openEditDialog,

            onToggleStatus:
                toggleBranchStatus,

            onDelete:
                setBranchToDelete,
        },

        formDialog: {
            state: formDialog,

            companies,

            onOpenChange: (
                open: boolean,
            ) => {
                if (!open) {
                    closeFormDialog();
                }
            },

            onSubmit:
                saveBranch,
        },

        viewDialog: {
            branch:
                branchToView,

            company:
                branchToView
                    ? companyMap.get(
                          branchToView.company_id,
                      ) ?? null
                    : null,

            staffCount:
                branchToView
                    ? staffByBranch.get(
                          branchToView.id,
                      ) ?? 0
                    : 0,

            activeStaffCount:
                branchToView
                    ? activeStaffByBranch.get(
                          branchToView.id,
                      ) ?? 0
                    : 0,

            onOpenChange: (
                open: boolean,
            ) => {
                if (!open) {
                    setBranchToView(null);
                }
            },

            onEdit: (
                branch: Branch,
            ) => {
                setBranchToView(null);
                openEditDialog(branch);
            },
        },

        deleteDialog: {
            branch:
                branchToDelete,

            companyName:
                branchToDelete
                    ? getCompanyName(
                          branchToDelete.company_id,
                      )
                    : "",

            isDeleting:
                Boolean(
                    branchToDelete &&
                        actionBranchId ===
                            branchToDelete.id,
                ),

            onOpenChange: (
                open: boolean,
            ) => {
                if (
                    !open &&
                    !actionBranchId
                ) {
                    setBranchToDelete(null);
                }
            },

            onConfirm:
                confirmDelete,
        },
    };
}

export type BranchesPageModel =
    ReturnType<
        typeof useBranchesPage
    >;
