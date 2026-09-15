export type CdasLinkedApplication = {
  id: string;
  application_reference: string;
  borrower_id: string;
  status: string;
  requested_amount: number;
  term_count: number;
  created_at: string;
};

export type CdasApplicationHandoffItem = {
  opportunity_id: string;
  client_name: string | null;
  client_reference: string | null;
  employee_no: string | null;
  nid: string | null;
  employer: string | null;
  pipeline_stage: string | null;
  booking_open_date: string | null;
  opportunity_agency_name: string | null;
  opportunity_expiry_date: string | null;
  application: CdasLinkedApplication | null;
};

export type CdasApplicationHandoffWorkspace = {
  items: CdasApplicationHandoffItem[];
  total: number;
  policy_note: string;
};

export type CdasApplicationHandoffCreate = {
  borrower_id: string;
  branch_id?: string | null;
  product_id?: string | null;
  requested_amount: number;
  term_count: number;
  purpose?: string | null;
  installment_due_dates: string[];
};

export type CdasCreatedApplicationHandoff = {
  id: string;
  application_reference: string;
  status: string;
  borrower_id: string;
  requested_amount: number;
  term_count: number;
  channel: string;
  cdas_source_opportunity_id: string;
  cdas_source_analysis_id: string | null;
  origination_workspace_url: string;
  policy_note: string;
};
