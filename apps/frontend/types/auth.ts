import type { Person } from "@/types/person";

export type UserRole =
    | "superadmin"
    | "platform_admin"
    | "platform_finance"
    | "platform_support"
    | "platform_auditor"
    | "platform_operations"
    | "platform_compliance"
    | "borrower"
    | "company_owner"
    | "company_admin"
    | "branch_manager"
    | "loan_officer"
    | "finance_officer"
    | "collections_officer"
    | "compliance_officer"
    | "auditor"
    | "customer_support"
    | "hr_manager"
    | "performance_manager"
    | "risk_manager"
    | "it_support"
    | "credit_analyst"
    | "aml_cft_officer"
    | "treasury_officer"
    | "data_protection_officer"
    | "regulatory_reporting_officer"
    | "operations_officer"
    | "information_security_officer";

export type CompanyMembership = {
    id: string;
    company_id: string;
    branch_id: string | null;
    role: UserRole;
    is_primary: boolean;
    is_active: boolean;
};

export type AuthUser = {
    id: string;
    email: string | null;
    phone: string;
    role: UserRole;
    is_active: boolean;
    is_verified: boolean;
    must_change_password?: boolean;
    created_at: string;
    person: Person | null;
    memberships: CompanyMembership[];
};

export type LoginRequest = {
    phone: string;
    password: string;
    otp?: string | null;
    recovery_code?: string | null;
    device_name?: string | null;
};

export type LoginResponse = {
    access_token: string;
    token_type: "bearer" | string;
    user: AuthUser;
};

export type RefreshResponse = {
    access_token: string;
    token_type: "bearer" | string;
};


export const PLATFORM_ROLES: readonly UserRole[] = [
    "superadmin",
    "platform_admin",
    "platform_finance",
    "platform_support",
    "platform_auditor",
    "platform_operations",
    "platform_compliance",
] as const;

export const PLATFORM_FINANCE_ROLES: readonly UserRole[] = [
    "superadmin",
    "platform_admin",
    "platform_finance",
    "platform_auditor",
    "platform_compliance",
] as const;

export function isPlatformRole(role: UserRole | null | undefined): boolean {
    return Boolean(role && PLATFORM_ROLES.includes(role));
}

export const COMPANY_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "loan_officer",
    "finance_officer",
    "collections_officer",
    "compliance_officer",
    "auditor",
    "customer_support",
    "hr_manager",
    "performance_manager",
    "risk_manager",
    "it_support",
    "credit_analyst",
    "aml_cft_officer",
    "treasury_officer",
    "data_protection_officer",
    "regulatory_reporting_officer",
    "operations_officer",
    "information_security_officer",
] as const;

export const COMPANY_MANAGEMENT_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
] as const;

export const LENDING_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "loan_officer",
    "credit_analyst",
] as const;

export const DIRECT_APPLICATION_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "loan_officer",
    "finance_officer",
    "risk_manager",
    "compliance_officer",
    "auditor",
    "credit_analyst",
    "aml_cft_officer",
    "regulatory_reporting_officer",
] as const;

export const FINANCE_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "finance_officer",
    "treasury_officer",
] as const;

export const COLLECTIONS_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "collections_officer",
] as const;

export const CASHIER_ROLES: readonly UserRole[] = Array.from(new Set([...FINANCE_ROLES, ...COLLECTIONS_ROLES]));


export const HR_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "hr_manager",
] as const;

export const PERFORMANCE_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "hr_manager",
    "performance_manager",
    "auditor",
] as const;

export const TRANSPARENCY_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "compliance_officer",
    "auditor",
    "hr_manager",
    "performance_manager",
    "risk_manager",
    "it_support",
    "credit_analyst",
    "aml_cft_officer",
    "treasury_officer",
    "data_protection_officer",
    "regulatory_reporting_officer",
    "operations_officer",
    "information_security_officer",
] as const;

export function isCompanyRole(role: UserRole | null | undefined): boolean {
    return Boolean(role && COMPANY_ROLES.includes(role));
}

export function hasRole(
    role: UserRole | null | undefined,
    allowedRoles: readonly UserRole[],
): boolean {
    return Boolean(role && allowedRoles.includes(role));
}



export const LENDING_OPERATIONS_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "loan_officer",
    "finance_officer",
    "collections_officer",
    "compliance_officer",
    "auditor",
    "risk_manager",
    "credit_analyst",
    "aml_cft_officer",
    "regulatory_reporting_officer",
    "operations_officer",
] as const;

export const TREASURY_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "finance_officer",
    "collections_officer",
    "compliance_officer",
    "auditor",
    "risk_manager",
    "treasury_officer",
    "operations_officer",
] as const;


export const ACCOUNTING_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "finance_officer",
    "auditor",
    "compliance_officer",
    "treasury_officer",
    "regulatory_reporting_officer",
] as const;

export const REPORTING_ROLES: readonly UserRole[] = [
    "company_owner",
    "company_admin",
    "branch_manager",
    "finance_officer",
    "compliance_officer",
    "auditor",
    "hr_manager",
    "performance_manager",
    "risk_manager",
    "credit_analyst",
    "aml_cft_officer",
    "treasury_officer",
    "data_protection_officer",
    "regulatory_reporting_officer",
    "operations_officer",
    "information_security_officer",
] as const;


export type ImpersonationTarget = {
    id: string;
    display_name: string;
    email: string | null;
    phone: string;
    role: UserRole;
    company_id: string | null;
    company_name: string | null;
    branch_id: string | null;
    branch_name: string | null;
};

export type ImpersonationRequest = {
    target_user_id: string;
    company_id?: string | null;
    reason: string;
    duration_minutes: number;
};

export type ImpersonationResponse = {
    access_token: string;
    token_type: string;
    expires_at: string;
    user: AuthUser;
    original_admin: AuthUser;
    company_id: string | null;
    reason: string;
};
