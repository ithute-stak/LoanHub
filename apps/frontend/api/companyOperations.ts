import { api } from "@/lib/api";

export type CompanyOperationsOverview = {
  crm: { open: number; followups_due: number; retention_risk: number };
  collateral: { held: number; unperfected: number; release_requested: number };
  legal: { open: number; court_dates_due: number; limitation_attention: number };
  complaints: { open: number; sla_breached: number; regulatory_reportable: number };
};

export type CompanyOperationRecord = {
  id: string;
  reference: string;
  status?: string;
  borrower_id?: string | null;
  loan_id?: string | null;
  updated_at?: string;
  [key: string]: unknown;
};

export async function getCompanyOperationsOverview(): Promise<CompanyOperationsOverview> {
  return (await api.get<CompanyOperationsOverview>("/company-operations/overview")).data;
}

export async function getCrmCases(): Promise<CompanyOperationRecord[]> {
  return (await api.get<CompanyOperationRecord[]>("/company-operations/crm")).data;
}

export async function getCollateralAssets(): Promise<CompanyOperationRecord[]> {
  return (await api.get<CompanyOperationRecord[]>("/company-operations/collateral")).data;
}

export async function getLegalRecoveryMatters(): Promise<CompanyOperationRecord[]> {
  return (await api.get<CompanyOperationRecord[]>("/company-operations/legal")).data;
}

export async function getComplaintCases(): Promise<CompanyOperationRecord[]> {
  return (await api.get<CompanyOperationRecord[]>("/company-operations/complaints")).data;
}
