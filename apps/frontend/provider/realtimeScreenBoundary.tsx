"use client";

import type { ReactNode } from "react";

/**
 * Realtime events invalidate scoped data caches in RealtimeProvider and
 * AppDataProvider. Never key or remount the entire route in response to a
 * database commit: that destroys unfinished registration, payment, loan, and
 * CDAS form state (including when the user moves focus between fields).
 *
 * Retain this boundary as a compatibility wrapper for existing callers.
 */
export function RealtimeScreenBoundary({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
