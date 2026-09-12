import { api } from "@/lib/api";

export type BorrowerWorkspaceContext = {
  account_id: string;
  account_reference: string;
  account_status: string;
  company_id: string;
  branch_id: string | null;
  borrower_id: string;
  name: string;
  phone: string | null;
  email: string | null;
  national_id: string | null;
  passport_number: string | null;
  physical_address: string | null;
  district: string | null;
  town_or_village: string | null;
  employment_status: string | null;
  employer_name: string | null;
  job_title: string | null;
  monthly_income: number | null;
  opened_at: string | null;
};

export const borrowerWorkspaceApi = {
  context: async (borrowerId: string): Promise<BorrowerWorkspaceContext> =>
    (await api.get<BorrowerWorkspaceContext>(`/borrower-workspace/${borrowerId}/context`)).data,
};
