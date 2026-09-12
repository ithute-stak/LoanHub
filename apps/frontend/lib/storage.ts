export const StorageKeys = {
    hasSeenOnboarding: "has_seen_onboarding",
    accessToken: "access_token",
    authUser: "user",
    activeCompanyId: "active_company_id",
    activeRole: "active_role",
    originalAdminToken: "original_admin_access_token",
    originalAdminUser: "original_admin_user",
    impersonation: "impersonation_session",
} as const;

function canUseStorage(): boolean {
    return typeof window !== "undefined";
}

export function getStoredValue(key: string): string | null {
    if (!canUseStorage()) {
        return null;
    }
    return window.localStorage.getItem(key);
}

export function setStoredValue(key: string, value: string): void {
    if (!canUseStorage()) {
        return;
    }
    window.localStorage.setItem(key, value);
}

export function removeStoredValue(key: string): void {
    if (!canUseStorage()) {
        return;
    }
    window.localStorage.removeItem(key);
}

export function getStoredJson<T>(key: string): T | null {
    const raw = getStoredValue(key);
    if (!raw) {
        return null;
    }
    try {
        return JSON.parse(raw) as T;
    } catch {
        removeStoredValue(key);
        return null;
    }
}

export function setStoredJson<T>(key: string, value: T): void {
    setStoredValue(key, JSON.stringify(value));
}

export function clearAuthStorage(): void {
    removeStoredValue(StorageKeys.accessToken);
    removeStoredValue(StorageKeys.authUser);
    removeStoredValue(StorageKeys.activeCompanyId);
    removeStoredValue(StorageKeys.activeRole);
    removeStoredValue(StorageKeys.originalAdminToken);
    removeStoredValue(StorageKeys.originalAdminUser);
    removeStoredValue(StorageKeys.impersonation);
}
