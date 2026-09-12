import type { Person } from "@/types/person";
import type { UserRole } from "@/types/auth";
import type { EmployerGroupCreate } from "@/types/employerGroup";

export type EmploymentStatus =
    | "employed"
    | "unemployed"
    | "self_employed"
    | "student"
    | "pensioner";

export interface Borrower {
    id: string;
    user_id: string;
    employment_status: EmploymentStatus;
    employment_type: string | null;
    employer_name: string | null;
    employer_group_id: string | null;
    income_day: number | null;
    job_title: string | null;
    employment_start_date: string | null;
    monthly_income: string | number | null;
    net_monthly_income: string | number | null;
    other_monthly_income: string | number;
    other_income_source: string | null;
    salary_date: string | null;
    monthly_living_expenses: string | number;
    monthly_debt_repayments: string | number;
    dependants: number;
    residential_status: string | null;
    years_at_address: number | null;
    has_existing_loans: boolean;
    existing_loan_total: string | number;
    bank_name: string | null;
    account_holder_name: string | null;
    account_last_four: string | null;
    consent_to_share_profile: boolean;
    consent_to_share_documents: boolean;
    consent_to_credit_checks: boolean;
    created_at: string;
    updated_at: string;
    person?: Person | null;
}

export interface CreateBorrowerPayload {
    email: string;
    phone: string;
    password_hash: string;
    first_name: string;
    middle_name: string;
    last_name: string;
    gender: "male" | "female" | "other";
    date_of_birth: string;
    national_id: string;
    passport_number: string;
    marital_status: "single" | "married" | "divorced" | "widowed";
    nationality: string;
    district: string;
    town_or_village: string;
    physical_address: string;
    employment_status: EmploymentStatus;
    employer_name: string | null;
    employer_group_id: string | null;
    new_employer_group: EmployerGroupCreate | null;
    income_day: number | null;
    job_title: string;
    monthly_income: number;
    salary_date: string;
    has_existing_loans: boolean;
    existing_loan_total: number;
    consent_to_share_profile: boolean;
    consent_to_credit_checks: boolean;
}

export interface UpdateBorrowerPayload {
    employment_status?: EmploymentStatus;
    employment_type?: string | null;
    employer_name?: string | null;
    employer_group_id?: string | null;
    income_day?: number | null;
    job_title?: string | null;
    employment_start_date?: string | null;
    monthly_income?: number | null;
    net_monthly_income?: number | null;
    other_monthly_income?: number;
    other_income_source?: string | null;
    salary_date?: string | null;
    monthly_living_expenses?: number;
    monthly_debt_repayments?: number;
    dependants?: number;
    residential_status?: string | null;
    years_at_address?: number | null;
    has_existing_loans?: boolean;
    existing_loan_total?: number;
    bank_name?: string | null;
    account_holder_name?: string | null;
    account_last_four?: string | null;
    consent_to_share_profile?: boolean;
    consent_to_share_documents?: boolean;
    consent_to_credit_checks?: boolean;
}

export interface BorrowerCreateResponse {
    user_id: string;
    person_id: string;
    borrower_id: string;
    email: string | null;
    phone: string;
    role: UserRole;
    first_name: string;
    last_name: string;
    district: string | null;
    created_at: string;
}
