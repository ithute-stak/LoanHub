import type { AuthUser, UserRole } from "@/types/auth";
import type { Gender, MaritalStatus, Person } from "@/types/person";

export type AccountMembership = {
    id: string;
    company_id: string;
    company_name: string;
    branch_id: string | null;
    branch_name: string | null;
    role: UserRole;
    is_primary: boolean;
    is_active: boolean;
};

export type AccountSecurity = {
    active_sessions: number;
    last_seen_at: string | null;
    account_created_at: string;
    account_updated_at: string;
    is_active: boolean;
    is_verified: boolean;
    is_impersonated: boolean;
    can_manage_security: boolean;
};

export type AccountOverview = {
    user: AuthUser;
    memberships: AccountMembership[];
    security: AccountSecurity;
};

export type AccountContactUpdate = {
    email?: string | null;
    phone?: string;
    current_password: string;
};

export type AccountProfileUpdate = {
    first_name?: string | null;
    middle_name?: string | null;
    last_name?: string | null;
    gender?: Gender | null;
    date_of_birth?: string | null;
    national_id?: string | null;
    passport_number?: string | null;
    marital_status?: MaritalStatus | null;
    nationality?: string | null;
    district?: string | null;
    town_or_village?: string | null;
    physical_address?: string | null;
};

export type ChangePasswordPayload = {
    current_password: string;
    new_password: string;
    confirm_password: string;
};

export type ChangePasswordResult = {
    message: string;
    requires_reauthentication: boolean;
};

export type AccountSession = {
    id: string;
    created_at: string;
    expires_at: string;
    is_current: boolean;
    is_active: boolean;
    status: "active" | "expired" | "revoked" | string;
};

export type AccountSessionAction = {
    message: string;
    revoked_count: number;
};

export type AccountActivity = {
    id: string;
    action: string;
    description: string | null;
    status: string;
    severity: string;
    ip_address: string | null;
    user_agent: string | null;
    changed_fields: string[];
    event_data: Record<string, unknown>;
    created_at: string;
};

export type AccountProfileResult = Person;
