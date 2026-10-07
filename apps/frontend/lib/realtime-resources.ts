import type { DbCommitBatchDetail } from "@/lib/realtime-commit";

export type RealtimeResource =
    | "companies"
    | "companyStaff"
    | "branches"
    | "borrowers"
    | "loanRequests"
    | "loanOffers"
    | "marketplace"
    | "loans"
    | "payments"
    | "billing"
    | "loanProducts";


const TABLE_RESOURCES: Record<string, RealtimeResource[]> = {
    loan_companies: ["companies"],
    company_staff: ["companyStaff"],
    company_branches: ["branches"],

    borrowers: ["borrowers"],
    borrower_contacts: ["borrowers"],
    borrower_service_requests: ["borrowers"],
    company_borrower_accounts: ["borrowers", "loans"],

    loan_requests: ["loanRequests", "marketplace"],
    loan_offers: ["loanOffers", "marketplace"],
    marketplace_unlocks: ["marketplace", "payments"],

    client_company_loan: ["loans"],
    repayment_installments: ["loans", "payments"],
    loan_early_settlements: ["loans", "payments"],
    payment_allocations: ["loans", "payments"],
    loan_contracts: ["loans"],
    credit_committee_cases: ["loans"],
    underwriting_assessments: ["loans"],
    credit_committee_conditions: ["loans"],

    payment_transactions: ["payments", "loans"],
    loan_payment_operations: ["payments", "loans"],
    treasury_entries: ["payments"],
    branch_daily_ledgers: ["payments"],

    loan_products: ["loanProducts"],

    subscription_plans: ["billing"],
    company_subscriptions: ["billing"],
    subscription_invoices: ["billing"],
};

const SAFE_DELETE_RESOURCE: Record<string, RealtimeResource | undefined> = {
    borrowers: "borrowers",
    loan_requests: "loanRequests",
    loan_offers: "loanOffers",
    client_company_loan: "loans",
    payment_transactions: "payments",
    loan_products: "loanProducts",
};

const PREFIX_RESOURCES: Array<[string, RealtimeResource[]]> = [
    ["borrower_", ["borrowers"]],
    ["credit_committee_", ["loans"]],
    ["repayment_", ["loans", "payments"]],
    ["payment_", ["payments", "loans"]],
    ["treasury_", ["payments"]],
    ["reconciliation_", ["payments"]],
    ["subscription_", ["billing"]],
    ["loan_product", ["loanProducts"]],
];

const RESOURCE_ROUTE_HINTS: Record<RealtimeResource, string[]> = {
    companies: ["/superadmin", "/company/settings", "/companies"],
    companyStaff: ["/company/staff", "/company/hr", "/company/settings", "/superadmin"],
    branches: ["/company/branches", "/company/settings", "/superadmin"],
    borrowers: ["/borrower", "/company/borrowers", "/company/clients", "/company/dashboard"],
    loanRequests: ["/borrower", "/marketplace", "/loan-requests"],
    loanOffers: ["/marketplace", "/loan-requests", "/borrower"],
    marketplace: ["/marketplace", "/loan-requests", "/borrower"],
    loans: ["/loans", "/credit-committee", "/borrower", "/company/dashboard"],
    payments: ["/payments", "/treasury", "/accounting", "/reconciliation", "/loans", "/company/dashboard"],
    billing: ["/billing", "/subscriptions", "/company/settings", "/superadmin"],
    loanProducts: ["/loan-products", "/products", "/borrower", "/company/settings"],
};

const ALWAYS_DYNAMIC_ROUTE_HINTS = [
    "/company/dashboard",
    "/superadmin",
    "/company/operating",
    "/company/reports",
    "/company/analytics",
    "/company/management",
];

export function resourcesForTable(table: unknown): RealtimeResource[] {
    const normalized = String(table ?? "").trim().toLowerCase();
    if (!normalized || normalized === "*") {
        return [
            "companies",
            "companyStaff",
            "branches",
            "borrowers",
            "loanRequests",
            "loanOffers",
            "marketplace",
            "loans",
            "payments",
            "billing",
            "loanProducts",
        ];
    }

    const exact = TABLE_RESOURCES[normalized];
    if (exact) return exact;

    for (const [prefix, resources] of PREFIX_RESOURCES) {
        if (normalized.startsWith(prefix)) {
            return resources;
        }
    }

    return [];
}

export function resourcesForCommitBatch(
    detail: DbCommitBatchDetail | null | undefined,
): Set<RealtimeResource> {
    const resources = new Set<RealtimeResource>();
    for (const event of detail?.events ?? []) {
        for (const resource of resourcesForTable(event.table)) {
            resources.add(resource);
        }
    }
    return resources;
}

export function shouldRefreshRouteForCommit(
    pathname: string,
    detail: DbCommitBatchDetail | null | undefined,
): boolean {
    if (!detail?.count) return false;
    if (detail.events.some((event) => String(event.table ?? "") === "*")) {
        return true;
    }

    if (ALWAYS_DYNAMIC_ROUTE_HINTS.some((hint) => pathname.startsWith(hint))) {
        return true;
    }

    const resources = resourcesForCommitBatch(detail);
    if (resources.size === 0) {
        // Unknown tables are safer to refresh than silently leave stale.
        return true;
    }

    for (const resource of resources) {
        if (
            RESOURCE_ROUTE_HINTS[resource].some(
                (hint) => pathname.includes(hint),
            )
        ) {
            return true;
        }
    }

    return false;
}

export function deletedEntityIdsByResource(
    detail: DbCommitBatchDetail | null | undefined,
): Partial<Record<RealtimeResource, Set<string>>> {
    const result: Partial<Record<RealtimeResource, Set<string>>> = {};

    for (const event of detail?.events ?? []) {
        if (String(event.action ?? "") !== "deleted") continue;
        const entityId = String(event.entity_id ?? "").trim();
        if (!entityId) continue;

        const resource = SAFE_DELETE_RESOURCE[
            String(event.table ?? "").trim().toLowerCase()
        ];
        if (!resource) continue;

        const ids = result[resource] ?? new Set<string>();
        ids.add(entityId);
        result[resource] = ids;
    }

    return result;
}
