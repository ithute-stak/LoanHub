import type { Person } from "@/types/person";
import type { UserRole } from "@/types/auth";

export type { UserRole };

export interface StaffUser {
    id: string;
    email: string | null;
    phone: string;
    role: UserRole;
    is_active: boolean;
    is_verified: boolean;
    created_at: string;
    person: Person | null;
}

export interface CompanyStaff {
    id: string;
    user_id: string;
    company_id: string;
    branch_id: string | null;
    role: UserRole;
    is_primary: boolean;
    is_active: boolean;
    created_at: string;
    updated_at: string;
    user: StaffUser;
}

export interface CreateCompanyStaffPayload {
    user_id: string;
    company_id: string;
    branch_id?: string | null;
    role: UserRole;
    is_primary?: boolean;
    is_active?: boolean;
}

export interface CreateCompanyStaffAccountPayload {
    email?: string | null;
    phone: string;
    password: string;
    first_name: string;
    middle_name?: string | null;
    last_name: string;
    gender?: "male" | "female" | "other" | null;
    date_of_birth?: string | null;
    national_id?: string | null;
    passport_number?: string | null;
    marital_status?: "single" | "married" | "divorced" | "widowed" | null;
    nationality?: string | null;
    district?: string | null;
    town_or_village?: string | null;
    physical_address?: string | null;
    branch_id?: string | null;
    role: UserRole;
    is_primary?: boolean;
    is_active?: boolean;
}

export interface UpdateCompanyStaffPayload {
    branch_id?: string | null;
    role?: UserRole;
    is_primary?: boolean;
    is_active?: boolean;
}
