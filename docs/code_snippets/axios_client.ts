import axios, {
    AxiosError,
    type InternalAxiosRequestConfig,
} from "axios";

import {
    StorageKeys,
    clearAuthStorage,
    getStoredJson,
    getStoredValue,
    removeStoredValue,
    setStoredValue,
} from "@/lib/storage";
import type { AuthUser, RefreshResponse } from "@/types/auth";

export const api = axios.create({
    baseURL:
        process.env.NEXT_PUBLIC_API_URL ??
        "http://localhost:8000/api/v1",
    withCredentials: true,
});

type RetryableRequest = InternalAxiosRequestConfig & {
    _retry?: boolean;
};

let refreshPromise: Promise<string> | null = null;

function restoreOriginalPlatformSession(): boolean {
    const impersonation = getStoredValue(StorageKeys.impersonation);
    const originalToken = getStoredValue(StorageKeys.originalAdminToken);
    const originalUser = getStoredJson<AuthUser>(StorageKeys.originalAdminUser);

    if (!impersonation || !originalToken || !originalUser) {
        return false;
    }

    setStoredValue(StorageKeys.accessToken, originalToken);
    setStoredValue(StorageKeys.authUser, JSON.stringify(originalUser));
    removeStoredValue(StorageKeys.originalAdminToken);
    removeStoredValue(StorageKeys.originalAdminUser);
    removeStoredValue(StorageKeys.impersonation);
    removeStoredValue(StorageKeys.activeCompanyId);

    if (typeof window !== "undefined") {
        window.location.assign("/superadmin?reason=impersonation-ended");
    }

    return true;
}

function refreshAccessToken(): Promise<string> {
    if (!refreshPromise) {
        refreshPromise = api
            .post<RefreshResponse>("/auth/refresh")
            .then((response) => {
                const token = response.data.access_token;
                setStoredValue(StorageKeys.accessToken, token);
                return token;
            })
            .finally(() => {
                refreshPromise = null;
            });
    }
    return refreshPromise;
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = getStoredValue(StorageKeys.accessToken);
    const activeCompanyId = getStoredValue(StorageKeys.activeCompanyId);

    // Never force application/json for FormData. The browser must generate the
    // multipart boundary; overriding it makes FastAPI report every form field
    // as missing even when the FormData object contains those values.
    if (
        typeof FormData !== "undefined" &&
        config.data instanceof FormData
    ) {
        config.headers.delete("Content-Type");
    }

    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    if (activeCompanyId) {
        config.headers["X-Company-ID"] = activeCompanyId;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as RetryableRequest | undefined;
        if (!originalRequest) {
            return Promise.reject(error);
        }

        const isUnauthorized = error.response?.status === 401;
        const url = originalRequest.url ?? "";
        const isAuthRequest =
            url.includes("/auth/login") ||
            url.includes("/auth/refresh") ||
            url.includes("/auth/logout");

        if (isUnauthorized && !originalRequest._retry && !isAuthRequest) {
            if (restoreOriginalPlatformSession()) {
                return Promise.reject(error);
            }

            originalRequest._retry = true;
            try {
                const token = await refreshAccessToken();
                originalRequest.headers.Authorization = `Bearer ${token}`;
                return api(originalRequest);
            } catch (refreshError: unknown) {
                clearAuthStorage();
                if (typeof window !== "undefined") {
                    const onLoginPage = window.location.pathname === "/login";
                    if (!onLoginPage) {
                        window.location.assign("/login?reason=session-expired");
                    }
                }
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    },
);
