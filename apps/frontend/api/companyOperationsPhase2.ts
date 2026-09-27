import { api } from "@/lib/api";

export type Phase2Overview = {
  procurement: { pending_approval: number };
  budgeting: { draft_plans: number; approved_plans: number };
  internal_audit: { open_engagements: number; open_findings: number };
};

export type Phase2Record = {
  id: string;
  reference?: string;
  title?: string;
  status?: string;
  amount?: number;
  fiscal_year?: string;
  audit_area?: string;
  updated_at?: string;
  [key: string]: unknown;
};

export async function getPhase2Overview(): Promise<Phase2Overview> {
  return (await api.get<Phase2Overview>("/company-operations-phase2/overview")).data;
}

export async function getProcurementRequests(): Promise<Phase2Record[]> {
  return (await api.get<Phase2Record[]>("/company-operations-phase2/procurement")).data;
}
