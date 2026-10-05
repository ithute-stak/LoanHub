import { api } from "@/lib/api";
import type {
  CreditBureauDecisionContext,
  CreditBureauEnquiry,
  ExperianCompanyConfiguration,
  ExperianConnectionTest,
  ExperianPlatformConfiguration,
  ExperianUsageConfiguration,
  CreditBureauSubscription,
  CreditBureauPaygTransaction,
  CreditBureauUsage,
  CreditBureauInvoice,
} from "@/types/creditBureau";

export const creditBureauApi = {
  getExperianConfiguration: async (): Promise<ExperianCompanyConfiguration> =>
    (await api.get<ExperianCompanyConfiguration>("/credit-bureau/experian/configuration")).data,

  updateExperianConfiguration: async (payload: {
    is_enabled: boolean;
    configuration: ExperianUsageConfiguration;
  }): Promise<ExperianCompanyConfiguration> =>
    (await api.put<ExperianCompanyConfiguration>("/credit-bureau/experian/configuration", payload)).data,

  listApplicationEnquiries: async (applicationId: string): Promise<CreditBureauEnquiry[]> =>
    (await api.get<CreditBureauEnquiry[]>(`/credit-bureau/applications/${applicationId}/enquiries`)).data,

  decisionContext: async (applicationId: string): Promise<CreditBureauDecisionContext> =>
    (await api.get<CreditBureauDecisionContext>(`/credit-bureau/applications/${applicationId}/decision-context`)).data,

  requestExperianSubscription: async (): Promise<CreditBureauSubscription> =>
    (await api.post<CreditBureauSubscription>("/credit-bureau/experian/subscription")).data,

  getExperianSubscription: async (): Promise<CreditBureauSubscription> =>
    (await api.get<CreditBureauSubscription>("/credit-bureau/experian/subscription")).data,

  listExperianTransactions: async (): Promise<CreditBureauPaygTransaction[]> =>
    (await api.get<CreditBureauPaygTransaction[]>("/credit-bureau/experian/transactions")).data,

  getExperianUsage: async (): Promise<CreditBureauUsage> =>
    (await api.get<CreditBureauUsage>("/credit-bureau/experian/usage")).data,

  listExperianInvoices: async (): Promise<CreditBureauInvoice[]> =>
    (await api.get<CreditBureauInvoice[]>("/credit-bureau/experian/invoices")).data,

  runExperian: async (
    applicationId: string,
    payload: {
      consent_confirmed: boolean;
      consent_method: "written" | "electronic" | "recorded" | "other";
      consent_reference?: string | null;
      permissible_purpose?: "credit_application";
      enquiry_purpose?: number;
      result_type?: "JSON" | "XML";
      address1?: string | null;
      address2?: string | null;
      address3?: string | null;
      address4?: string | null;
      postal_code: string;
      cs_data?: boolean;
      cpa_plus_nlr_data?: boolean;
      deeds?: boolean;
      directors?: boolean;
      run_compuscore?: boolean;
      run_codix?: boolean;
      force_refresh?: boolean;
    },
  ): Promise<CreditBureauEnquiry> =>
    (await api.post<CreditBureauEnquiry>(`/credit-bureau/applications/${applicationId}/experian`, payload)).data,
};

export const platformCreditBureauApi = {
  getExperianConfiguration: async (): Promise<ExperianPlatformConfiguration> =>
    (await api.get<ExperianPlatformConfiguration>("/platform-owner/credit-bureau/experian/configuration")).data,

  updateExperianConfiguration: async (payload: {
    environment: "sandbox" | "live";
    is_enabled: boolean;
    configuration: Record<string, unknown>;
    credentials?: {
      username: string;
      password: string;
    } | null;
  }): Promise<ExperianPlatformConfiguration> =>
    (await api.put<ExperianPlatformConfiguration>("/platform-owner/credit-bureau/experian/configuration", payload)).data,

  testExperianConnection: async (): Promise<ExperianConnectionTest> =>
    (await api.post<ExperianConnectionTest>("/platform-owner/credit-bureau/experian/test-connection")).data,

  listExperianSubscriptions: async (): Promise<CreditBureauSubscription[]> =>
    (await api.get<CreditBureauSubscription[]>("/platform-owner/credit-bureau/experian/subscriptions")).data,

  decideExperianSubscription: async (
    companyId: string,
    payload: {
      decision: "approved" | "rejected" | "suspended";
      price_per_transaction?: number | null;
      currency?: string | null;
      reason?: string | null;
      notes?: string | null;
      credit_limit?: number | null;
      warning_threshold?: number | null;
      auto_suspend_on_limit?: boolean | null;
      billing_due_days?: number | null;
    },
  ): Promise<CreditBureauSubscription> =>
    (await api.post<CreditBureauSubscription>(`/platform-owner/credit-bureau/experian/subscriptions/${companyId}/decision`, payload)).data,

  listExperianTransactions: async (): Promise<CreditBureauPaygTransaction[]> =>
    (await api.get<CreditBureauPaygTransaction[]>("/platform-owner/credit-bureau/experian/transactions")).data,

  waiveExperianTransaction: async (transactionId: string, reason: string): Promise<CreditBureauPaygTransaction> =>
    (await api.post<CreditBureauPaygTransaction>(`/platform-owner/credit-bureau/experian/transactions/${transactionId}/waive`, { reason })).data,

  issueExperianInvoice: async (companyId: string, periodStart: string, periodEnd: string): Promise<CreditBureauInvoice> =>
    (await api.post<CreditBureauInvoice>(`/platform-owner/credit-bureau/experian/invoices/${companyId}`, { period_start: periodStart, period_end: periodEnd })).data,

  listExperianInvoices: async (): Promise<CreditBureauInvoice[]> =>
    (await api.get<CreditBureauInvoice[]>("/platform-owner/credit-bureau/experian/invoices")).data,

  markExperianInvoicePaid: async (invoiceId: string): Promise<CreditBureauInvoice> =>
    (await api.post<CreditBureauInvoice>(`/platform-owner/credit-bureau/experian/invoices/${invoiceId}/paid`)).data,
};
