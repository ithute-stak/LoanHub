import { api } from "@/lib/api";
import type { ImpersonationRequest, ImpersonationResponse, ImpersonationTarget } from "@/types/auth";

export async function listImpersonationTargets(search?: string): Promise<ImpersonationTarget[]> {
    const response = await api.get<ImpersonationTarget[]>("/auth/impersonation-targets", { params: { search } });
    return response.data;
}

export async function startImpersonation(payload: ImpersonationRequest): Promise<ImpersonationResponse> {
    const response = await api.post<ImpersonationResponse>("/auth/impersonate", payload);
    return response.data;
}


export type PasswordResetRequestResponse = {
    message: string;
    request_reference: string;
};

export async function requestPasswordReset(
    identifier: string,
): Promise<PasswordResetRequestResponse> {
    const response = await api.post<PasswordResetRequestResponse>(
        "/auth/password-reset-request",
        { identifier },
    );
    return response.data;
}


export async function changePassword(payload: {
    current_password: string;
    new_password: string;
}): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>(
        "/auth/change-password",
        payload,
    );
    return response.data;
}

export type WebSocketSessionResponse = {
    // Optional during rolling deployments against an older backend image.
    websocket_token?: string;
    expires_in: number;
};

export async function prepareWebSocketSession(
    companyId: string | null,
    clientId: string,
): Promise<WebSocketSessionResponse> {
    const response = await api.post<WebSocketSessionResponse>(
        "/auth/websocket-session",
        {
            company_id: companyId,
            client_id: clientId,
        },
    );

    return response.data;
}
