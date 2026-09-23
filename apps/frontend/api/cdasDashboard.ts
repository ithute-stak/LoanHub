import { api } from "@/lib/api";

export type CdasMovement = {
  amount: number;
  percent: number | null;
  direction: "growth" | "decay" | "stable" | "new_book";
};

export type CdasWindowKpi = {
  days: number;
  count: number;
  monthly_amount: number;
  nearest_date: string | null;
};

export type CdasBranchBookKpi = {
  branch_id: string | null;
  name: string;
  active_deduction_count: number;
  active_client_count: number;
  monthly_amount: number;
};

export type CdasOfficerBookKpi = {
  user_id: string;
  name: string;
  active_deduction_count: number;
  active_client_count: number;
  monthly_amount: number;
};

export type CdasDashboardKpis = {
  configured: boolean;
  environment: "test" | "live" | string;
  as_of: string;
  currency: "LSL" | string;
  active_deduction_count: number;
  active_client_count: number;
  monthly_active_deductions: number;
  previous_month_deductions: number;
  month_movement: CdasMovement;
  soon_commencing: CdasWindowKpi;
  soon_expiring: CdasWindowKpi;
  projected_next_month: {
    month: string;
    monthly_amount: number;
    movement: CdasMovement;
    basis: string;
  };
  ready_for_collection_review: number;
  monitor_no_capacity: number;
  potential_additional_monthly_deduction: number;
  latest_daily_check: string | null;
  daily_check_failures_today: number;
  run_rate_history: Array<{ month: string; amount: number }>;
  top_branches: CdasBranchBookKpi[];
  top_officers: CdasOfficerBookKpi[];
  methodology: string;
};

export type CdasMonthlyAutomationStatus = {
  enabled: boolean;
  configured: boolean;
  item_code: string;
  loan_policy: number;
  timezone: string;
  window_start_day: number;
  window_end_day: number;
  scheduled_time: string;
  authorization_basis: string;
  legacy_daily_0345_enabled: boolean;
  latest: Record<string, unknown> | null;
  latest_run: {
    date: string | null;
    checked: number;
    positive_affordability: number;
    activated: number;
    no_capacity: number;
    failed: number;
    provider_writes: number;
    remaining_affordability: number;
  };
  totals: {
    checks: number;
    activated: number;
    provider_writes: number;
    failed: number;
  };
};

export const cdasDashboardApi = {
  getKpis: async (): Promise<CdasDashboardKpis> =>
    (await api.get<CdasDashboardKpis>("/cdas/daily-intelligence/dashboard-kpis")).data,
  getMonthlyAutomationStatus: async (): Promise<CdasMonthlyAutomationStatus> =>
    (await api.get<CdasMonthlyAutomationStatus>("/cdas/monthly-automation/status")).data,
};
