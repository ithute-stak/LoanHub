import { api } from "@/lib/api";
import type {
  LelefaCandidateResponse,
  LelefaCollectionSettings,
  LelefaReferral,
} from "@/types/lelefaCollections";

export const lelefaCollectionsApi = {
  settings: async (): Promise<LelefaCollectionSettings> =>
    (await api.get<LelefaCollectionSettings>("/lelefa-collections/settings")).data,

  updateSettings: async (payload: {
    enabled: boolean;
    rules: LelefaCollectionSettings["rules"];
  }): Promise<LelefaCollectionSettings> =>
    (await api.put<LelefaCollectionSettings>("/lelefa-collections/settings", payload)).data,

  candidates: async (): Promise<LelefaCandidateResponse> =>
    (await api.get<LelefaCandidateResponse>("/lelefa-collections/candidates")).data,

  referrals: async (): Promise<LelefaReferral[]> =>
    (await api.get<LelefaReferral[]>("/lelefa-collections/referrals")).data,

  createReferral: async (caseIds: string[], note?: string): Promise<LelefaReferral> =>
    (await api.post<LelefaReferral>("/lelefa-collections/referrals", {
      case_ids: caseIds,
      note: note?.trim() || null,
    })).data,

  retryReferral: async (referralId: string): Promise<LelefaReferral> =>
    (await api.post<LelefaReferral>(`/lelefa-collections/referrals/${referralId}/retry`)).data,

  decideOffer: async (
    referralId: string,
    decision: "accept" | "reject",
    notes?: string,
  ): Promise<LelefaReferral> =>
    (await api.post<LelefaReferral>(`/lelefa-collections/referrals/${referralId}/offer/decision`, {
      decision,
      notes: notes?.trim() || null,
    })).data,
};
