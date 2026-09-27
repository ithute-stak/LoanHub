import { api } from "@/lib/api";

export type ReconciliationLine = {
  id: string;
  source_kind: string;
  transaction_date: string;
  reference: string | null;
  description: string | null;
  amount: number;
  currency: string;
  direction: string;
  status: string;
  match_method: string | null;
  match_confidence: number | null;
  matched_payment_id: string | null;
  matched_loan_id: string | null;
  folio_number: string | null;
  expected_amount: number | null;
  variance_amount: number;
  exception_code: string | null;
  exception_reason: string | null;
  candidate_snapshot: Array<Record<string, unknown>>;
  is_manual_match: boolean;
  resolution_note: string | null;
  payment_adjustment_id: string | null;
};

export type ReconciliationBatch = {
  id: string;
  batch_reference: string;
  source_type: string;
  source_reference: string | null;
  account_reference: string | null;
  period_start: string;
  period_end: string;
  currency: string;
  status: string;
  imported_line_count: number;
  matched_line_count: number;
  exception_line_count: number;
  duplicate_line_count: number;
  missing_source_count: number;
  imported_amount: number;
  matched_amount: number;
  shortage_amount: number;
  excess_amount: number;
  unmatched_amount: number;
  imported_at: string | null;
  reconciled_at: string | null;
  closed_at: string | null;
  close_note: string | null;
  lines?: ReconciliationLine[];
};

export type ReconciliationDashboard = {
  summary: {
    open_batches: number;
    exception_batches: number;
    unresolved_exceptions: number;
    shortage_amount: number;
    excess_amount: number;
    unmatched_amount: number;
  };
  batches: ReconciliationBatch[];
};

export async function getReconciliationDashboard(): Promise<ReconciliationDashboard> {
  return (await api.get<ReconciliationDashboard>("/reconciliation/dashboard")).data;
}

export async function createReconciliationBatch(payload: {
  source_type: string;
  source_reference?: string | null;
  account_reference?: string | null;
  period_start: string;
  period_end: string;
  currency?: string;
}): Promise<ReconciliationBatch> {
  return (await api.post<ReconciliationBatch>("/reconciliation/batches", payload)).data;
}

export async function getReconciliationBatch(id: string): Promise<ReconciliationBatch> {
  return (await api.get<ReconciliationBatch>(`/reconciliation/batches/${id}`)).data;
}

export async function uploadReconciliationCsv(id: string, file: File): Promise<ReconciliationBatch> {
  const form = new FormData();
  form.append("file", file);
  return (await api.post<ReconciliationBatch>(`/reconciliation/batches/${id}/import.csv`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  })).data;
}

export async function reconcileBatch(id: string): Promise<ReconciliationBatch> {
  return (await api.post<ReconciliationBatch>(`/reconciliation/batches/${id}/reconcile`)).data;
}

export async function manuallyMatchLine(batchId: string, lineId: string, paymentId: string, evidenceNote: string): Promise<ReconciliationLine> {
  return (await api.put<ReconciliationLine>(`/reconciliation/batches/${batchId}/lines/${lineId}/match`, {
    payment_id: paymentId,
    evidence_note: evidenceNote,
  })).data;
}

export async function resolveReconciliationLine(batchId: string, lineId: string, resolution: "ignored" | "duplicate", note: string): Promise<ReconciliationLine> {
  return (await api.patch<ReconciliationLine>(`/reconciliation/batches/${batchId}/lines/${lineId}/resolve`, { resolution, note })).data;
}

export async function requestReconciliationAdjustment(batchId: string, lineId: string, payload: { adjustment_type: string; amount: number; reason: string }) {
  return (await api.post(`/reconciliation/batches/${batchId}/lines/${lineId}/adjustment`, payload)).data;
}

export async function closeReconciliationBatch(id: string, note: string): Promise<ReconciliationBatch> {
  return (await api.post<ReconciliationBatch>(`/reconciliation/batches/${id}/close`, { note })).data;
}

export async function downloadReconciliationCsv(batch: ReconciliationBatch) {
  const response = await api.get<Blob>(`/reconciliation/batches/${batch.id}/export.csv`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${batch.batch_reference}-reconciliation.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5000);
}
