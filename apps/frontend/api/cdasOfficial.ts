import { api } from "@/lib/api";
import type {
  CdasBorrowerIntelligenceRequest,
  CdasBorrowerIntelligenceResponse,
  CdasLinkedActionRequest,
  CdasLinkedModifyRequest,
  CdasLinkedSettlementRequest,
  CdasLoanDeductionRegistrationRequest,
  CdasOfficialMandateEvent,
  CdasOfficialMandateState,
  CdasOfficialRefreshRequest,
  CdasOfficialRefreshResponse,
  CdasRegistrationPlan,
  CdasRegistrationRetryRequest,
} from "@/types/cdasOfficial";

export const cdasOfficialApi = {
  refreshEmployee: async (
    payload: CdasOfficialRefreshRequest,
  ): Promise<CdasOfficialRefreshResponse> =>
    (await api.post<CdasOfficialRefreshResponse>("/cdas/refresh", payload)).data,

  runBorrowerIntelligence: async (
    payload: CdasBorrowerIntelligenceRequest,
  ): Promise<CdasBorrowerIntelligenceResponse> =>
    (await api.post<CdasBorrowerIntelligenceResponse>("/cdas/intelligence", payload)).data,

  getRegistrationPlan: async (loanId: string): Promise<CdasRegistrationPlan> =>
    (await api.get<CdasRegistrationPlan>(`/cdas/loans/${loanId}/registration-plan`)).data,

  registerLoanDeduction: async (
    payload: CdasLoanDeductionRegistrationRequest,
  ): Promise<CdasOfficialMandateState> =>
    (await api.post<CdasOfficialMandateState>("/cdas/loan-deductions", payload)).data,

  retryLoanDeductionRegistration: async (
    stateId: string,
    payload: CdasRegistrationRetryRequest,
  ): Promise<CdasOfficialMandateState> =>
    (
      await api.post<CdasOfficialMandateState>(
        `/cdas/loan-deductions/${stateId}/retry-registration`,
        payload,
      )
    ).data,

  getLoanDeduction: async (loanId: string): Promise<CdasOfficialMandateState> =>
    (await api.get<CdasOfficialMandateState>(`/cdas/loans/${loanId}/deduction`)).data,

  getDeductionState: async (stateId: string): Promise<CdasOfficialMandateState> =>
    (await api.get<CdasOfficialMandateState>(`/cdas/loan-deductions/${stateId}`)).data,

  getDeductionEvents: async (
    stateId: string,
    limit = 100,
  ): Promise<CdasOfficialMandateEvent[]> =>
    (
      await api.get<CdasOfficialMandateEvent[]>(
        `/cdas/loan-deductions/${stateId}/events`,
        { params: { limit } },
      )
    ).data,

  runDeductionAction: async (
    stateId: string,
    payload: CdasLinkedActionRequest,
  ): Promise<CdasOfficialMandateState> =>
    (
      await api.post<CdasOfficialMandateState>(
        `/cdas/loan-deductions/${stateId}/actions`,
        payload,
      )
    ).data,

  modifyActiveDeduction: async (
    stateId: string,
    payload: CdasLinkedModifyRequest,
  ): Promise<CdasOfficialMandateState> =>
    (
      await api.post<CdasOfficialMandateState>(
        `/cdas/loan-deductions/${stateId}/modify-active`,
        payload,
      )
    ).data,

  settleDeduction: async (
    stateId: string,
    payload: CdasLinkedSettlementRequest,
  ): Promise<CdasOfficialMandateState> =>
    (
      await api.post<CdasOfficialMandateState>(
        `/cdas/loan-deductions/${stateId}/settle`,
        payload,
      )
    ).data,

  reconcileDeduction: async (
    stateId: string,
    deductionStatus: number,
  ): Promise<CdasOfficialMandateState> =>
    (
      await api.post<CdasOfficialMandateState>(
        `/cdas/loan-deductions/${stateId}/reconcile`,
        undefined,
        { params: { deduction_status: deductionStatus } },
      )
    ).data,
};
