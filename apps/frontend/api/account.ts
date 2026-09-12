import { api } from "@/lib/api";
import type { AuthUser } from "@/types/auth";
import type { CompanyClientNationalIdChangeRequest } from "@/types/companyClient";
import type {
    AccountActivity,
    AccountContactUpdate,
    AccountOverview,
    AccountProfileResult,
    AccountProfileUpdate,
    AccountSession,
    AccountSessionAction,
    ChangePasswordPayload,
    ChangePasswordResult,
} from "@/types/account";

export async function getAccountOverview(): Promise<AccountOverview> {
    const response = await api.get<AccountOverview>("/auth/account");
    return response.data;
}

export async function updateAccountContact(payload: AccountContactUpdate): Promise<AuthUser> {
    const response = await api.patch<AuthUser>("/auth/account/contact", payload);
    return response.data;
}

export async function updateAccountProfile(payload: AccountProfileUpdate): Promise<AccountProfileResult> {
    const response = await api.put<AccountProfileResult>("/auth/account/profile", payload);
    return response.data;
}

export async function changeAccountPassword(payload: ChangePasswordPayload): Promise<ChangePasswordResult> {
    const response = await api.post<ChangePasswordResult>("/auth/account/password", payload);
    return response.data;
}

export async function listAccountSessions(): Promise<AccountSession[]> {
    const response = await api.get<AccountSession[]>("/auth/account/sessions");
    return response.data;
}

export async function revokeAccountSession(sessionId: string): Promise<AccountSessionAction> {
    const response = await api.delete<AccountSessionAction>(`/auth/account/sessions/${sessionId}`);
    return response.data;
}

export async function revokeOtherAccountSessions(): Promise<AccountSessionAction> {
    const response = await api.post<AccountSessionAction>("/auth/account/sessions/revoke-others");
    return response.data;
}

export async function revokeAllAccountSessions(): Promise<AccountSessionAction> {
    const response = await api.post<AccountSessionAction>("/auth/account/sessions/revoke-all");
    return response.data;
}

export async function listAccountActivity(limit = 30): Promise<AccountActivity[]> {
    const response = await api.get<AccountActivity[]>("/auth/account/activity", { params: { limit } });
    return response.data;
}

export async function listMyNationalIdChangeRequests(): Promise<CompanyClientNationalIdChangeRequest[]> {
    const response = await api.get<CompanyClientNationalIdChangeRequest[]>(
        "/auth/account/national-id-change-requests",
    );
    return response.data;
}

export async function decideMyNationalIdChangeRequest(
    requestId: string,
    payload: { approve: boolean; reason?: string | null },
): Promise<CompanyClientNationalIdChangeRequest> {
    const response = await api.post<CompanyClientNationalIdChangeRequest>(
        `/auth/account/national-id-change-requests/${requestId}/decision`,
        payload,
    );
    return response.data;
}
