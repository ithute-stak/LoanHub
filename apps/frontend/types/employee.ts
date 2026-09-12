import type { Person } from "@/types/person";
import type { UserRole } from "@/types/auth";

export type EmployeeProfile = {
    id: string;
    staff_id: string;
    company_id: string;
    branch_id: string | null;
    reports_to_staff_id: string | null;
    employee_number: string;
    job_title: string | null;
    department: string | null;
    employment_type: string;
    employment_status: string;
    hire_date: string | null;
    probation_end_date: string | null;
    termination_date: string | null;
    base_salary: string | number | null;
    currency: string;
    skills: string[];
    target_config: Record<string, unknown>;
    bank_name: string | null;
    bank_account_name: string | null;
    bank_account_number: string | null;
    notes: string | null;
    is_manager: boolean;
    created_at: string;
    updated_at: string;
};

export type Employee = {
    staff_id: string;
    company_id: string;
    branch_id: string | null;
    role: UserRole;
    is_active: boolean;
    user: {
        id: string;
        email: string | null;
        phone: string;
        role: UserRole;
        is_active: boolean;
        person: Person | null;
    };
    profile: EmployeeProfile | null;
};

export type EmployeeProfilePayload = {
    employee_number: string;
    job_title: string | null;
    department: string | null;
    employment_type: string;
    employment_status: string;
    hire_date: string | null;
    probation_end_date: string | null;
    termination_date: string | null;
    reports_to_staff_id: string | null;
    base_salary: number | null;
    currency: string;
    skills: string[];
    target_config: Record<string, unknown>;
    bank_name?: string | null;
    bank_account_name?: string | null;
    bank_account_number?: string | null;
    notes: string | null;
    is_manager: boolean;
};

export type PerformanceGoal = {
    id: string;
    employee_id: string;
    company_id: string;
    branch_id: string | null;
    created_by_user_id: string | null;
    title: string;
    description: string | null;
    category: string;
    target_value: string | number;
    current_value: string | number;
    unit: string;
    weight: string | number;
    period_start: string;
    period_end: string;
    status: string;
    completed_at: string | null;
    created_at: string;
    updated_at: string;
};

export type PerformanceGoalPayload = {
    title: string;
    description?: string | null;
    category: string;
    target_value: number;
    current_value: number;
    unit: string;
    weight: number;
    period_start: string;
    period_end: string;
    status: string;
};

export type PerformanceReviewPayload = {
    period_start: string;
    period_end: string;
    overall_score: number;
    rating: string;
    status: string;
    strengths?: string | null;
    improvements?: string | null;
    comments?: string | null;
    metrics: Record<string, unknown>;
};
