import { api } from "@/lib/api";

export type CompanyOwnerAccount = {
    staff_id: string;
    user_id: string;
    full_name: string;
    email: string | null;
    phone: string;
    is_active: boolean;
    is_verified: boolean;
    must_change_password: boolean;
};

export type CompanyOwnerAccountUpdate = {
    email: string | null;
    phone: string;
    is_active: boolean;
};

export type CompanyOwnerTemporaryPassword = {
    user_id: string;
    temporary_password: string;
    must_change_password: boolean;
    message: string;
};

export async function getCompanyOwnerAccount(
    companyId: string,
): Promise<CompanyOwnerAccount> {
    const response = await api.get<CompanyOwnerAccount>(
        `/companies/${companyId}/owner-account`,
    );
    return response.data;
}

export async function updateCompanyOwnerAccount(
    companyId: string,
    payload: CompanyOwnerAccountUpdate,
): Promise<CompanyOwnerAccount> {
    const response = await api.patch<CompanyOwnerAccount>(
        `/companies/${companyId}/owner-account`,
        payload,
    );
    return response.data;
}

export async function createCompanyOwnerTemporaryPassword(
    companyId: string,
): Promise<CompanyOwnerTemporaryPassword> {
    const response = await api.post<CompanyOwnerTemporaryPassword>(
        `/companies/${companyId}/owner-account/temporary-password`,
    );
    return response.data;
}
