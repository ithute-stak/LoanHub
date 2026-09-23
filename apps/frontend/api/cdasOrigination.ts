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
  affordability: number;
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
