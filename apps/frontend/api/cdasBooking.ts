import { api } from "@/lib/api";
import type {
  CdasBookingAnalysis,
  CdasBookingAnalyzeRequest,
  CdasBookingMonitorRequest,
  CdasBookingOpportunity,
  CdasBookingOpportunityList,
} from "@/types/cdasBooking";

export interface CdasPdfDownload {
  blob: Blob;
  filename: string | null;
}

function filenameFromDisposition(value?: string): string | null {
  if (!value) return null;
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try { return decodeURIComponent(encoded); } catch { return encoded; }
  }
  return value.match(/filename="?([^";]+)"?/i)?.[1] || null;
}

export const cdasBookingApi = {
  analyze: async (payload: CdasBookingAnalyzeRequest): Promise<CdasBookingAnalysis> =>
    (await api.post<CdasBookingAnalysis>("/cdas-booking/analyze", payload)).data,
  downloadAnalysisReport: async (payload: CdasBookingMonitorRequest): Promise<CdasPdfDownload> => {
    const response = await api.post<Blob>("/cdas-booking/report/pdf", payload, { responseType: "blob" });
    return {
      blob: response.data,
      filename: filenameFromDisposition(response.headers["content-disposition"]),
    };
  },
  saveOpportunity: async (payload: CdasBookingMonitorRequest): Promise<CdasBookingOpportunity> =>
    (await api.post<CdasBookingOpportunity>("/cdas-booking/opportunities", payload)).data,
  listOpportunities: async (): Promise<CdasBookingOpportunityList> =>
    (await api.get<CdasBookingOpportunityList>("/cdas-booking/opportunities")).data,
  downloadOpportunityReport: async (id: string): Promise<CdasPdfDownload> => {
    const response = await api.get<Blob>(`/cdas-booking/opportunities/${id}/report/pdf`, { responseType: "blob" });
    return {
      blob: response.data,
      filename: filenameFromDisposition(response.headers["content-disposition"]),
    };
  },
  markBooked: async (id: string): Promise<CdasBookingOpportunity> =>
    (await api.patch<CdasBookingOpportunity>(`/cdas-booking/opportunities/${id}/booked`)).data,
};
