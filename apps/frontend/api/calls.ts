import { api } from "@/lib/api";
import type {
  CallClient,
  CallClientDetail,
  DesktopCallingCapability,
  EmployeeMediaSession,
  CallDashboard,
  CallManagementPolicy,
  CallQualityReview,
  ClientCall,
  LiveMonitorSession,
} from "@/types/calls";

export const callsApi = {
  dashboard: async (): Promise<CallDashboard> =>
    (await api.get<CallDashboard>("/call-management/dashboard")).data,

  listCalls: async (params?: { search?: string; direction?: string; status?: string; limit?: number }): Promise<ClientCall[]> =>
    (await api.get<ClientCall[]>("/call-management/calls", { params })).data,

  getCall: async (callId: string): Promise<ClientCall> =>
    (await api.get<ClientCall>(`/call-management/calls/${callId}`)).data,

  createCall: async (payload: {
    device_call_uuid: string;
    phone_number: string;
    direction: "outgoing";
    started_at: string;
    borrower_id: string;
    loan_id?: string | null;
    status?: "started";
  }): Promise<ClientCall> =>
    (await api.post<ClientCall>("/call-management/calls", payload)).data,

  updateDescription: async (callId: string, description: string | null): Promise<ClientCall> =>
    (await api.put<ClientCall>(`/call-management/calls/${callId}/description`, { description })).data,

  deleteCall: async (callId: string): Promise<void> => {
    await api.delete(`/call-management/calls/${callId}`);
  },

  employeeMediaToken: async (callId: string): Promise<EmployeeMediaSession> =>
    (await api.post<EmployeeMediaSession>(`/call-management/calls/${callId}/media-token`)).data,

  dial: async (callId: string): Promise<{ call_id: string; status: string }> =>
    (await api.post<{ call_id: string; status: string }>(`/call-management/calls/${callId}/dial`)).data,

  hangup: async (callId: string): Promise<{ call_id: string; status: string; ended_at: string }> =>
    (await api.post<{ call_id: string; status: string; ended_at: string }>(`/call-management/calls/${callId}/hangup`)).data,

  listLiveCalls: async (): Promise<ClientCall[]> =>
    (await api.get<ClientCall[]>("/call-management/live-calls")).data,

  listClients: async (search?: string): Promise<CallClient[]> =>
    (await api.get<CallClient[]>("/call-management/clients", { params: { search } })).data,

  getClient: async (borrowerId: string): Promise<CallClientDetail> =>
    (await api.get<CallClientDetail>(`/call-management/clients/${borrowerId}`)).data,

  desktopCapability: async (): Promise<DesktopCallingCapability> =>
    (await api.get<DesktopCallingCapability>("/call-management/desktop-capability")).data,

  getPolicy: async (): Promise<CallManagementPolicy> =>
    (await api.get<CallManagementPolicy>("/call-management/policy")).data,

  updatePolicy: async (payload: Omit<CallManagementPolicy, "id" | "company_id">): Promise<CallManagementPolicy> =>
    (await api.put<CallManagementPolicy>("/call-management/policy", payload)).data,

  monitor: async (callId: string): Promise<LiveMonitorSession> =>
    (await api.post<LiveMonitorSession>(`/call-management/live-calls/${callId}/monitor`)).data,

  playRecording: async (recordingId: string): Promise<Blob> =>
    (await api.get(`/call-management/recordings/${recordingId}/play`, { responseType: "blob" })).data as Blob,

  qualityReview: async (
    callId: string,
    payload: { score: number; compliance_status: string; customer_care_status: string; notes?: string | null },
  ): Promise<CallQualityReview> =>
    (await api.put<CallQualityReview>(`/call-management/calls/${callId}/quality-review`, payload)).data,

  createLegalHold: async (recordingId: string, reason: string) =>
    (await api.post(`/call-management/recordings/${recordingId}/legal-hold`, { reason })).data,

  releaseLegalHold: async (recordingId: string, holdId: string) =>
    (await api.post(`/call-management/recordings/${recordingId}/legal-hold/${holdId}/release`)).data,
};
