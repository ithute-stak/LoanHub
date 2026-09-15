import { api } from "@/lib/api";
import type {
  CdasAnalysisRecordList,
  CdasBookingAnalysis,
  CdasBookingAnalyzeRequest,
  CdasBookingMonitorRequest,
  CdasBookingOpportunity,
  CdasBookingOpportunityList,
  CdasClientProfileDetail,
  CdasClientProfileList,
  CdasPipelineStage,
} from "@/types/cdasBooking";
import type { CdasAgencyIntelligence } from "@/types/cdasAgencyIntelligence";
import type { CdasBookingCalendar } from "@/types/cdasBookingCalendar";
import type { CdasBookingFailureRecord, CdasBookingFailureRequest, CdasBookingFailureWorkspace } from "@/types/cdasBookingFailures";
import type { CdasBookingPriorityQueue } from "@/types/cdasBookingPriority";
import type { CdasBulkAnalyzeRequest, CdasBulkAnalyzeResponse } from "@/types/cdasBulkProcessing";
import type { CdasChangeDetection } from "@/types/cdasChanges";
import type { CdasContactCreateRequest, CdasContactRecord, CdasFollowUpWorkspace } from "@/types/cdasFollowUps";
import type { CdasDataQualityCentre } from "@/types/cdasDataQuality";
import type { CdasDuplicateDetection } from "@/types/cdasDuplicateDetection";
import type { CdasEmployerIntelligence } from "@/types/cdasEmployerIntelligence";
import type { CdasForecast } from "@/types/cdasForecast";
import type { CdasMaxLoanRequest, CdasMaxLoanResult } from "@/types/cdasMaxLoan";
import type { CdasOfficerPerformanceWorkspace } from "@/types/cdasOfficerPerformance";
import type { CdasOpportunityPipeline } from "@/types/cdasOpportunityPipeline";
import type { CdasWhatIfRequest, CdasWhatIfResult } from "@/types/cdasWhatIf";

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
  bulkAnalyze: async (payload: CdasBulkAnalyzeRequest): Promise<CdasBulkAnalyzeResponse> =>
    (await api.post<CdasBulkAnalyzeResponse>("/cdas-booking/bulk-analyze", payload)).data,
  listAnalyses: async (): Promise<CdasAnalysisRecordList> =>
    (await api.get<CdasAnalysisRecordList>("/cdas-booking/analyses")).data,
  listClientProfiles: async (): Promise<CdasClientProfileList> =>
    (await api.get<CdasClientProfileList>("/cdas-booking/clients")).data,
  getClientProfile: async (clientKey: string): Promise<CdasClientProfileDetail> =>
    (await api.get<CdasClientProfileDetail>(`/cdas-booking/clients/${encodeURIComponent(clientKey)}`)).data,
  getDuplicateDetection: async (): Promise<CdasDuplicateDetection> =>
    (await api.get<CdasDuplicateDetection>("/cdas-booking/duplicates")).data,
  getBookingCalendar: async (): Promise<CdasBookingCalendar> =>
    (await api.get<CdasBookingCalendar>("/cdas-booking/calendar")).data,
  getBookingPriorities: async (): Promise<CdasBookingPriorityQueue> =>
    (await api.get<CdasBookingPriorityQueue>("/cdas-booking/priorities")).data,
  getAgencyIntelligence: async (): Promise<CdasAgencyIntelligence> =>
    (await api.get<CdasAgencyIntelligence>("/cdas-booking/agency-intelligence")).data,
  getEmployerIntelligence: async (): Promise<CdasEmployerIntelligence> =>
    (await api.get<CdasEmployerIntelligence>("/cdas-booking/employer-intelligence")).data,
  getForecast: async (): Promise<CdasForecast> =>
    (await api.get<CdasForecast>("/cdas-booking/forecast")).data,
  getChanges: async (): Promise<CdasChangeDetection> =>
    (await api.get<CdasChangeDetection>("/cdas-booking/changes")).data,
  getDataQuality: async (): Promise<CdasDataQualityCentre> =>
    (await api.get<CdasDataQualityCentre>("/cdas-booking/data-quality")).data,
  getOfficerPerformance: async (): Promise<CdasOfficerPerformanceWorkspace> =>
    (await api.get<CdasOfficerPerformanceWorkspace>("/cdas-booking/officer-performance")).data,
  getOpportunityPipeline: async (): Promise<CdasOpportunityPipeline> =>
    (await api.get<CdasOpportunityPipeline>("/cdas-booking/pipeline")).data,
  updatePipelineStage: async (id: string, stage: CdasPipelineStage): Promise<CdasBookingOpportunity> =>
    (await api.patch<CdasBookingOpportunity>(`/cdas-booking/opportunities/${id}/pipeline`, { stage })).data,
  getFollowUps: async (): Promise<CdasFollowUpWorkspace> =>
    (await api.get<CdasFollowUpWorkspace>("/cdas-booking/follow-ups")).data,
  addContact: async (id: string, payload: CdasContactCreateRequest): Promise<CdasContactRecord> =>
    (await api.post<CdasContactRecord>(`/cdas-booking/opportunities/${id}/contacts`, payload)).data,
  assignOpportunity: async (id: string, userId: string | null): Promise<{ opportunity_id: string; assigned_to_user_id: string | null }> =>
    (await api.patch(`/cdas-booking/opportunities/${id}/assignment`, { user_id: userId })).data,
  getBookingFailures: async (): Promise<CdasBookingFailureWorkspace> =>
    (await api.get<CdasBookingFailureWorkspace>("/cdas-booking/failures")).data,
  recordBookingFailure: async (id: string, payload: CdasBookingFailureRequest): Promise<CdasBookingFailureRecord> =>
    (await api.post<CdasBookingFailureRecord>(`/cdas-booking/opportunities/${id}/failures`, payload)).data,
  retryFailedBooking: async (id: string): Promise<CdasBookingOpportunity> =>
    (await api.post<CdasBookingOpportunity>(`/cdas-booking/opportunities/${id}/retry-failed`)).data,
  simulateWhatIf: async (payload: CdasWhatIfRequest): Promise<CdasWhatIfResult> =>
    (await api.post<CdasWhatIfResult>("/cdas-booking/simulator", payload)).data,
  calculateMaxLoan: async (payload: CdasMaxLoanRequest): Promise<CdasMaxLoanResult> =>
    (await api.post<CdasMaxLoanResult>("/cdas-booking/loan-capacity", payload)).data,
  downloadArchivedAnalysisReport: async (id: string): Promise<CdasPdfDownload> => {
    const response = await api.get<Blob>(`/cdas-booking/analyses/${id}/report/pdf`, { responseType: "blob" });
    return {
      blob: response.data,
      filename: filenameFromDisposition(response.headers["content-disposition"]),
    };
  },
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
    (await api.patch<CdasBookingOpportunity>(`/cdas-booking/opportunities/${id}/pipeline`, { stage: "booked" })).data,
};
