import type { Branch } from "@/types/branch";

export type BranchStatusFilter =
    | "all"
    | "active"
    | "inactive";

export type BranchSort =
    | "newest"
    | "oldest"
    | "name_asc"
    | "name_desc"
    | "company_asc"
    | "district_asc";

export type BranchPageSize =
    | 6
    | 12
    | 24
    | 48
    | "all";

export type BranchDialogMode =
    | "create"
    | "edit";

export type BranchPageStats = {
    totalBranches: number;
    activeBranches: number;
    inactiveBranches: number;
    companiesWithBranches: number;
    companiesWithoutBranches: number;
    districtsCovered: number;
    assignedStaff: number;
    branchesWithStaff: number;
    branchesWithoutStaff: number;
    newBranchesLast30Days: number;
    activeRate: number;
    averageBranchesPerCompany: number;
    averageStaffPerBranch: number;
};

export type DistrictBranchAnalytics = {
    district: string;
    branches: number;
    activeBranches: number;
    companies: number;
    staff: number;
};

export type CompanyBranchAnalytics = {
    companyId: string;
    companyName: string;
    branches: number;
    activeBranches: number;
    staff: number;
};

export type BranchDialogState = {
    mode: BranchDialogMode;
    branch: Branch | null;
};
