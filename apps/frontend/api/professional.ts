import { api } from "@/lib/api";
import type {
  DirectApplicationApprovePayload,
  DirectApplicationApproveResult,
  DirectApplicationRejectPayload,
  DirectApplicationReviewPayload,
  DirectLoanApplication,
  DirectLoanApplicationCreate,
  PlatformSuggestion,
  PlatformSuggestionCreate,
  SystemAssistantResponse,
} from "@/types/professional";

export const professionalApi = {
  listDirect: async (): Promise<DirectLoanApplication[]> =>
    (await api.get<DirectLoanApplication[]>("/professional/direct-applications")).data,

  createDirect: async (payload: DirectLoanApplicationCreate): Promise<DirectLoanApplication> =>
    (await api.post<DirectLoanApplication>("/professional/direct-applications", payload)).data,

  getDirect: async (id: string): Promise<DirectLoanApplication> =>
    (await api.get<DirectLoanApplication>(`/professional/direct-applications/${id}`)).data,

  reviewDirect: async (id: string, payload: DirectApplicationReviewPayload): Promise<DirectLoanApplication> =>
    (await api.post<DirectLoanApplication>(`/professional/direct-applications/${id}/review`, payload)).data,

  approveDirect: async (id: string, payload: DirectApplicationApprovePayload): Promise<DirectApplicationApproveResult> =>
    (await api.post<DirectApplicationApproveResult>(`/professional/direct-applications/${id}/approve`, payload)).data,

  rejectDirect: async (id: string, payload: DirectApplicationRejectPayload): Promise<DirectLoanApplication> =>
    (await api.post<DirectLoanApplication>(`/professional/direct-applications/${id}/reject`, payload)).data,

  suggestions: async (): Promise<PlatformSuggestion[]> =>
    (await api.get<PlatformSuggestion[]>("/professional/suggestions")).data,

  suggest: async (payload: PlatformSuggestionCreate): Promise<PlatformSuggestion> =>
    (await api.post<PlatformSuggestion>("/professional/suggestions", payload)).data,

  queries: async (): Promise<PlatformSuggestion[]> =>
    (await api.get<PlatformSuggestion[]>("/professional/queries")).data,

  submitQuery: async (payload: PlatformSuggestionCreate): Promise<PlatformSuggestion> =>
    (await api.post<PlatformSuggestion>("/professional/queries", payload)).data,

  updateQuery: async (
    id: string,
    payload: { status: string; platform_response?: string | null },
  ): Promise<PlatformSuggestion> =>
    (await api.patch<PlatformSuggestion>(`/professional/suggestions/${id}`, payload)).data,

  wall: async (): Promise<unknown[]> =>
    (await api.get<unknown[]>("/professional/wall-posts")).data,

  interest: async (id: string): Promise<unknown> =>
    (await api.post(`/professional/wall-posts/${id}/interest`)).data,

  ask: async (question: string, current_path: string): Promise<SystemAssistantResponse> =>
    (await api.post<SystemAssistantResponse>("/professional/assistant", { question, current_path })).data,
};
