import { api } from "@/lib/api";
import type {
  CdasBookingAnalysis,
  CdasBookingAnalyzeRequest,
  CdasBookingMonitor,
  CdasBookingMonitorCreate,
} from "@/types/cdasBooking";

export const cdasBookingApi = {
  analyze: async (payload: CdasBookingAnalyzeRequest): Promise<CdasBookingAnalysis> =>
    (await api.post<CdasBookingAnalysis>("/cdas-booking/analyze", payload)).data,
  listMonitors: async (): Promise<CdasBookingMonitor[]> =>
    (await api.get<CdasBookingMonitor[]>("/cdas-booking/monitors")).data,
  createMonitor: async (payload: CdasBookingMonitorCreate): Promise<CdasBookingMonitor> =>
    (await api.post<CdasBookingMonitor>("/cdas-booking/monitors", payload)).data,
  markBooked: async (monitorId: string): Promise<CdasBookingMonitor> =>
    (await api.patch<CdasBookingMonitor>(`/cdas-booking/monitors/${monitorId}/booked`)).data,
};
