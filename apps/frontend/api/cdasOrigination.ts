import { api } from "@/lib/api";

export type CdasOriginationPreview = {
  borrower_id: string;
  employee_no: string;
  verified: boolean;
  national_id_masked: string;
  employee: {
    employee_no: string | null;
    name: string | null;
    surname: string | null;
    dob: string | null;
    department: string | null;
    joining_date: string | null;
    termination_date: string | null;
  };
  provider_reported_affordability: number;
  pending_loanhub_cdas_commitments: number;
  pending_commitment_loans: Array<{
    loan_id: string;
    loan_reference: string;
    reserved_installment: number;
  }>;
  affordability: number;
  net_available_affordability: number;
  total_repayable: number;
  scheduled_installment: number;
  requested_term: number;
  fits_scheduled_installment: boolean;
  payroll_shortfall: number;
  remaining_affordability_after_scheduled: number;
  effective_preview_deduction: number;
  estimated_installments_at_effective_deduction: number | null;
  estimated_settlement_month: string | null;
  fastest_installments_at_full_affordability: number | null;
  fastest_settlement_month: string | null;
  processing_window_start: string;
  processing_window_end: string;
  processing_time: string;
  timezone: string;
  effective_month: string;
  first_expected_collection_month: string;
  monitoring_required: boolean;
  automation_note: string;
};

export type CdasOriginationPreviewRequest = {
  employee_no: string;
  total_repayable: number;
  scheduled_installment: number;
  requested_term: number;
};

export async function previewCdasOrigination(
  borrowerId: string,
  payload: CdasOriginationPreviewRequest,
): Promise<CdasOriginationPreview> {
  return (
    await api.post<CdasOriginationPreview>(
      `/cdas/borrowers/${borrowerId}/origination-preview`,
      payload,
    )
  ).data;
}