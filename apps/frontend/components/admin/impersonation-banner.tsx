"use client";

import { LogOut, ShieldAlert } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { StorageKeys, getStoredJson, getStoredValue, removeStoredValue } from "@/lib/storage";
import { useAppDispatch } from "@/store/hooks";
import { replaceAuthSession } from "@/store/slices/authSlice";
import type { AuthUser } from "@/types/auth";
import { toast } from "@/utils/toast";

type SessionInfo = { expires_at: string; reason: string; target_name: string };

export function ImpersonationBanner() {
    const router = useRouter();
    const pathname = usePathname();
    const dispatch = useAppDispatch();
    const [info, setInfo] = useState<SessionInfo | null>(null);
    useEffect(() => {
        const timer = window.setTimeout(() => {
            setInfo(getStoredJson<SessionInfo>(StorageKeys.impersonation));
        }, 0);
        return () => window.clearTimeout(timer);
    }, [pathname]);
    if (!info) return null;

    function stop() {
        const token = getStoredValue(StorageKeys.originalAdminToken);
        const user = getStoredJson<AuthUser>(StorageKeys.originalAdminUser);
        if (!token || !user) {
            removeStoredValue(StorageKeys.impersonation);
            setInfo(null);
            router.replace("/login");
            return;
        }
        dispatch(replaceAuthSession({ accessToken: token, user }));
        [StorageKeys.originalAdminToken, StorageKeys.originalAdminUser, StorageKeys.impersonation, StorageKeys.activeCompanyId].forEach(removeStoredValue);
        setInfo(null);
        toast.success("Returned to platform-owner session");
        router.replace("/superadmin");
        router.refresh();
    }

    return <div className="fixed inset-x-0 top-0 z-[120] flex min-h-10 items-center justify-center gap-3 bg-amber-500 px-3 py-2 text-center text-xs font-black text-slate-950 shadow-lg"><ShieldAlert className="h-4 w-4" /><span>Audited role-switch session: {info.target_name}. Expires {new Date(info.expires_at).toLocaleTimeString()}.</span><button type="button" onClick={stop} className="inline-flex items-center gap-1 rounded-lg bg-slate-950 px-2 py-1 text-white"><LogOut className="h-3 w-3" />Return</button></div>;
}
