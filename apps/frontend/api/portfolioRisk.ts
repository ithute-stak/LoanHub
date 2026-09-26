import { api } from "@/lib/api";

export type RiskGroup = {
  label: string;
  loan_count: number;
  exposure: number;
  share_percent: number;
  par_30: number;
  fpd_rate: number;
};

export type PortfolioRiskOverview = {
  as_of: string;
  summary: {
    active_exposure: number;
    active_loans: number;
    par_1: number;
    par_1_amount: number;
    par_7: number;
    par_7_amount: number;
    par_30: number;
    par_30_amount: number;
    par_60: number;
    par_60_amount: number;
    par_90: number;
    par_90_amount: number;
    fpd_rate: number;
    fpd_loans: number;
    write_off_count: number;
    write_off_amount: number;
    write_off_rate: number;
    top_up_exposure: number;
    cdas_exposure: number;
    open_recovery_work_items: number;
  };
  delinquency_buckets: Array<{ bucket: string; loan_count: number; exposure: number }>;
  roll_and_cure: {
    available: boolean;
    message?: string;
    previous_snapshot_date?: string;
    current_snapshot_date?: string;
    interval_days?: number;
    cure_rate?: number;
    roll_forward_rate?: number;
    matrix: Array<{ from_bucket: string; to_bucket: string; loan_count: number; exposure: number }>;
  };
  vintages: Array<{
    vintage: string;
    loan_count: number;
    originated_principal: number;
    outstanding_balance: number;
    par_30: number;
    fpd_rate: number;
    write_off_count: number;
    top_up_count: number;
  }>;
  top_up_performance: Array<{
    label: string;
    loan_count: number;
    active_exposure: number;
    par_30: number;
    fpd_rate: number;
    write_off_count: number;
  }>;
  branch_risk: RiskGroup[];
  product_risk: RiskGroup[];
  employer_risk: RiskGroup[];
  concentration: {
    branch: { hhi: number; top_share_percent: number; group_count: number; groups: RiskGroup[] };
    product: { hhi: number; top_share_percent: number; group_count: number; groups: RiskGroup[] };
    employer: { hhi: number; top_share_percent: number; group_count: number; groups: RiskGroup[] };
  };
  projected_cash_flow: Array<{
    month: string;
    scheduled_collections: number;
    cdas_scheduled: number;
    non_cdas_scheduled: number;
    loan_count: number;
  }>;
  methodology: Record<string, string>;
};

export type PortfolioRiskHistory = Array<{
  date: string;
  active_exposure: number;
  par_1: number;
  par_7: number;
  par_30: number;
  par_60: number;
  par_90: number;
}>;

export async function getPortfolioRiskOverview(branchId?: string): Promise<PortfolioRiskOverview> {
  return (await api.get<PortfolioRiskOverview>("/portfolio-risk/overview", {
    params: branchId ? { branch_id: branchId } : undefined,
  })).data;
}

export async function getPortfolioRiskHistory(branchId?: string): Promise<PortfolioRiskHistory> {
  return (await api.get<PortfolioRiskHistory>("/portfolio-risk/history", {
    params: branchId ? { branch_id: branchId } : undefined,
  })).data;
}

export async function createPortfolioRiskSnapshot() {
  return (await api.post("/portfolio-risk/snapshot")).data;
}

export async function downloadPortfolioRiskCsv(branchId?: string) {
  const response = await api.get<Blob>("/portfolio-risk/export.csv", {
    params: branchId ? { branch_id: branchId } : undefined,
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `portfolio-risk-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5_000);
}
