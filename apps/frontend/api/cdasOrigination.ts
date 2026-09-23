import { api } from "@/lib/api";

export type CdasOriginationPreview = {
  borrower_id: string;
  employee_no: string;
  verified: boolean;
  total_repayable: number;
  available_affordability: number;
  proposed_monthly_deduction: number;
  estimated_installments: number | null;
  estimated_settlement_date: string | null;
  final_installment: number | null;
  planned_installment: number;
  planned_installment_covered: boolean;
  selected_term_count: number;
  within_selected_term: boolean;
  status: "no_capacity" | "within_selected_term" | "longer_than_selected_term";
  message: string;
  verification: {
    borrower_id: string;
    employee_no: string;
    verified: boolean;
    verified_at: string | null;
    employee: {
      employee_no: string | null;
      name: string | null;
      surname: string | null;
      dob: string | null;
      department: string | null;
      joining_date: string | null;
      termination_date: string | null;
    };
  };
};

export type CdasApplicationCollectionLink = {
  application_id: string;
  enabled: boolean;
  legacy_unspecified: boolean;
  employee_no: string | null;
  linked_at: string | null;
};

export const cdasOriginationApi = {
  preview: async (
    borrowerId: string,
    payload: {
      employee_no: string;
      total_repayable: number;
      planned_installment: number;
      selected_term_count: number;
      first_payment_date?: string | null;
    },
  ): Promise<CdasOriginationPreview> =>
    (await api.post<CdasOriginationPreview>(`/cdas/borrowers/${borrowerId}/origination-preview`, payload)).data,

  getCollectionLink: async (applicationId: string): Promise<CdasApplicationCollectionLink> =>
    (await api.get<CdasApplicationCollectionLink>(`/cdas/origination/applications/${applicationId}/collection-link`)).data,

  setCollectionLink: async (
    applicationId: string,
    payload: { enabled: boolean; employee_no?: string | null },
  ): Promise<CdasApplicationCollectionLink> =>
    (await api.put<CdasApplicationCollectionLink>(`/cdas/origination/applications/${applicationId}/collection-link`, payload)).data,
};
