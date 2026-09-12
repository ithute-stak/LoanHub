import { api } from "@/lib/api";
import type { CompanySocialShareSettings } from "@/types/files";

export type CompanySocialShareSettingsPayload = Omit<
    CompanySocialShareSettings,
    "id" | "company_id" | "configured_by_user_id" | "created_at" | "updated_at"
>;

export async function getCompanySocialShareSettings(companyId: string): Promise<CompanySocialShareSettings> {
    const response = await api.get<CompanySocialShareSettings>(`/companies/${companyId}/social-sharing`);
    return response.data;
}

export async function updateCompanySocialShareSettings(
    companyId: string,
    payload: CompanySocialShareSettingsPayload,
): Promise<CompanySocialShareSettings> {
    const response = await api.put<CompanySocialShareSettings>(`/companies/${companyId}/social-sharing`, payload);
    return response.data;
}
