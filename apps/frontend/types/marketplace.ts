import type { LoanRequestStatus } from "@/types/loanRequest";
import type { PaymentMethod } from "@/types/expenseManagement";

export type MarketplaceBorrowerSummary = {
    district: string | null;
    employment_status: string;
    monthly_income_band: string | null;
    has_existing_loans: boolean;
};

export type MarketplaceRequestCard = {
    id: string;
    requested_amount: number;
    preferred_term_months: number | null;
    loan_purpose: string | null;
    status: LoanRequestStatus;
    allow_lenders_to_call: boolean;
    created_at: string;
    expires_at: string | null;
    is_unlocked: boolean;
    unlock_price: number;
    borrower: MarketplaceBorrowerSummary;
};

export type MarketplaceEvidenceDocument = {
    id: string;
    category: string;
    original_name: string;
    mime_type: string;
    size_bytes: number;
    created_at: string;
};

export type MarketplaceBorrowerDetail = {
    borrower_id: string;
    user_id: string;
    full_name: string;
    phone: string;
    email: string | null;
    gender: string | null;
    date_of_birth: string | null;
    national_id: string | null;
    passport_number: string | null;
    district: string | null;
    town_or_village: string | null;
    physical_address: string | null;
    employment_status: string;
    employment_type: string | null;
    employer_name: string | null;
    job_title: string | null;
    employment_start_date: string | null;
    monthly_income: number | null;
    net_monthly_income: number | null;
    other_monthly_income: number;
    other_income_source: string | null;
    monthly_living_expenses: number;
    monthly_debt_repayments: number;
    dependants: number;
    residential_status: string | null;
    years_at_address: number | null;
    existing_loan_total: number;
    bank_name: string | null;
    account_holder_name: string | null;
    account_last_four: string | null;
    consent_to_credit_checks: boolean;
    consent_to_share_documents: boolean;
    total_monthly_income: number;
    total_monthly_commitments: number;
    disposable_monthly_income: number;
    debt_to_income_percent: number | null;
    profile_completeness: number;
    missing_requirements: string[];
    evidence_documents: MarketplaceEvidenceDocument[];
};

export type MarketplaceRequestDetail = MarketplaceRequestCard & {
    borrower_detail: MarketplaceBorrowerDetail | null;
};

export type UnlockStatus = "pending" | "unlocked" | "failed" | "revoked";

export type MarketplaceUnlock = {
    id: string;
    company_id: string;
    loan_request_id: string;
    payment_transaction_id: string | null;
    unlocked_by_user_id: string | null;
    price_paid: number;
    status: UnlockStatus;
    unlocked_at: string | null;
    expires_at: string | null;
    created_at: string;
};

export type UnlockMarketplacePayload = {
    payment_method: PaymentMethod;
    proof_reference?: string | null;
    proof_url?: string | null;
    proof_notes?: string | null;
};
