import type { InterestMethod } from "@/types/loan";

export type LoanProduct = {
    id: string;
    company_id: string;
    name: string;
    description: string | null;
    min_amount: number;
    max_amount: number;
    min_term_months: number;
    max_term_months: number;
    interest_method: InterestMethod;
    interest_rate_percent: number;
    processing_fee: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
};

export type LoanProductCreatePayload = {
    company_id?: string | null;
    name: string;
    description?: string | null;
    min_amount: number;
    max_amount: number;
    min_term_months: number;
    max_term_months: number;
    interest_method?: InterestMethod;
    interest_rate_percent?: number;
    processing_fee?: number;
    is_active?: boolean;
};

export type LoanProductUpdatePayload = Partial<
    Omit<LoanProductCreatePayload, "company_id">
>;
