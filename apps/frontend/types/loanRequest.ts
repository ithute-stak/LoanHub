export enum LoanRequestStatus {
    DRAFT = "draft",
    SUBMITTED = "submitted",
    OPEN = "open",
    UNDER_REVIEW = "under_review",
    OFFERED = "offered",
    ACCEPTED = "accepted",
    CANCELLED = "cancelled",
    EXPIRED = "expired",
}

export interface LoanRequest {
    id: string;
    borrower_id: string;
    requested_amount: number;
    preferred_term_months: number | null;
    loan_purpose: string | null;
    status: LoanRequestStatus;
    visible_to_lenders: boolean;
    allow_lenders_to_call: boolean;
    selected_offer_id: string | null;
    origination_channel: string;
    captured_by_user_id: string | null;
    service_fee_amount: number;
    service_fee_currency: string;
    service_fee_status: "not_required" | "required" | "processing" | "paid" | "failed";
    service_fee_payment_id: string | null;
    submitted_at: string | null;
    expires_at: string | null;
    accepted_at: string | null;
    created_at: string;
}

export interface LoanRequestCreatePayload {
    requested_amount: number;
    preferred_term_months?: number | null;
    loan_purpose?: string | null;
    visible_to_lenders?: boolean;
    allow_lenders_to_call?: boolean;
}

export interface LoanRequestUpdatePayload {
    requested_amount?: number;
    preferred_term_months?: number | null;
    loan_purpose?: string | null;
    visible_to_lenders?: boolean;
    allow_lenders_to_call?: boolean;
    status?: LoanRequestStatus;
}
