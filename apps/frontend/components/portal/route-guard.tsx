"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getDashboardRoute } from "@/lib/role-redirect";
import { useAppSelector } from "@/store/hooks";
import { isCompanyRole, type UserRole } from "@/types/auth";

export function RouteGuard({
    children,
    allowedRoles,
    allowCompanyRoles = false,
}: {
    children: ReactNode;
    allowedRoles?: readonly UserRole[];
    allowCompanyRoles?: boolean;
}) {
    const router = useRouter();
    const { user, initialized } = useAppSelector((state) => state.auth);
    const authorized = Boolean(
        user &&
            (allowCompanyRoles
                ? isCompanyRole(user.role)
                : !allowedRoles || allowedRoles.includes(user.role)),
    );

    useEffect(() => {
        if (!initialized) return;
        if (!user) {
            router.replace("/login");
            return;
        }
        if (!authorized) {
            router.replace(getDashboardRoute(user.role));
        }
    }, [authorized, initialized, router, user]);

    if (!initialized || !authorized) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-background">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return children;
}
