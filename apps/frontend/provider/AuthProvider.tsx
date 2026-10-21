"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { useAppDispatch } from "@/store/hooks";
import { bootstrapAuth } from "@/store/slices/authSlice";
import { refreshAccessToken } from "@/lib/api";
import { getStoredValue, StorageKeys } from "@/lib/storage";

// Refresh ahead of expiry without navigating, remounting children or changing
// the visible loading state. Request interceptor handles 401s as a fallback.
const RENEW_BEFORE_MS = 2 * 60 * 1000;
const CHECK_EVERY_MS = 30 * 1000;

function tokenExpiryMs(token: string): number | null {
    try {
        const payload = token.split(".")[1];
        if (!payload) return null;
        const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as { exp?: unknown };
        return typeof decoded.exp === "number" ? decoded.exp * 1000 : null;
    } catch {
        return null;
    }
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const dispatch = useAppDispatch();
    const started = useRef(false);

    useEffect(() => {
        if (started.current) return;
        started.current = true;
        const timer = window.setTimeout(() => void dispatch(bootstrapAuth()), 0);
        return () => window.clearTimeout(timer);
    }, [dispatch]);

    useEffect(() => {
        const renewIfNeeded = () => {
            if (document.visibilityState === "hidden" || !navigator.onLine) return;
            const token = getStoredValue(StorageKeys.accessToken);
            if (!token) return;
            const expiresAt = tokenExpiryMs(token);
            if (expiresAt === null || expiresAt - Date.now() > RENEW_BEFORE_MS) return;
            // Never clear form state, show a spinner or navigate as a side effect.
            // A rejected refresh is handled on the next authenticated action.
            void refreshAccessToken().catch(() => undefined);
        };

        const interval = window.setInterval(renewIfNeeded, CHECK_EVERY_MS);
        document.addEventListener("visibilitychange", renewIfNeeded);
        window.addEventListener("online", renewIfNeeded);
        renewIfNeeded();
        return () => {
            window.clearInterval(interval);
            document.removeEventListener("visibilitychange", renewIfNeeded);
            window.removeEventListener("online", renewIfNeeded);
        };
    }, []);

    return children;
}
