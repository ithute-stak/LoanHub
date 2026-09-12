export type ExperianUsageConfiguration = {
  max_report_age_hours?: number;
  require_before_affordability?: boolean;
  include_bureau_commitments_in_affordability?: boolean;
  bureau_debt_mode?: "max" | "bureau_only" | "declared_plus_bureau" | string;
  decline_below_score?: number | null;
  refer_below_score?: number | null;
  block_defaults?: boolean;
  require_identity_match?: boolean;
};

export type ExperianCompanyConfiguration = {
  provider: "experian";
  scope: "company";
  is_enabled: boolean;
  configuration: ExperianUsageConfiguration;
  platform: {
    configured: boolean;
    is_enabled: boolean;
    environment: "sandbox" | "uat" | "production" | string | null;
    has_credentials: boolean;
    last_test_status: string | null;
    last_tested_at: string | null;
    ready_for_company_use: boolean;
    product: string | null;
    region: string | null;
  };
};

export type ExperianPlatformConfiguration = {
  provider: "experian";
  scope: "platform";
  environment: "sandbox" | "uat" | "production" | string;
  is_enabled: boolean;
  has_credentials: boolean;
  last_test_status: string | null;
  last_tested_at: string | null;
  configuration: {
    region?: string;
    product?: string;
    bureau_endpoint_path?: string;
    request_template?: Record<string, unknown>;
    response_mapping?: Record<string, string>;
    [key: string]: unknown;
  };
  readiness: {
    credentials: boolean;
    oauth_connected: boolean;
    bureau_endpoint: boolean;
    request_template: boolean;
    response_mapping: boolean;
    ready_for_company_use: boolean;
  };
};

// Backward-compatible name used by the company Experian workspace.
export type ExperianConfiguration = ExperianCompanyConfiguration;

export type ExperianConnectionTest = {
  provider: "experian";
  environment: string;
  host: string;
  status: "connected";
  token_type: string | null;
  expires_in: number | null;
};

export type CreditBureauEnquiry = {
  id: string;
  company_id: string;
  branch_id: string | null;
  borrower_id: string;
  application_id: string;
  provider: string;
  enquiry_type: string;
  permissible_purpose: string;
  consent_confirmed: boolean;
  consent_method: string | null;
  consent_reference: string | null;
  consent_captured_at: string | null;
  status: "pending" | "succeeded" | "failed" | string;
  provider_reference: string | null;
  requested_at: string;
  completed_at: string | null;
  score: number | null;
  risk_band: string | null;
  identity_match: boolean | null;
  open_accounts_count: number;
  defaults_count: number;
  judgments_count: number;
  collections_count: number;
  recent_enquiries_count: number;
  monthly_commitments: number;
  total_balance: number;
  normalized_result: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  requested_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type CreditBureauDecisionContext = {
  application_id: string;
  declared_monthly_debt: number;
  bureau_monthly_commitments: number | null;
  bureau_total_balance: number | null;
  variance: number | null;
  score: number | null;
  risk_band: string | null;
  defaults_count: number | null;
  latest_enquiry_id: string | null;
  latest_enquiry_status: string | null;
};
