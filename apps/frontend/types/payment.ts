import type { PaymentMethod } from "@/types/expenseManagement";

export type PaymentProvider = "cash" | "lelefapaygate" | "manual" | "mpesa" | "ecocash" | "eft" | "mock";
export type PaymentStatus = "pending" | "processing" | "succeeded" | "failed" | "cancelled" | "reversed";
export type PaymentDirection = "inbound" | "outbound";
export type PaymentPurpose =
  | "subscription"
  | "marketplace_unlock"
  | "loan_disbursement"
  | "loan_repayment"
  | "borrow_request_fee"
  | "assisted_borrower_account_fee"
  | "platform_fee"
  | "platform_transaction_charge"
  | "platform_claim_settlement"
  | "business_payment"
  | "refund";

export type CashTransaction = {
  id: string;
  payment_id: string;
  branch_id: string | null;
  handled_by_user_id: string | null;
  direction: PaymentDirection;
  cash_reference: string;
  tendered_amount: number;
  applied_amount: number;
  change_amount: number;
  forward_amount: number;
  installment_number: number | null;
  expected_installment_amount: number | null;
  installment_outstanding_before: number | null;
  installment_outstanding_after: number | null;
  notes: string | null;
  created_at: string;
};

export type PaymentTransaction = {
  id: string;
  company_id: string | null;
  borrower_id: string | null;
  loan_request_id: string | null;
  loan_id: string | null;
  direct_application_id: string | null;
  initiated_by_user_id: string | null;
  provider: PaymentProvider;
  payment_method: PaymentMethod;
  direction: PaymentDirection;
  purpose: PaymentPurpose;
  status: PaymentStatus;
  amount: number;
  currency: string;
  idempotency_key: string;
  provider_reference: string | null;
  proof_reference: string | null;
  proof_url: string | null;
  proof_notes: string | null;
  verified_by_user_id: string | null;
  verified_at: string | null;
  provider_payload: Record<string, unknown>;
  failure_reason: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  cash_transaction: CashTransaction | null;
};
