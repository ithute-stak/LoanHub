import type { OpeningSourceType, PaymentMethod } from "@/types/expenseManagement";

export type BackdatedOpeningSourceType = Exclude<
  OpeningSourceType,
  "previous_closing" | "headquarters_funding"
>;

export interface BackdatedOpeningAdjustmentCreate {
  branch_id?: string;
  business_date: string;
  source_type: BackdatedOpeningSourceType;
  payment_method: PaymentMethod;
  amount: number | string;
  currency?: string;
  description: string;
  correction_reason: string;
  source_reference?: string;
  proof_reference?: string;
  proof_url?: string;
  proof_notes?: string;
  corrected_declared_closing_balance?: number | string;
}

export interface BackdatedOpeningAdjustmentResult {
  source_id: string;
  ledger_id: string;
  business_date: string;
  source_reference: string;
  old_opening_balance: number | string;
  new_opening_balance: number | string;
  old_expected_closing_balance: number | string;
  new_expected_closing_balance: number | string;
  target_submission_sequence?: number | null;
  downstream_days_refreshed: number;
  downstream_days_revised: number;
  current_opening_balance?: number | string | null;
  current_expected_closing_balance?: number | string | null;
}
