import type { AuthUser, UserRole } from "@/types/auth";
import type { Person } from "@/types/person";

export type { UserRole };

export interface User {
    id: string;
    email: string | null;
    phone: string;
    role: UserRole;
    is_active: boolean;
    is_verified: boolean;
    created_at: string;
    person: Person | null;
}

export type UserAuthResponse = AuthUser;

export interface CreateUserRequest {
    email?: string | null;
    phone: string;
    role: UserRole;
    is_active: boolean;
    is_verified: boolean;
    password_hash: string;
}
