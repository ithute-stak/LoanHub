import type { InterestMethod } from "@/types/loan";

export type OfferStatus =
    | "pending"
    | "accepted"
    | "rejected"
    | "withdrawn"
    | "expired";

export interface LoanOffer {
    id: string;
    loan_request_id: string;
    company_id: string;
    branch_id: string | null;
    offered_by_user_id: string;
    approved_amount: number;
    term_months: number;
    interest_rate_percent: number | null;
    processing_fee: number;
    monthly_repayment: number | null;
    total_repayment: number | null;
    notes: string | null;
    calculation_method: InterestMethod;
    calculation_breakdown: Record<string, unknown>;
    status: OfferStatus;
    created_at: string;
}

export interface LoanOfferCreatePayload {
    loan_request_id: string;
    branch_id?: string | null;
    approved_amount: number;
    term_months: number;
    interest_rate_percent?: number | null;
    processing_fee?: number;
    notes?: string | null;
    calculation_method: InterestMethod;
    installment_due_dates: string[];
}

export interface LoanOfferUpdatePayload {
    id: string;
    approved_amount?: number;
    term_months?: number;
    interest_rate_percent?: number | null;
    processing_fee?: number;
    notes?: string | null;
    calculation_method?: InterestMethod;
    installment_due_dates?: string[];
}
