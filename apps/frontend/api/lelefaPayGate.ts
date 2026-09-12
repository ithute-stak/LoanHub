import { api } from "@/lib/api";

export type GatewayRailField = {
  key: "phone";
  type: "tel";
  label: string;
  placeholder?: string;
  required: boolean;
  autocomplete?: string;
};

export type GatewayPaymentRail = {
  id: string;
  provider: string;
  label: string;
  description: string;
  payment_method: string;
  flow: "phone_prompt" | "hosted_checkout";
  available: boolean;
  environment: string;
  fields: GatewayRailField[];
};

export type GatewayPaymentMethodCatalog = {
  currency: string;
  methods: GatewayPaymentRail[];
};

export type BorrowerGatewayCheckout = {
  payment_id: string;
  status: string;
  amount: number;
  currency: string;
  checkout_url: string;
};

export type BorrowerSettlementQuote = {
  id: string;
  loan_id: string;
  status: string;
  settlement_date: string;
  quote_expires_at: string;
  calculation_method: string;
  chargeable_periods: number;
  original_balance: number;
  revised_total_repayable: number;
  settlement_amount: number;
  earned_interest: number;
  unearned_interest_rebate: number;
};

export async function getGatewayPaymentMethods(currency = "LSL"): Promise<GatewayPaymentMethodCatalog> {
  return (
    await api.get<GatewayPaymentMethodCatalog>("/lelefapaygate/payment-methods", {
      params: { currency },
    })
  ).data;
}

export async function createBorrowerGatewayCheckout(
  loanId: string,
  payload: { amount: number; idempotency_key?: string },
): Promise<BorrowerGatewayCheckout> {
  return (
    await api.post<BorrowerGatewayCheckout>(
      `/lelefapaygate/borrower/loans/${loanId}/checkout`,
      payload,
    )
  ).data;
}

export async function createBorrowerSettlementQuote(
  loanId: string,
  payload: { settlement_date: string; valid_for_days?: number },
): Promise<BorrowerSettlementQuote> {
  return (
    await api.post<BorrowerSettlementQuote>(
      `/lelefapaygate/borrower/loans/${loanId}/settlement-quotes`,
      payload,
    )
  ).data;
}

export async function createBorrowerSettlementCheckout(
  loanId: string,
  settlementId: string,
  payload: {
    borrower_acknowledged: boolean;
    agreement_note: string;
    agreement_reference?: string;
    idempotency_key?: string;
  },
): Promise<BorrowerGatewayCheckout> {
  return (
    await api.post<BorrowerGatewayCheckout>(
      `/lelefapaygate/borrower/loans/${loanId}/settlement-quotes/${settlementId}/checkout`,
      payload,
    )
  ).data;
}
