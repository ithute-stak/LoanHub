export type CompanyAction =
    | "approve"
    | "reject"
    | "activate"
    | "deactivate";

export type CompanyStatusFilter =
    | "all"
    | "pending"
    | "approved"
    | "rejected";

export type CompanyActivityFilter =
    | "all"
    | "active"
    | "inactive";

export type CompanyPageStats = {
    totalCompanies: number;
    approvedCompanies: number;
    pendingCompanies: number;
    rejectedCompanies: number;

    activeCompanies: number;
    inactiveCompanies: number;

    totalBranches: number;
    activeBranches: number;

    totalStaff: number;
    activeStaff: number;

    newCompaniesLast30Days: number;

    approvalRate: number;
    activeRate: number;

    averageBranches: number;
    averageStaff: number;
};

export type DistrictAnalytics = {
    district: string;
    companies: number;
    activeCompanies: number;
    branches: number;
    staff: number;
};