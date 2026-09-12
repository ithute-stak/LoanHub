import type { BankAccountInput } from "@/types/origination";
import type { EmployerGroupCreate } from "@/types/employerGroup";

export type ExternalDebtFrequency = "weekly" | "fortnightly" | "monthly" | "quarterly" | "custom";
export type ExternalDebtStatus = "active" | "settled" | "defaulted" | "restructured" | "written_off" | "unknown";

export type CompanyClientExternalDebtInput = {
    creditor: string;
    account_reference?: string | null;
    debt_type?: string;
    started_on?: string | null;
    original_amount: number;
    current_balance: number;
    installment_amount: number;
    installment_frequency: ExternalDebtFrequency;
    total_installments?: number | null;
    installments_paid?: number;
    remaining_installments?: number | null;
    next_due_date?: string | null;
    status?: ExternalDebtStatus;
    source?: string;
    is_verified?: boolean;
    notes?: string | null;
};

export type CompanyClientExternalDebtEvent = {
    id: string;
    event_type: string;
    event_at: string;
    amount: number | null;
    balance_after: number | null;
    remaining_installments_after: number | null;
    notes: string | null;
    recorded_by_user_id: string | null;
};

export type CompanyClientExternalDebt = CompanyClientExternalDebtInput & {
    id: string;
    company_id: string;
    borrower_id: string;
    debt_type: string;
    monthly_installment: number;
    installments_paid: number;
    status: ExternalDebtStatus;
    source: string;
    is_verified: boolean;
    last_reviewed_at: string | null;
    created_at: string;
    updated_at: string;
    events: CompanyClientExternalDebtEvent[];
};

export type CompanyClient = {
    id: string;
    account_reference: string;
    company_id: string;
    branch_id: string | null;
    borrower_id: string;
    user_id: string;
    opened_by_user_id: string | null;
    source: string;
    status: string;
    opening_fee_amount: number;
    opening_fee_currency: string;
    opening_fee_status: string;
    opening_fee_payment_id: string | null;
    first_name: string;
    middle_name: string | null;
    last_name: string;
    full_name: string;
    email: string | null;
    phone: string;
    gender: string | null;
    date_of_birth: string | null;
    marital_status: string | null;
    nationality: string | null;
    national_id: string | null;
    passport_number: string | null;
    district: string | null;
    town_or_village: string | null;
    physical_address: string | null;
    employment_status: string;
    employer_name: string | null;
    employer_group_id: string | null;
    employer_group_code: string | null;
    income_day: number | null;
    job_title: string | null;
    monthly_income: number | null;
    has_existing_loans: boolean;
    existing_loan_total: number;
    consent_to_credit_checks: boolean;
    is_login_active: boolean;
    salary_date: string | null;
    has_bank_account: boolean;
    bank_account_holder: string | null;
    bank_name: string | null;
    bank_branch_name: string | null;
    bank_branch_code: string | null;
    bank_account_last4: string | null;
    masked_bank_account: string | null;
    bank_account_type: string | null;
    bank_currency: string | null;
    bank_verification_status: string | null;
    salary_account: boolean;
    next_salary_pay_date: string | null;
    loan_count: number;
    active_loan_count: number;
    loan_statuses: string[];
    outstanding_balance: number;
    next_due_date: string | null;
    next_due_amount: number | null;
    overdue_installment_count: number;
    recent_loan_id: string | null;
    recent_loan_reference: string | null;
    recent_loan_status: string | null;
    recent_loan_created_at: string | null;
    case_entry_count: number;
    comment_count: number;
    legal_action_count: number;
    open_legal_action_count: number;
    latest_case_entry_at: string | null;
    latest_case_entry_kind: string | null;
    created_at: string;
    updated_at: string;
};

export type AssistedCompanyClientCreate = {
    branch_id?: string | null;
    email?: string | null;
    phone: string;
    temporary_password?: string | null;
    first_name: string;
    middle_name?: string | null;
    last_name: string;
    gender: "male" | "female" | "other";
    date_of_birth: string;
    national_id?: string | null;
    passport_number?: string | null;
    marital_status?: "single" | "married" | "divorced" | "widowed" | null;
    nationality?: string | null;
    district: string;
    town_or_village?: string | null;
    physical_address?: string | null;
    employment_status: "employed" | "self_employed" | "unemployed" | "student" | "pensioner";
    employer_name?: string | null;
    employer_group_id?: string | null;
    new_employer_group?: EmployerGroupCreate | null;
    income_day?: number | null;
    job_title?: string | null;
    monthly_income?: number | null;
    salary_date?: string | null;
    has_existing_loans: boolean;
    existing_loan_total: number;
    consent_to_share_profile: boolean;
    consent_to_credit_checks: boolean;
    bank_account?: BankAccountInput | null;
    external_debts: CompanyClientExternalDebtInput[];
};


export type CompanyClientExistingLoanCheck = {
    national_id: string;
    borrower_found: boolean;
    already_company_client: boolean;
    company_client_account_id: string | null;
    has_existing_loans: boolean;
    total_loan_count: number;
    active_loan_count: number;
    completed_loan_count: number;
    defaulted_loan_count: number;
    overdue_loan_count: number;
    lender_count: number;
    loanhub_outstanding_total: number;
    declared_existing_loan_total: number;
    external_debt_count: number;
    external_debt_balance_total: number;
    external_debt_monthly_commitment: number;
    external_debts: CompanyClientExternalDebt[];
    existing_loan_total: number;
    lifetime_principal_total: number;
    lifetime_paid_total: number;
    latest_loan_at: string | null;
    checked_at: string;
};

export type CompanyClientPaymentRating = {
    score: number | null;
    grade: string;
    label: string;
    has_history: boolean;
    explanation: string;
    total_due_installments: number;
    paid_installments: number;
    on_time_installments: number;
    late_installments: number;
    overdue_installments: number;
    undated_paid_installments: number;
    on_time_rate: number;
    completion_rate: number;
    average_days_late: number;
    total_due_amount: number;
    total_paid_amount: number;
    last_payment_at: string | null;
};

export type CompanyClientProfileStats = {
    total_loans: number;
    active_loans: number;
    completed_loans: number;
    defaulted_loans: number;
    overdue_loans: number;
    lifetime_principal_total: number;
    lifetime_paid_total: number;
    outstanding_balance: number;
    document_count: number;
    comment_count: number;
    legal_action_count: number;
    open_legal_action_count: number;
};

export type CompanyClientProfileLoan = {
    id: string;
    loan_reference: string;
    status: string;
    risk_level: string;
    principal_amount: number;
    total_repayable: number;
    amount_paid: number;
    balance: number;
    installment_amount: number;
    repayment_type: string;
    repayment_period: number;
    approved_at: string | null;
    disbursed_at: string | null;
    first_payment_due: string | null;
    maturity_date: string | null;
    is_overdue: boolean;
    overdue_installment_count: number;
};

export type CompanyClientProfileDocument = {
    id: string;
    reference: string;
    document_type: string;
    original_name: string;
    mime_type: string;
    size_bytes: number;
    description: string | null;
    is_confidential: boolean;
    created_at: string;
};

export type CompanyClientProfilePermissions = {
    can_edit_profile: boolean;
    can_edit_contact: boolean;
    can_edit_banking: boolean;
    can_edit_account_status: boolean;
    can_request_national_id_change: boolean;
    can_approve_national_id_change: boolean;
};

export type CompanyClientNationalIdChangeRequest = {
    id: string;
    reference: string;
    company_id: string;
    branch_id: string | null;
    company_borrower_account_id: string;
    borrower_id: string;
    current_national_id: string | null;
    proposed_national_id: string;
    reason: string;
    status: string;
    borrower_approved_at: string | null;
    company_owner_approved_at: string | null;
    rejected_at: string | null;
    rejected_by_role: string | null;
    rejection_reason: string | null;
    applied_at: string | null;
    expires_at: string;
    created_at: string;
    updated_at: string;
};

export type CompanyClientProfileUpdate = {
    first_name?: string | null;
    middle_name?: string | null;
    last_name?: string | null;
    gender?: "male" | "female" | "other" | null;
    date_of_birth?: string | null;
    passport_number?: string | null;
    marital_status?: "single" | "married" | "divorced" | "widowed" | null;
    nationality?: string | null;
    district?: string | null;
    town_or_village?: string | null;
    physical_address?: string | null;
    email?: string | null;
    phone?: string | null;
    is_login_active?: boolean;
    account_status?: "active" | "inactive" | "suspended" | "closed";
    employment_status?: "employed" | "self_employed" | "unemployed" | "student" | "pensioner";
    employer_name?: string | null;
    job_title?: string | null;
    monthly_income?: number | null;
    salary_date?: string | null;
    bank_account?: {
        account_holder?: string | null;
        bank_name?: string | null;
        branch_name?: string | null;
        branch_code?: string | null;
        account_type?: string | null;
        currency?: string | null;
        account_number?: string | null;
        salary_account?: boolean;
    } | null;
};

export type CompanyClientProfile = {
    client: CompanyClient;
    stats: CompanyClientProfileStats;
    payment_rating: CompanyClientPaymentRating;
    permissions: CompanyClientProfilePermissions;
    latest_national_id_change_request: CompanyClientNationalIdChangeRequest | null;
    loans: CompanyClientProfileLoan[];
    external_debts: CompanyClientExternalDebt[];
    documents: CompanyClientProfileDocument[];
    profile_image: CompanyClientProfileDocument | null;
    recent_case_entries: CompanyClientCaseEntry[];
};

export type InternalClientLoanRequestCreate = {
    branch_id?: string | null;
    product_id?: string | null;
    requested_amount: number;
    term_count: number;
    repayment_type: "daily" | "weekly" | "monthly" | "custom";
    purpose?: string | null;
    installment_due_dates: string[];
};

export type InternalClientLoanRequest = {
    id: string;
    application_reference: string;
    company_id: string;
    branch_id: string | null;
    borrower_id: string;
    product_id: string | null;
    requested_amount: number;
    term_count: number;
    repayment_type: string;
    purpose: string | null;
    installment_due_dates: string[];
    channel: "internal_client_offer" | string;
    status: string;
    captured_by_user_id: string | null;
    submitted_at: string | null;
    created_at: string;
    updated_at: string;
};


export type CompanyClientLoanInsight = {
    loan_id: string;
    loan_reference: string;
    client_account_id: string;
    borrower_id: string;
    client_name: string;
    status: string;
    balance: number;
    installment_amount: number;
    due_date: string | null;
    due_amount: number | null;
    created_at: string;
};

export type CompanyClientPortfolioInsights = {
    due_within_days: number;
    soon_due: CompanyClientLoanInsight[];
    recent_loans: CompanyClientLoanInsight[];
};


export type CompanyClientCaseEntryType = "comment" | "legal_action";

export type CompanyClientCaseEntryCreate = {
    entry_type: CompanyClientCaseEntryType;
    category?: string;
    title?: string | null;
    body: string;
    status?: string | null;
    action_date?: string | null;
    reference_number?: string | null;
    amount?: number | null;
    currency?: string;
};

export type CompanyClientCaseEntry = {
    id: string;
    company_id: string;
    branch_id: string | null;
    company_borrower_account_id: string;
    borrower_id: string;
    created_by_user_id: string | null;
    created_by_name: string | null;
    entry_type: CompanyClientCaseEntryType;
    category: string;
    title: string | null;
    body: string;
    status: string;
    action_date: string | null;
    reference_number: string | null;
    amount: number | null;
    currency: string;
    created_at: string;
    updated_at: string;
};

export type CompanyClientCaseRecord = {
    client_account_id: string;
    borrower_id: string;
    branch_id: string | null;
    account_reference: string;
    client_name: string;
    phone: string;
    comment_count: number;
    legal_action_count: number;
    open_legal_action_count: number;
    latest_entry_at: string;
    latest_entry_kind: CompanyClientCaseEntryType;
    latest_entry_status: string;
    latest_entry_preview: string;
};
