export type CdasDataQualitySeverity = "BLOCKER" | "WARNING" | "INFO";

export interface CdasDataQualityDeductionContext {
  item_code: string | null;
  agency_name: string | null;
  reference_no: string | null;
  deduction_amount: number;
  effective_date: string | null;
  expiry_date: string | null;
  status: string | null;
  data_quality_status: string | null;
}

export interface CdasDataQualityIssue {
  category: string;
  severity: CdasDataQualitySeverity;
  label: string;
  message: string;
  source: string;
  deduction: CdasDataQualityDeductionContext | null;
}

export interface CdasDataQualityClient {
  client_key: string;
  client_name: string | null;
  client_reference: string | null;
  employee_no: string | null;
  nid: string | null;
  employer: string | null;
  current_agency_name: string | null;
  decision: string | null;
  latest_analysis_id: string | null;
  latest_analyzed_at: string | null;
  quality_score: number;
  issue_count: number;
  blocker_count: number;
  warning_count: number;
  excluded_monthly_amount: number;
  issues: CdasDataQualityIssue[];
}

export interface CdasDataQualityCategory {
  category: string;
  label: string;
  severity: CdasDataQualitySeverity;
  count: number;
}

export interface CdasDataQualityCentre {
  summary: {
    clients_checked: number;
    clients_with_issues: number;
    blocker_clients: number;
    total_issues: number;
    blocker_issues: number;
    warning_issues: number;
    excluded_monthly_amount: number;
  };
  categories: CdasDataQualityCategory[];
  items: CdasDataQualityClient[];
  total: number;
}
