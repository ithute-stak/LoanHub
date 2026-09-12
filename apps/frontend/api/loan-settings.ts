import { api } from "@/lib/api";
import type { ContractTemplateStyle } from "@/types/origination";

export type CompanyLoanSettings = {
  id: string;
  company_id: string;
  default_contract_template_style: ContractTemplateStyle;
};

export type ContractTemplateStyleOption = {
  value: ContractTemplateStyle;
  label: string;
};

export const loanSettingsApi = {
  getSettings: async (): Promise<CompanyLoanSettings> =>
    (await api.get<CompanyLoanSettings>("/loan-settings")).data,

  updateSettings: async (
    payload: Pick<CompanyLoanSettings, "default_contract_template_style">,
  ): Promise<CompanyLoanSettings> =>
    (await api.put<CompanyLoanSettings>("/loan-settings", payload)).data,

  listContractTemplateStyles: async (): Promise<ContractTemplateStyleOption[]> =>
    (await api.get<ContractTemplateStyleOption[]>("/loan-settings/contract-template-styles")).data,
};
