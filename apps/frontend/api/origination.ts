import { api } from "@/lib/api";
import {
  markDocumentGenerationFailed,
  markDocumentGenerationReady,
  prepareDocumentGenerationWindow,
} from "@/lib/document-generation-overlay";
import { loanSettingsApi } from "@/api/loan-settings";
import type { InterestMethod } from "@/types/loan";
import type {
  ContractTemplateStyle,
  AffordabilityAssessment,
  BorrowerProfileActivity,
  FinancialProfile,
  FinancialProfileUpdate,
  IntegrationConfiguration,
  LoanContract,
  OriginationApplication,
  OriginationApplicationCreate,
  OriginationPolicy,
  OriginationPolicyUpdate,
  OriginationWorkspace,
  TopUpEligibility,
} from "@/types/origination";

export function toOriginationPolicyUpdate(policy: OriginationPolicy): OriginationPolicyUpdate {
  return {
    currency: policy.currency,
    is_active: policy.is_active,
    allow_concurrent_active_loans: policy.allow_concurrent_active_loans,
    max_active_loans: policy.max_active_loans,
    max_open_applications: policy.max_open_applications,
    allow_top_up: policy.allow_top_up,
    top_up_min_paid_percent: policy.top_up_min_paid_percent,
    top_up_min_paid_installments: policy.top_up_min_paid_installments,
    top_up_owner_exception_enabled: policy.top_up_owner_exception_enabled,
    top_up_require_positive_history: policy.top_up_require_positive_history,
    top_up_settle_existing_balance: policy.top_up_settle_existing_balance,
    cooling_off_days: policy.cooling_off_days,
    min_age: policy.min_age,
    max_age: policy.max_age,
    min_verified_net_income: policy.min_verified_net_income,
    max_dti_percent: policy.max_dti_percent,
    max_installment_income_percent: policy.max_installment_income_percent,
    disposable_income_usage_percent: policy.disposable_income_usage_percent,
    min_disposable_after_installment: policy.min_disposable_after_installment,
    living_expense_buffer: policy.living_expense_buffer,
    dependant_allowance: policy.dependant_allowance,
    min_employment_months: policy.min_employment_months,
    required_payslips: policy.required_payslips,
    required_bank_statement_months: policy.required_bank_statement_months,
    require_kyc_verified: policy.require_kyc_verified,
    require_signed_contract: policy.require_signed_contract,
    allow_blacklisted: policy.allow_blacklisted,
    manager_override_enabled: policy.manager_override_enabled,
  };
}

export const originationApi = {
  getPolicy: async (): Promise<OriginationPolicy> =>
    (await api.get<OriginationPolicy>("/origination/policy")).data,

  updatePolicy: async (payload: OriginationPolicyUpdate): Promise<OriginationPolicy> =>
    (await api.put<OriginationPolicy>("/origination/policy", payload)).data,

  listApplications: async (): Promise<OriginationApplication[]> =>
    (await api.get<OriginationApplication[]>("/origination/applications")).data,

  createApplication: async (payload: OriginationApplicationCreate): Promise<OriginationApplication> =>
    (await api.post<OriginationApplication>("/origination/applications", payload)).data,

  updateApplication: async (id: string, payload: Partial<Omit<OriginationApplicationCreate, "borrower_id">> & { application_step?: number }): Promise<OriginationApplication> =>
    (await api.patch<OriginationApplication>(`/origination/applications/${id}`, payload)).data,

  getWorkspace: async (id: string): Promise<OriginationWorkspace> =>
    (await api.get<OriginationWorkspace>(`/origination/applications/${id}/workspace`)).data,

  getFinancialProfile: async (borrowerId: string): Promise<FinancialProfile> =>
    (await api.get<FinancialProfile>(`/origination/borrowers/${borrowerId}/financial-profile`)).data,

  getMyFinancialProfile: async (): Promise<FinancialProfile> =>
    (await api.get<FinancialProfile>("/borrowers/me/financial-profile")).data,

  saveMyFinancialProfile: async (payload: FinancialProfileUpdate): Promise<FinancialProfile> =>
    (await api.put<FinancialProfile>("/borrowers/me/financial-profile", payload)).data,

  getMyProfileActivity: async (): Promise<BorrowerProfileActivity[]> =>
    (await api.get<BorrowerProfileActivity[]>("/borrowers/me/profile-activity")).data,

  saveFinancialProfile: async (borrowerId: string, payload: FinancialProfileUpdate): Promise<FinancialProfile> =>
    (await api.put<FinancialProfile>(`/origination/borrowers/${borrowerId}/financial-profile`, payload)).data,

  duplicateCheck: async (borrowerId: string) =>
    (await api.get(`/origination/borrowers/${borrowerId}/duplicate-check`)).data,

  topUpEligibility: async (borrowerId: string, loanId?: string | null): Promise<TopUpEligibility> =>
    (await api.get<TopUpEligibility>(`/origination/borrowers/${borrowerId}/top-up-eligibility`, {
      params: { loan_id: loanId || undefined },
    })).data,

  approveTopUpException: async (applicationId: string, reason: string): Promise<OriginationApplication> =>
    (await api.post<OriginationApplication>(`/origination/applications/${applicationId}/top-up-exception/approve`, { reason })).data,

  assess: async (
    applicationId: string,
    payload: { proposed_principal: number; proposed_rate_percent: number; proposed_months: number; processing_fee: number; interest_method: InterestMethod },
  ): Promise<AffordabilityAssessment> =>
    (await api.post<AffordabilityAssessment>(`/origination/applications/${applicationId}/assess`, payload)).data,

  submit: async (applicationId: string): Promise<OriginationApplication> =>
    (await api.post<OriginationApplication>(`/origination/applications/${applicationId}/submit`)).data,

  overrideAssessment: async (assessmentId: string, payload: { decision: string; reason: string }): Promise<AffordabilityAssessment> =>
    (await api.post<AffordabilityAssessment>(`/origination/assessments/${assessmentId}/override`, payload)).data,

  listContracts: async (): Promise<LoanContract[]> =>
    (await api.get<LoanContract[]>("/origination/contracts")).data,

  generateContract: async (
    loanId: string,
    witnessName?: string | null,
    templateStyle?: ContractTemplateStyle | null,
  ): Promise<LoanContract> => {
    const resolvedTemplateStyle = templateStyle
      ?? (await loanSettingsApi.getSettings()).default_contract_template_style;
    return (await api.post<LoanContract>(`/origination/loans/${loanId}/contract`, {
      witness_name: witnessName ?? null,
      template_style: resolvedTemplateStyle,
    })).data;
  },

  borrowerSign: async (contractId: string, payload: { signature_name: string; signature_method: string; witness_name?: string | null }): Promise<LoanContract> =>
    (await api.post<LoanContract>(`/origination/contracts/${contractId}/borrower-sign`, payload)).data,

  companySign: async (contractId: string, signatureMethod: string): Promise<LoanContract> =>
    (await api.post<LoanContract>(`/origination/contracts/${contractId}/company-sign`, { signature_method: signatureMethod })).data,

  regenerateContractPdf: async (
    contractId: string,
    templateStyle?: ContractTemplateStyle | null,
  ): Promise<LoanContract> =>
    (await api.post<LoanContract>(`/origination/contracts/${contractId}/regenerate-pdf`, {
      template_style: templateStyle ?? null,
    })).data,

  listIntegrations: async (): Promise<IntegrationConfiguration[]> =>
    (await api.get<IntegrationConfiguration[]>("/origination/integrations")).data,

  updateIntegration: async (
    provider: string,
    payload: { environment: string; is_enabled: boolean; configuration: Record<string, unknown>; credentials?: string | null },
  ): Promise<IntegrationConfiguration> => {
    if (provider === "experian") {
      throw new Error("Experian provider credentials are controlled by the Platform Owner. Company usage is configured from Credit Origination → Experian credit bureau.");
    }
    return (await api.put<IntegrationConfiguration>(`/origination/integrations/${provider}`, payload)).data;
  },

  openContractForPrinting: async (contract: LoanContract, targetWindow?: Window | null): Promise<void> => {
    const popup = targetWindow ?? window.open("", "_blank", "width=1100,height=850");
    if (!popup) {
      throw new Error("The print window was blocked. Allow pop-ups for LoanHub and try again.");
    }

    prepareDocumentGenerationWindow(popup, {
      title: `Preparing ${contract.contract_number}`,
      description: "Please wait while LoanHub prepares the current contract PDF for printing.",
      companyId: contract.company_id,
    });

    try {
      const response = await api.get<Blob>(`/origination/contracts/${contract.id}/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      markDocumentGenerationReady(popup);
      popup.location.replace(url);
      window.setTimeout(() => URL.revokeObjectURL(url), 120_000);
    } catch (error) {
      markDocumentGenerationFailed(popup);
      throw error;
    }
  },

  downloadContract: async (contract: LoanContract): Promise<void> => {
    const response = await api.get<Blob>(`/origination/contracts/${contract.id}/pdf`, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${contract.contract_number}.pdf`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },
};
