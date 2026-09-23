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
  methodology: string;
};

export const cdasDashboardApi = {
  getKpis: async (): Promise<CdasDashboardKpis> =>
    (await api.get<CdasDashboardKpis>("/cdas/daily-intelligence/dashboard-kpis")).data,
};
