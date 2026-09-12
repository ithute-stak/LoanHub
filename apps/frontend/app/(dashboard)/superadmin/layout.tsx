"use client";

import type { ReactNode } from "react";

import { SuperAdminShell } from "@/components/dashboard/superadmin-shell";
import { RouteGuard } from "@/components/portal/route-guard";

export default function SuperAdminLayout({ children }: { children: ReactNode }) {
    return (
        <RouteGuard allowedRoles={["superadmin"]}>
            <SuperAdminShell>{children}</SuperAdminShell>
        </RouteGuard>
    );
}
