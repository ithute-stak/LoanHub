import { api } from "@/lib/api";
import type {
  CdasOfficialRefreshRequest,
  CdasOfficialRefreshResponse,
} from "@/types/cdasOfficial";

export const cdasOfficialApi = {
  refreshEmployee: async (
    payload: CdasOfficialRefreshRequest,
  ): Promise<CdasOfficialRefreshResponse> =>
    (await api.post<CdasOfficialRefreshResponse>("/cdas/refresh", payload)).data,
};
