"use client";

import { useEffect, useState } from "react";
import { useAppSelector } from "@/store/hooks";

export function AuthUserChip() {
    const user = useAppSelector((state) => state.auth.user);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        const timer = window.setTimeout(() => setMounted(true), 0);
        return () => window.clearTimeout(timer);
    }, []);

    if (!mounted) {
        return (
            <div className="hidden h-[58px] w-[220px] rounded-2xl border border-border bg-background md:flex" />
        );
    }

    const initials =
        user?.phone?.substring(0, 2).toUpperCase() ??
        user?.role?.substring(0, 2).toUpperCase() ??
        "U";

    return (
        <div className="hidden items-center gap-3 rounded-2xl border border-border bg-background px-4 py-2 shadow-sm md:flex">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-sm font-black text-primary-foreground">
                {initials}
            </div>

            <div>
                <p className="max-w-[160px] truncate text-sm font-black">
                    {user?.email ?? user?.phone ?? "Unknown User"}
                </p>

                <p className="text-xs capitalize text-muted-foreground">
                    {user?.role?.replaceAll("_", " ") ?? "System User"}
                </p>
            </div>
        </div>
    );
}