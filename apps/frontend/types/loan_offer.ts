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

export type QuickLoanAffordability = {
    decision: "pass" | "fail" | string;
    passed: boolean;
    monthly_income: string;
    living_expenses: string;
    existing_debt_repayments: string;
    proposed_installment: string;
    maximum_affordable_installment: string;
    affordability_headroom: string;
    disposable_after_installment: string;
    dti_percent: string;
    reasons: Array<{ severity: string; code: string; message: string }>;
};

export type QuickLoanAffordabilityPreviewResult = {
    affordability: QuickLoanAffordability;
    monthly_repayment: number;
    total_repayment: number;
    calculation_method: InterestMethod;
    own_risk_override_available: boolean;
    own_risk_override_roles: string[];
};

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
    approve_at_own_risk?: boolean;
    own_risk_reason?: string | null;
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
    approve_at_own_risk?: boolean;
    own_risk_reason?: string | null;
}
