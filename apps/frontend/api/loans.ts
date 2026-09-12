import { api } from "@/lib/api";
import {
  markDocumentGenerationFailed,
  markDocumentGenerationReady,
  prepareDocumentGenerationWindow,
} from "@/lib/document-generation-overlay";
import type { PaymentMethod } from "@/types/expenseManagement";
import type {
  CashPaymentResult,
  CashRepaymentPreview,
  EarlySettlement,
  EarlySettlementPaymentResult,
  Loan,
  LoanDocumentKind,
  LoanPaymentSlip,
  InterestMethod,
  LoanCalculation,
  MicroLoanCalculation,
  OverpaymentAction,
} from "@/types/loan";

export async function listLoans(): Promise<Loan[]> {
  return (await api.get<Loan[]>("/loans/")).data;
}

export async function getLoan(loanId: string): Promise<Loan> {
  return (await api.get<Loan>(`/loans/${loanId}`)).data;
}

export async function getLoanByReference(loanReference: string): Promise<Loan> {
  return (await api.get<Loan>(`/loans/by-reference/${encodeURIComponent(loanReference.trim().toUpperCase())}`)).data;
}

export type InstallmentDueDateAdjustmentPayload = {
  new_due_date: string;
  agreement_note: string;
  agreement_reference?: string | null;
};

export async function adjustInstallmentDueDate(
  loanId: string,
  installmentId: string,
  payload: InstallmentDueDateAdjustmentPayload,
): Promise<Loan> {
  return (
    await api.patch<Loan>(`/loans/${loanId}/installments/${installmentId}/due-date`, payload)
  ).data;
}

export type LoanCalculationPayload = {
  principal: number;
  rate_percent: number;
  months: number;
  processing_fee?: number;
  interest_method: InterestMethod;
  interest_start_date?: string | null;
  due_dates: string[];
};

export async function calculateLoan(payload: LoanCalculationPayload): Promise<LoanCalculation> {
  return (await api.post<LoanCalculation>("/loans/calculator", payload)).data;
}

export async function calculateMicroLoan(
  payload: Omit<LoanCalculationPayload, "interest_method">,
): Promise<MicroLoanCalculation> {
  return calculateLoan({ ...payload, interest_method: "micro_loan" });
}

export type PaymentEvidencePayload = {
  payment_method: PaymentMethod;
  proof_reference?: string | null;
  proof_url?: string | null;
  proof_notes?: string | null;
  notes?: string | null;
  idempotency_key?: string;
};

export async function disburseLoan(
  loanId: string,
  payload: PaymentEvidencePayload,
): Promise<CashPaymentResult> {
  return (await api.post<CashPaymentResult>(`/loans/${loanId}/disburse`, payload)).data;
}

export async function previewRepayment(payload: {
  loan_reference: string;
  amount_tendered: number;
  overpayment_action: OverpaymentAction;
  installment_number?: number;
  payment_method?: PaymentMethod;
  payment_date?: string | null;
}): Promise<CashRepaymentPreview> {
  return (await api.post<CashRepaymentPreview>("/loans/repayments/preview", payload)).data;
}

export async function collectRepayment(payload: {
  loan_reference: string;
  amount_tendered: number;
  overpayment_action: OverpaymentAction;
  installment_number?: number;
  payment_method: PaymentMethod;
  gateway_provider?: string | null;
  gateway_customer_phone?: string | null;
  proof_reference?: string | null;
  proof_url?: string | null;
  proof_notes?: string | null;
  notes?: string;
  idempotency_key?: string;
  payment_date?: string | null;
}): Promise<CashPaymentResult> {
  return (await api.post<CashPaymentResult>("/loans/repayments", payload)).data;
}

export type InstallmentPaymentPayload = {
  amount_tendered: number;
  payment_method: PaymentMethod;
  gateway_provider?: string | null;
  gateway_customer_phone?: string | null;
  proof_reference?: string | null;
  proof_url?: string | null;
  proof_notes?: string | null;
  notes?: string | null;
  idempotency_key?: string;
  payment_date?: string | null;
};

export async function payLoanInstallment(
  loanId: string,
  installmentId: string,
  payload: InstallmentPaymentPayload,
): Promise<CashPaymentResult> {
  return (
    await api.post<CashPaymentResult>(
      `/loans/${loanId}/installments/${installmentId}/payments`,
      payload,
    )
  ).data;
}

// Backward-compatible aliases for older imports. New UI uses the generic names.
export const disburseCashLoan = disburseLoan;
export const previewCashRepayment = previewRepayment;
export const collectCashRepayment = collectRepayment;



export async function listEarlySettlements(loanId: string): Promise<EarlySettlement[]> {
  return (await api.get<EarlySettlement[]>(`/loans/${loanId}/early-settlements`)).data;
}

export async function createEarlySettlementQuote(
  loanId: string,
  payload: { settlement_date: string; valid_for_days?: number },
): Promise<EarlySettlement> {
  return (
    await api.post<EarlySettlement>(`/loans/${loanId}/early-settlements/quote`, payload)
  ).data;
}

export async function payEarlySettlement(
  loanId: string,
  settlementId: string,
  payload: {
    payment_method: PaymentMethod;
    gateway_provider?: string | null;
    gateway_customer_phone?: string | null;
    borrower_acknowledged: boolean;
    agreement_note: string;
    agreement_reference?: string | null;
    notes?: string | null;
    idempotency_key?: string;
  },
): Promise<EarlySettlementPaymentResult> {
  return (
    await api.post<EarlySettlementPaymentResult>(
      `/loans/${loanId}/early-settlements/${settlementId}/pay`,
      payload,
    )
  ).data;
}

export async function listLoanPaymentSlips(loanId: string): Promise<LoanPaymentSlip[]> {
  return (await api.get<LoanPaymentSlip[]>(`/loans/${loanId}/payment-slips`)).data;
}

async function openFastApiPdf(
  url: string,
  title: string,
  targetWindow?: Window | null,
  companyId?: string | null,
): Promise<void> {
  const popup = targetWindow ?? window.open("", "_blank", "width=1100,height=850");
  if (!popup) {
    throw new Error("The PDF window was blocked. Allow pop-ups for LoanHub and try again.");
  }

  prepareDocumentGenerationWindow(popup, {
    title: `Preparing ${title}`,
    description: `Please wait while LoanHub generates the latest ${title} PDF.`,
    companyId,
  });

  try {
    const response = await api.get<Blob>(url, { responseType: "blob" });
    const objectUrl = URL.createObjectURL(response.data);
    markDocumentGenerationReady(popup);
    popup.location.replace(objectUrl);
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 120_000);
  } catch (error) {
    markDocumentGenerationFailed(popup);
    throw error;
  }
}

export async function openLoanDocumentPdf(
  loanId: string,
  loanReference: string,
  kind: LoanDocumentKind,
  targetWindow?: Window | null,
  companyId?: string | null,
): Promise<void> {
  const label: Record<LoanDocumentKind, string> = {
    "loan-information": "loan information",
    "repayment-schedule": "repayment schedule",
    "payment-history": "payment history",
  };
  await openFastApiPdf(
    `/loans/${loanId}/documents/${kind}.pdf`,
    `${loanReference} ${label[kind]}`,
    targetWindow,
    companyId,
  );
}

export async function openLoanPaymentSlipPdf(
  loanId: string,
  slip: LoanPaymentSlip,
  targetWindow?: Window | null,
  companyId?: string | null,
): Promise<void> {
  // Print by payment ID, not receipt file/receipt ID. The backend renders the
  // PDF directly from the authoritative ledger and therefore does not depend
  // on an old ManagedFile that may have disappeared after deployment.
  await openFastApiPdf(
    `/loans/${loanId}/payment-slips/by-payment/${slip.payment_id}.pdf`,
    slip.receipt_number,
    targetWindow,
    companyId,
  );
}
