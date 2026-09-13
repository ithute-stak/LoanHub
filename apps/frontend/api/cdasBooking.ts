import { api } from "@/lib/api";
import type { CdasBookingAnalysis, CdasBookingAnalyzeRequest } from "@/types/cdasBooking";

export const cdasBookingApi = {
  analyze: async (payload: CdasBookingAnalyzeRequest): Promise<CdasBookingAnalysis> =>
    (await api.post<CdasBookingAnalysis>("/cdas-booking/analyze", payload)).data,
};
