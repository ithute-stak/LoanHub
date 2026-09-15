export type CdasDuplicateConfidence = "HIGH" | "MEDIUM";

export interface CdasDuplicateProfileSummary {
  client_key: string;
  client_name?: string | null;
  client_reference?: string | null;
  employee_no?: string | null;
  nid?: string | null;
  employer?: string | null;
  current_agency_name?: string | null;
  latest_analysis_id?: string | null;
  latest_analyzed_at?: string | null;
  analysis_count: number;
  opportunity_count: number;
}

export interface CdasDuplicateSharedIdentifier {
  value: string;
  left_field: string;
  right_field: string;
}

export interface CdasDuplicateCandidate {
  candidate_id: string;
  confidence: CdasDuplicateConfidence;
  reason_codes: string[];
  evidence: string[];
  shared_identifiers: CdasDuplicateSharedIdentifier[];
  left: CdasDuplicateProfileSummary;
  right: CdasDuplicateProfileSummary;
}

export interface CdasDuplicateDetection {
  summary: {
    profiles_checked: number;
    candidate_pairs: number;
    high_confidence_pairs: number;
    medium_confidence_pairs: number;
    affected_client_profiles: number;
  };
  items: CdasDuplicateCandidate[];
  total: number;
  policy: {
    automatic_merge: boolean;
    fuzzy_name_matching: boolean;
    description: string;
  };
}
