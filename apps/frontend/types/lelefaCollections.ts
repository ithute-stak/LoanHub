export type LelefaCollectionRules = {
  min_days_past_due: number;
  min_overdue_amount: number;
  min_outstanding_balance: number;
  stages: string[];
  priorities: string[];
  exclude_active_promises: boolean;
  exclude_legal_handover: boolean;
  share_national_id: boolean;
  share_employment: boolean;
};

export type LelefaCollectionSettings = {
  enabled: boolean;
  provider: string;
  integration_type: string;
  selection_mode: string;
  rules: LelefaCollectionRules;
  bridge_configured: boolean;
  bridge_status: string;
  privacy: {
    share_bank_account_numbers: boolean;
    share_documents_automatically: boolean;
    share_national_id: boolean;
    share_employment: boolean;
  };
};

export type LelefaCollectionCandidate = {
  collection_case_id: string;
  case_reference: string;
  borrower_id: string;
  loan_id: string;
  loan_reference: string;
  loan_status: string;
  borrower_name: string;
  phone: string | null;
  email: string | null;
  physical_address: string | null;
  district: string | null;
  town_or_village: string | null;
  days_past_due: number;
  overdue_amount: number;
  outstanding_balance: number;
  priority: string;
  stage: string;
  case_status: string;
  promise_status: string | null;
  promise_amount: number | null;
  promise_date: string | null;
  legal_handover_at: string | null;
  loan_principal_amount: number;
  loan_amount_paid: number;
  loan_disbursed_at: string | null;
  national_id?: string | null;
  passport_number?: string | null;
  employment_status?: string | null;
  employer_name?: string | null;
  job_title?: string | null;
  already_referred: boolean;
  eligible: boolean;
};

export type LelefaCandidateResponse = {
  enabled: boolean;
  rules: LelefaCollectionRules;
  candidate_count: number;
  candidate_total_outstanding: number;
  excluded_case_count: number;
  candidates: LelefaCollectionCandidate[];
};

export type LelefaOffer = {
  offer_id: string;
  status: string;
  commission_percent: number;
  onboarding_fee: number;
  legal_action_fee: number;
  max_settlement_discount_percent: number;
  engagement_term_months: number;
  valid_until: string | null;
  reporting_cadence: string;
  service_terms: Record<string, unknown>;
  notes: string | null;
  sent_at: string | null;
};

export type LelefaReferral = {
  id: string;
  reference: string;
  status: string;
  title: string;
  description: string | null;
  amount: number;
  currency: string;
  data: {
    submitted_at?: string;
    company?: Record<string, unknown>;
    criteria?: LelefaCollectionRules;
    items?: LelefaCollectionCandidate[];
    delivery?: { status?: string; message?: string; updated_at?: string };
    remote_referral_id?: string | null;
    offer?: LelefaOffer | null;
    decision?: { decision?: string; status?: string; notes?: string | null; message?: string } | null;
  };
  created_at: string | null;
  updated_at: string | null;
};
