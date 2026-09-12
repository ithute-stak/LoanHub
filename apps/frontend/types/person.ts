export type Gender = "male" | "female" | "other";

export type MaritalStatus =
    | "single"
    | "married"
    | "divorced"
    | "widowed";

export interface Person {
    id: string;
    user_id: string;
    first_name: string;
    middle_name: string | null;
    last_name: string;
    full_name: string;
    gender: Gender | null;
    date_of_birth: string | null;
    national_id: string | null;
    passport_number: string | null;
    marital_status: MaritalStatus | null;
    nationality: string | null;
    district: string | null;
    town_or_village: string | null;
    physical_address: string | null;
    created_at: string;
    updated_at: string;
}

export interface CreatePersonPayload {
    user_id: string;
    first_name: string;
    middle_name?: string | null;
    last_name: string;
    gender?: Gender | null;
    date_of_birth?: string | null;
    national_id?: string | null;
    passport_number?: string | null;
    marital_status?: MaritalStatus | null;
    nationality?: string | null;
    district?: string | null;
    town_or_village?: string | null;
    physical_address?: string | null;
}

export type UpdatePersonPayload = Partial<Omit<CreatePersonPayload, "user_id">>;
