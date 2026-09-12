import { api } from "@/lib/api";

export type ControlSummary = {
  pending_approvals: number;
  payment_adjustments_attention: number;
  webhook_dead_letters: number;
  unmatched_bank_lines: number;
  open_complaints: number;
};

export type ControlRecord = Record<string, unknown> & { id: string; status: string; created_at?: string };

export const governanceControlsApi = {
  summary: () => api.get<ControlSummary>("/controls/summary").then(r => r.data),
  auditIntegrity: () => api.get<{valid:boolean;sealed_events:number;broken_event_id:string|null}>("/controls/audit-integrity").then(r => r.data),
  paymentAdjustments: () => api.get<ControlRecord[]>("/controls/payment-adjustments").then(r => r.data),
  requestPaymentAdjustment: (payload: Record<string, unknown>) => api.post<ControlRecord>("/controls/payment-adjustments", payload).then(r => r.data),
  decidePaymentAdjustment: (id: string, action: "approve"|"reject", reason: string) => api.post<ControlRecord>(`/controls/payment-adjustments/${id}/${action}`, {reason}).then(r => r.data),
  accountingPeriods: () => api.get<ControlRecord[]>("/controls/accounting-periods").then(r => r.data),
  createAccountingPeriod: (period_start: string, period_end: string) => api.post<ControlRecord>("/controls/accounting-periods", {period_start, period_end}).then(r => r.data),
  periodAction: (id: string, action: "lock"|"close", note: string) => api.post<ControlRecord>(`/controls/accounting-periods/${id}/${action}`, {note}).then(r => r.data),
  bankLines: () => api.get<ControlRecord[]>("/controls/bank-statement-lines").then(r => r.data),
  createBankLine: (payload: Record<string, unknown>) => api.post<ControlRecord>("/controls/bank-statement-lines", payload).then(r => r.data),
  matchBankLine: (id: string, payment_id: string) => api.post<ControlRecord>(`/controls/bank-statement-lines/${id}/match`, {payment_id}).then(r => r.data),
  complaints: () => api.get<ControlRecord[]>("/controls/complaints").then(r => r.data),
  updateComplaint: (id: string, payload: Record<string, unknown>) => api.patch<ControlRecord>(`/controls/complaints/${id}`, payload).then(r => r.data),
  webhookOutbox: () => api.get<ControlRecord[]>("/controls/webhook-outbox").then(r => r.data),
  replayWebhook: (id: string) => api.post<ControlRecord>(`/controls/webhook-outbox/${id}/replay`).then(r => r.data),
  myComplaints: () => api.get<ControlRecord[]>("/controls/my-complaints").then(r => r.data),
  createMyComplaint: (payload: Record<string, unknown>) => api.post<ControlRecord>("/controls/my-complaints", payload).then(r => r.data),
  myDataRights: () => api.get<ControlRecord[]>("/controls/data-rights/mine").then(r => r.data),
  createDataRights: (request_type: string, description: string) => api.post<ControlRecord>("/controls/data-rights", {request_type, description}).then(r => r.data),
};
