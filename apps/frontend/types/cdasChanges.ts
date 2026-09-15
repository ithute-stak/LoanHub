export type CdasChangeKind = "FIELD_CHANGED" | "DEDUCTION_ADDED" | "DEDUCTION_REMOVED" | "DEDUCTION_MODIFIED";
export type CdasChangeImpact = "MATERIAL" | "INFO";

export interface CdasChangeEntry {
  kind: CdasChangeKind;
  field: string;
  label: string;
  before: unknown;
  after: unknown;
  changed_fields?: string[];
  impact: CdasChangeImpact;
}

export interface CdasClientChangeSet {
  client_key: string;
  client_name: string | null;
  client_reference: string | null;
  employer: string | null;
  latest_analysis_id: string;
  previous_analysis_id: string;
  latest_analyzed_at: string;
  previous_analyzed_at: string;
  change_count: number;
  material_change_count: number;
  has_material_changes: boolean;
  changes: CdasChangeEntry[];
}

export interface CdasChangeDetection {
  summary: {
    clients_compared: number;
    clients_with_material_changes: number;
    total_changes: number;
    material_changes: number;
  };
  items: CdasClientChangeSet[];
  total: number;
}
