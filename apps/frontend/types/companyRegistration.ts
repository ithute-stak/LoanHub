import type { Gender, MaritalStatus } from "@/types/person";

export type InstitutionType =
    | "loan_company"
    | "commercial_bank"
    | "microfinance_institution"
    | "financial_cooperative"
    | "development_finance_institution"
    | "government_lending_program";

export type CompanyOwnerRegistrationPayload = {
    institution_type?: InstitutionType;
    company_name: string;
    registration_number?: string | null;
    license_number?: string | null;
    company_phone: string;
    company_email?: string | null;
    website?: string | null;
    address?: string | null;
    district?: string | null;
    owner_email?: string | null;
    owner_phone: string;
    password: string;
    first_name: string;
    middle_name?: string | null;
    last_name: string;
    gender?: Gender | null;
    date_of_birth?: string | null;
    national_id?: string | null;
    passport_number?: string | null;
    marital_status?: MaritalStatus | null;
    nationality?: string | null;
    town_or_village?: string | null;
    physical_address?: string | null;
};

export type CompanyOwnerRegistrationResponse = {
    company_id: string;
    institution_type: InstitutionType;
    owner_user_id: string;
    staff_membership_id: string;
    status: string;
    message: string;
};
