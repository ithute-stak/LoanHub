import { api } from "@/lib/api";

export type ArrearsRule = "simple_carry" | "fixed_schedule" | "carry_with_interest";
export type ArrearsPolicy = {
  rule: ArrearsRule;
  version: number;
  periodic_arrears_rate_percent: number;
  additional_interest_authorized: boolean;
};

const ROOT = "/loan-products/policy";

export async function getCompanyArrearsPolicy(): Promise<ArrearsPolicy> {
  const result = await api.get<ArrearsPolicy>(ROOT + "/company");
  return result.data;
}
export async function saveCompanyArrearsPolicy(policy: ArrearsPolicy): Promise<ArrearsPolicy> {
  const result = await api.put<ArrearsPolicy>(ROOT + "/company", policy);
  return result.data;
}
