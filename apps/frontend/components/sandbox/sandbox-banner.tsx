"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { api, isSandboxHostname } from "@/lib/api";
import { getDashboardRoute } from "@/lib/role-redirect";
import {
    StorageKeys,
    removeStoredValue,
    setStoredValue,
} from "@/lib/storage";
import { useAppSelector } from "@/store/hooks";
import {
    COMPANY_ROLES,
    PLATFORM_ROLES,
    type UserRole,
} from "@/types/auth";

const SANDBOX_PHONE = "12345678";
const SANDBOX_PASSWORD = "1234567890";
const ALL_SANDBOX_ROLES: readonly UserRole[] = [
    ...PLATFORM_ROLES,
    "borrower",
    ...COMPANY_ROLES,
];

function roleLabel(role: UserRole): string {
    return role
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function browserIsSandbox(): boolean {
    return typeof window !== "undefined" && isSandboxHostname(window.location.hostname);
}

export function SandboxAccessCard() {
    const { user, initialized } = useAppSelector((state) => state.auth);

    if (!browserIsSandbox() || !initialized || user) {
        return null;
    }

    return (
        <aside
            className="fixed bottom-4 right-4 z-[120] w-[min(94vw,390px)] rounded-2xl border border-amber-300 bg-amber-50 p-4 text-slate-950 shadow-2xl"
            aria-label="LoanHub public sandbox login"
        >
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-amber-800">
                        Public LoanHub sandbox
                    </p>
                    <p className="mt-1 text-sm font-semibold">
                        Use the shared demo account. Nothing here changes production data.
                    </p>
                </div>
                <span className="rounded-full bg-amber-200 px-2 py-1 text-[10px] font-black uppercase tracking-wide text-amber-950">
                    Demo
                </span>
            </div>

            <dl className="mt-3 grid grid-cols-[88px_1fr] gap-x-3 gap-y-2 rounded-xl border border-amber-200 bg-white/80 p-3 text-sm">
                <dt className="font-bold text-slate-600">Login</dt>
                <dd className="font-mono font-black tracking-wide">{SANDBOX_PHONE}</dd>
                <dt className="font-bold text-slate-600">Password</dt>
                <dd className="font-mono font-black tracking-wide">{SANDBOX_PASSWORD}</dd>
            </dl>

            <Link
                href="/login"
                className="mt-3 inline-flex w-full items-center justify-center rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-black text-white transition hover:bg-slate-800"
            >
                Sign in and test LoanHub
            </Link>

            <p className="mt-2 text-[11px] leading-5 text-slate-600">
                Includes 5 synthetic clients, writable records and role switching across the platform.
            </p>
        </aside>
    );
}

export function SandboxBanner() {
    const user = useAppSelector((state) => state.auth.user);
    const [switching, setSwitching] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const membershipByRole = useMemo(
        () => new Map(
            (user?.memberships ?? [])
                .filter((membership) => membership.is_active)
                .map((membership) => [membership.role, membership]),
        ),
        [user?.memberships],
    );

    if (!browserIsSandbox() || !user || user.phone !== SANDBOX_PHONE) {
        return null;
    }

    async function switchRole(nextRole: UserRole) {
        if (switching || nextRole === user?.role) {
            return;
        }

        setSwitching(true);
        setError(null);
        try {
            await api.post("/sandbox/switch-role", { role: nextRole });

            if (COMPANY_ROLES.includes(nextRole)) {
                const membership = membershipByRole.get(nextRole);
                if (!membership) {
                    throw new Error("The selected sandbox company role is not seeded");
                }
                setStoredValue(StorageKeys.activeCompanyId, membership.company_id);
                setStoredValue(StorageKeys.activeRole, nextRole);
            } else {
                removeStoredValue(StorageKeys.activeCompanyId);
                removeStoredValue(StorageKeys.activeRole);
            }

            window.location.assign(getDashboardRoute(nextRole));
        } catch (caught: unknown) {
            setError(
                caught instanceof Error
                    ? caught.message
                    : "Could not switch the sandbox role",
            );
            setSwitching(false);
        }
    }

    return (
        <aside
            className="fixed bottom-4 right-4 z-[120] w-[min(94vw,390px)] rounded-2xl border border-amber-300 bg-amber-50 p-4 text-slate-950 shadow-2xl"
            aria-label="LoanHub sandbox controls"
        >
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-amber-800">
                        Sandbox environment
                    </p>
                    <p className="mt-1 text-sm font-semibold">
                        Demo data only — production records are isolated.
                    </p>
                </div>
                <span className="rounded-full bg-amber-200 px-2 py-1 text-[10px] font-black uppercase tracking-wide text-amber-950">
                    Safe demo
                </span>
            </div>

            <label className="mt-3 block text-xs font-bold text-slate-700" htmlFor="sandbox-role">
                Test the system as
            </label>
            <select
                id="sandbox-role"
                value={user.role}
                disabled={switching}
                onChange={(event) => void switchRole(event.target.value as UserRole)}
                className="mt-1 w-full rounded-xl border border-amber-300 bg-white px-3 py-2 text-sm font-semibold outline-none focus:ring-2 focus:ring-amber-500 disabled:cursor-wait disabled:opacity-70"
            >
                {ALL_SANDBOX_ROLES.map((role) => (
                    <option key={role} value={role}>
                        {roleLabel(role)}
                    </option>
                ))}
            </select>

            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-700">
                <span>5 sample clients included</span>
                <span>New records are writable</span>
                <span>External live actions are blocked</span>
            </div>

            {error ? (
                <p className="mt-2 text-xs font-semibold text-red-700" role="alert">
                    {error}
                </p>
            ) : null}
        </aside>
    );
}
