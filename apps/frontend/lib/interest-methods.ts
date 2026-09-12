import type { InterestMethod } from "@/types/loan";

export const INTEREST_METHOD_OPTIONS: Array<{
  value: InterestMethod;
  label: string;
  rateLabel: string;
  description: string;
}> = [
  {
    value: "micro_loan",
    label: "LoanHub Micro Loan Method",
    rateLabel: "Cycle rate (%)",
    description: "Legacy LoanHub split-and-carry calculation retained for existing products.",
  },
  {
    value: "simple_interest",
    label: "Simple Interest",
    rateLabel: "Annual rate (%)",
    description: "Interest is calculated on the original principal for the full term.",
  },
  {
    value: "flat_rate",
    label: "Flat Rate",
    rateLabel: "Annual flat rate (%)",
    description: "A fixed annual rate is charged on the original principal and split across instalments.",
  },
  {
    value: "compound_interest",
    label: "Compound Interest",
    rateLabel: "Annual rate (%)",
    description: "Interest is capitalised monthly on principal plus prior interest before the fixed schedule is created.",
  },
  {
    value: "reducing_balance",
    label: "Reducing Balance (Amortised)",
    rateLabel: "Annual rate (%)",
    description: "Each month, interest is charged on the remaining principal and the balance reduces after payment.",
  },
  {
    value: "daily_accrual_reducing",
    label: "Daily Accrual Reducing Balance",
    rateLabel: "Annual rate (%)",
    description: "Actual/Month daily interest: annual rate ÷ 12, prorated by the actual days in each calendar month.",
  },
];

export function interestMethodLabel(method: string | null | undefined): string {
  return INTEREST_METHOD_OPTIONS.find((item) => item.value === method)?.label
    ?? String(method ?? "micro_loan").replaceAll("_", " ").replace(/\b\w/g, (value) => value.toUpperCase());
}

export function interestMethodOption(method: InterestMethod) {
  return INTEREST_METHOD_OPTIONS.find((item) => item.value === method) ?? INTEREST_METHOD_OPTIONS[0];
}
