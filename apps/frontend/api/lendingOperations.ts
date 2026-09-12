import { api } from "@/lib/api";
import type {
  CDASAffordability,
  CDASMandate,
  CDASPayrollProfile,
  CDASRemittanceBatch,
  CDASRemittanceLine,
  CollectionActivity,
  CollectionCase,
  ComplianceCase,
  ComplianceScreening,
  CreditBureauEnquiry,
  CreditDecision,
  CreditDecisionPolicy,
  LendingOperationsDashboard,
  ReconciliationException,
  ReconciliationRun,
  RegulatorySubmission,
  WorkflowInstance,
  WorkflowTemplate,
} from "@/types/lendingOperations";

const base = "/lending-operations";

export const lendingOperationsApi = {
  dashboard: async () => (await api.get<LendingOperationsDashboard>(`${base}/dashboard`)).data,

  listPayrollProfiles: async () => (await api.get<CDASPayrollProfile[]>(`${base}/cdas/payroll-profiles`)).data,
  savePayrollProfile: async (payload: Record<string, unknown>) =>
    (await api.post<CDASPayrollProfile>(`${base}/cdas/payroll-profiles`, payload)).data,
  calculateCDASAffordability: async (payload: Record<string, unknown>) =>
    (await api.post<CDASAffordability>(`${base}/cdas/affordability`, payload)).data,
  listCDASMandates: async () => (await api.get<CDASMandate[]>(`${base}/cdas/mandates`)).data,
  createCDASMandate: async (payload: Record<string, unknown>) =>
    (await api.post<CDASMandate>(`${base}/cdas/mandates`, payload)).data,
  updateCDASMandateStatus: async (id: string, payload: Record<string, unknown>) =>
    (await api.patch<CDASMandate>(`${base}/cdas/mandates/${id}/status`, payload)).data,
  listCDASBatches: async () => (await api.get<CDASRemittanceBatch[]>(`${base}/cdas/remittance-batches`)).data,
  createCDASBatch: async (payload: Record<string, unknown>) =>
    (await api.post<CDASRemittanceBatch>(`${base}/cdas/remittance-batches`, payload)).data,
  listCDASBatchLines: async (id: string) =>
    (await api.get<CDASRemittanceLine[]>(`${base}/cdas/remittance-batches/${id}/lines`)).data,
  createCDASBatchLine: async (id: string, payload: Record<string, unknown>) =>
    (await api.post<CDASRemittanceLine>(`${base}/cdas/remittance-batches/${id}/lines`, payload)).data,
  reconcileCDASBatch: async (id: string) =>
    (await api.post<ReconciliationRun>(`${base}/cdas/remittance-batches/${id}/reconcile`)).data,

  listReconciliationRuns: async () => (await api.get<ReconciliationRun[]>(`${base}/reconciliation/runs`)).data,
  runReconciliation: async (payload: Record<string, unknown>) =>
    (await api.post<ReconciliationRun>(`${base}/reconciliation/run`, payload)).data,
  listReconciliationExceptions: async () =>
    (await api.get<ReconciliationException[]>(`${base}/reconciliation/exceptions`)).data,
  updateReconciliationException: async (id: string, payload: Record<string, unknown>) =>
    (await api.patch<ReconciliationException>(`${base}/reconciliation/exceptions/${id}`, payload)).data,

  listCreditEnquiries: async () => (await api.get<CreditBureauEnquiry[]>(`${base}/credit-bureau/enquiries`)).data,
  createCreditEnquiry: async (payload: Record<string, unknown>) =>
    (await api.post<CreditBureauEnquiry>(`${base}/credit-bureau/enquiries`, payload)).data,
  completeCreditEnquiry: async (id: string, payload: Record<string, unknown>) =>
    (await api.post<CreditBureauEnquiry>(`${base}/credit-bureau/enquiries/${id}/complete`, payload)).data,

  listComplianceCases: async () => (await api.get<ComplianceCase[]>(`${base}/compliance/cases`)).data,
  createComplianceCase: async (payload: Record<string, unknown>) =>
    (await api.post<ComplianceCase>(`${base}/compliance/cases`, payload)).data,
  updateComplianceCase: async (id: string, payload: Record<string, unknown>) =>
    (await api.patch<ComplianceCase>(`${base}/compliance/cases/${id}`, payload)).data,
  listComplianceScreenings: async (id: string) =>
    (await api.get<ComplianceScreening[]>(`${base}/compliance/cases/${id}/screenings`)).data,
  createComplianceScreening: async (id: string, payload: Record<string, unknown>) =>
    (await api.post<ComplianceScreening>(`${base}/compliance/cases/${id}/screenings`, payload)).data,

  listCollectionCases: async () => (await api.get<CollectionCase[]>(`${base}/collections/cases`)).data,
  syncOverdueCases: async () => (await api.post<{ created: number; message: string }>(`${base}/collections/sync-overdue`)).data,
  createCollectionCase: async (payload: Record<string, unknown>) =>
    (await api.post<CollectionCase>(`${base}/collections/cases`, payload)).data,
  updateCollectionCase: async (id: string, payload: Record<string, unknown>) =>
    (await api.patch<CollectionCase>(`${base}/collections/cases/${id}`, payload)).data,
  listCollectionActivities: async (id: string) =>
    (await api.get<CollectionActivity[]>(`${base}/collections/cases/${id}/activities`)).data,
  createCollectionActivity: async (id: string, payload: Record<string, unknown>) =>
    (await api.post<CollectionActivity>(`${base}/collections/cases/${id}/activities`, payload)).data,

  listRegulatorySubmissions: async () =>
    (await api.get<RegulatorySubmission[]>(`${base}/regulatory/submissions`)).data,
  createRegulatorySubmission: async (payload: Record<string, unknown>) =>
    (await api.post<RegulatorySubmission>(`${base}/regulatory/submissions`, payload)).data,
  generateRegulatorySubmission: async (id: string) =>
    (await api.post<RegulatorySubmission>(`${base}/regulatory/submissions/${id}/generate`)).data,
  updateRegulatorySubmission: async (id: string, payload: Record<string, unknown>) =>
    (await api.patch<RegulatorySubmission>(`${base}/regulatory/submissions/${id}`, payload)).data,

  listDecisionPolicies: async () => (await api.get<CreditDecisionPolicy[]>(`${base}/decisions/policies`)).data,
  createDecisionPolicy: async (payload: Record<string, unknown>) =>
    (await api.post<CreditDecisionPolicy>(`${base}/decisions/policies`, payload)).data,
  listDecisions: async () => (await api.get<CreditDecision[]>(`${base}/decisions`)).data,
  evaluateDecision: async (payload: Record<string, unknown>) =>
    (await api.post<CreditDecision>(`${base}/decisions/evaluate`, payload)).data,
  listWorkflowTemplates: async () => (await api.get<WorkflowTemplate[]>(`${base}/workflows/templates`)).data,
  createWorkflowTemplate: async (payload: Record<string, unknown>) =>
    (await api.post<WorkflowTemplate>(`${base}/workflows/templates`, payload)).data,
  listWorkflowInstances: async () => (await api.get<WorkflowInstance[]>(`${base}/workflows/instances`)).data,
  createWorkflowInstance: async (payload: Record<string, unknown>) =>
    (await api.post<WorkflowInstance>(`${base}/workflows/instances`, payload)).data,
  advanceWorkflowInstance: async (id: string, payload: Record<string, unknown>) =>
    (await api.post<WorkflowInstance>(`${base}/workflows/instances/${id}/advance`, payload)).data,
};
