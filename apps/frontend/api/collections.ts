import { api } from "@/lib/api";
import type {
  CollectionAction,
  CollectionActionType,
  CollectionDailyReport,
  CollectionsWorkspace,
} from "@/types/collections";

export const collectionsApi = {
  workspace: async (params?: { search?: string; status?: string; stage?: string }): Promise<CollectionsWorkspace> =>
    (await api.get<CollectionsWorkspace>("/collections/workspace", { params })).data,

  sync: async (): Promise<{ created: number; message: string }> =>
    (await api.post<{ created: number; message: string }>("/collections/sync")).data,

  listActions: async (caseId: string): Promise<CollectionAction[]> =>
    (await api.get<CollectionAction[]>(`/collections/cases/${caseId}/actions`)).data,

  claimCase: async (caseId: string): Promise<{ case_id: string; claimed_by_user_id: string; claim_expires_at: string | null }> =>
    (await api.post(`/maturity-recovery/collections/cases/${caseId}/claim`)).data,

  releaseCase: async (caseId: string): Promise<void> => {
    await api.delete(`/maturity-recovery/collections/cases/${caseId}/claim`);
  },

  createAction: async (
    caseId: string,
    payload: {
      actionType: CollectionActionType;
      customActionTitle?: string;
      outcome?: string;
      notes?: string;
      followUpAt?: string | null;
      contactPhone?: string;
      visitedAddress?: string;
      courtDate?: string;
      courtName?: string;
      courtCaseNumber?: string;
      promiseAmount?: number | null;
      promiseDate?: string | null;
      files?: File[];
    },
  ): Promise<CollectionAction> => {
    const form = new FormData();
    form.append("action_type", payload.actionType);
    if (payload.customActionTitle) form.append("custom_action_title", payload.customActionTitle);
    if (payload.outcome) form.append("outcome", payload.outcome);
    if (payload.notes) form.append("notes", payload.notes);
    if (payload.followUpAt) form.append("follow_up_at", payload.followUpAt);
    if (payload.contactPhone) form.append("contact_phone", payload.contactPhone);
    if (payload.visitedAddress) form.append("visited_address", payload.visitedAddress);
    if (payload.courtDate) form.append("court_date", payload.courtDate);
    if (payload.courtName) form.append("court_name", payload.courtName);
    if (payload.courtCaseNumber) form.append("court_case_number", payload.courtCaseNumber);
    if (payload.promiseAmount !== null && payload.promiseAmount !== undefined) form.append("promise_amount", String(payload.promiseAmount));
    if (payload.promiseDate) form.append("promise_date", payload.promiseDate);
    for (const file of payload.files ?? []) form.append("files", file);
    return (await api.post<CollectionAction>(`/collections/cases/${caseId}/actions`, form)).data;
  },

  listDailyReports: async (): Promise<CollectionDailyReport[]> =>
    (await api.get<CollectionDailyReport[]>("/collections/daily-reports")).data,

  runDailyReport: async (reportDate: string): Promise<{ generated_or_existing: number; report_date: string; message: string }> =>
    (await api.post("/collections/daily-reports/run", null, { params: { report_date: reportDate } })).data,
};
