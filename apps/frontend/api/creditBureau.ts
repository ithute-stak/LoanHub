import { api } from "@/lib/api";
import type {
  CreditBureauDecisionContext,
  CreditBureauEnquiry,
  ExperianCompanyConfiguration,
  ExperianConnectionTest,
  ExperianPlatformConfiguration,
  ExperianUsageConfiguration,
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

  runExperian: async (
    applicationId: string,
    payload: {
      consent_confirmed: boolean;
      consent_method: "written" | "electronic" | "recorded" | "other";
      consent_reference?: string | null;
      permissible_purpose?: "credit_application";
    },
  ): Promise<CreditBureauEnquiry> =>
    (await api.post<CreditBureauEnquiry>(`/credit-bureau/applications/${applicationId}/experian`, payload)).data,
};

export const platformCreditBureauApi = {
  getExperianConfiguration: async (): Promise<ExperianPlatformConfiguration> =>
    (await api.get<ExperianPlatformConfiguration>("/platform-owner/credit-bureau/experian/configuration")).data,

  updateExperianConfiguration: async (payload: {
    environment: "sandbox" | "uat" | "production";
    is_enabled: boolean;
    configuration: Record<string, unknown>;
    credentials?: {
      username: string;
      password: string;
      client_id: string;
      client_secret: string;
    } | null;
  }): Promise<ExperianPlatformConfiguration> =>
    (await api.put<ExperianPlatformConfiguration>("/platform-owner/credit-bureau/experian/configuration", payload)).data,

  testExperianConnection: async (): Promise<ExperianConnectionTest> =>
    (await api.post<ExperianConnectionTest>("/platform-owner/credit-bureau/experian/test-connection")).data,
};
