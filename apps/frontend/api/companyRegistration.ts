import { api } from "@/lib/api";
import type {
    CompanyOwnerRegistrationPayload,
    CompanyOwnerRegistrationResponse,
} from "@/types/companyRegistration";

export async function registerCompanyOwner(
    payload: CompanyOwnerRegistrationPayload,
): Promise<CompanyOwnerRegistrationResponse> {
    const response = await api.post<CompanyOwnerRegistrationResponse>(
        "/company-registration/",
        payload,
    );
    return response.data;
}
