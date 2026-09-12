import type { UserRole } from "@/types/auth";

export type PlatformStaffAccount = {
    id: string;
    user_id: string;
    email: string | null;
    phone: string;
    first_name: string;
    middle_name: string | null;
    last_name: string;
    full_name: string;
    role: UserRole;
    job_title: string;
    department: string | null;
    permissions: string[];
    is_active: boolean;
    created_at: string;
    updated_at: string;
};

export type PlatformStaffAccountPayload = {
    email: string | null;
    phone: string;
    first_name: string;
    middle_name: string | null;
    last_name: string;
    role: UserRole;
    job_title: string;
    department: string | null;
    permissions: string[];
    is_active: boolean;
};

export type PlatformStaffAccountCreatePayload = PlatformStaffAccountPayload & {
    password: string;
};
