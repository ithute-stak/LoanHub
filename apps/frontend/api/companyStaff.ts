import { api } from "@/lib/api";
import type {
    CompanyStaff,
    CreateCompanyStaffAccountPayload,
    CreateCompanyStaffPayload,
    UpdateCompanyStaffPayload,
} from "@/types/companyStuff";

export async function createCompanyStaffAccount(
    payload: CreateCompanyStaffAccountPayload,
): Promise<CompanyStaff> {
    const response = await api.post<CompanyStaff>("/company-staff/accounts", payload);
    return response.data;
}


export async function assignCompanyStaffRole(
    payload: CreateCompanyStaffPayload,
): Promise<CompanyStaff> {
    const response = await api.post<CompanyStaff>("/company-staff/", payload);
    return response.data;
}

export async function updateCompanyStaffMember(
    staffId: string,
    payload: UpdateCompanyStaffPayload,
): Promise<CompanyStaff> {
    const response = await api.put<CompanyStaff>(`/company-staff/${staffId}`, payload);
    return response.data;
}

export async function deleteCompanyStaffMember(staffId: string): Promise<void> {
    await api.delete(`/company-staff/${staffId}`);
}

export async function setCompanyStaffUserStatus(
    userId: string,
    isActive: boolean,
): Promise<CompanyStaff[]> {
    const response = await api.patch<CompanyStaff[]>(
        `/company-staff/users/${userId}/status`,
        { is_active: isActive },
    );
    return response.data;
}
