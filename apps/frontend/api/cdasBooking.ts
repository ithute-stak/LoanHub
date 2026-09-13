import { api } from "@/lib/api";
import type {
  CdasBookingAnalysis,
  CdasBookingAnalyzeRequest,
  CdasBookingMonitorRequest,
  CdasBookingOpportunity,
  CdasBookingOpportunityList,
} from "@/types/cdasBooking";

export const cdasBookingApi = {
  analyze: async (payload: CdasBookingAnalyzeRequest): Promise<CdasBookingAnalysis> =>
    (await api.post<CdasBookingAnalysis>("/cdas-booking/analyze", payload)).data,
  saveOpportunity: async (payload: CdasBookingMonitorRequest): Promise<CdasBookingOpportunity> =>
    (await api.post<CdasBookingOpportunity>("/cdas-booking/opportunities", payload)).data,
  listOpportunities: async (): Promise<CdasBookingOpportunityList> =>
    (await api.get<CdasBookingOpportunityList>("/cdas-booking/opportunities")).data,
  markBooked: async (id: string): Promise<CdasBookingOpportunity> =>
    (await api.patch<CdasBookingOpportunity>(`/cdas-booking/opportunities/${id}/booked`)).data,
};
