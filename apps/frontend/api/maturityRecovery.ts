import { api } from "@/lib/api";
import type { MaturityRecoveryOverview, MaturityRenewalPolicy } from "@/types/maturityRecovery";

export type MaturityPolicyUpdate = Pick<
  MaturityRenewalPolicy,
  | "enabled"
  | "rollover_basis"
  | "reuse_original_rate"
  | "renewal_rate_percent"
  | "reuse_original_term"
  | "renewal_term_months"
  | "include_processing_fee"
  | "grace_days"
  | "max_cycles"
  | "notify_borrower"
>;

export const maturityRecoveryApi = {
  overview: async (): Promise<MaturityRecoveryOverview> =>
    (await api.get<MaturityRecoveryOverview>("/maturity-recovery/overview")).data,

  updatePolicy: async (payload: MaturityPolicyUpdate): Promise<MaturityRenewalPolicy> =>
    (await api.patch<MaturityRenewalPolicy>("/maturity-recovery/policy", payload)).data,

  run: async (): Promise<Record<string, number>> =>
    (await api.post<Record<string, number>>("/maturity-recovery/run")).data,

  stopLoan: async (loanId: string, reason: string): Promise<{ message: string; collection_case_id: string | null }> =>
    (await api.post(`/maturity-recovery/loans/${loanId}/stop`, { reason })).data,

  resumeLoan: async (loanId: string): Promise<{ message: string }> =>
    (await api.post(`/maturity-recovery/loans/${loanId}/resume`)).data,
};
