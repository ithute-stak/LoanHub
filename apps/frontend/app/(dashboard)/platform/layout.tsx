"use client";

import type { ReactNode } from "react";
import { PlatformShell } from "@/components/dashboard/platform-shell";
import { RouteGuard } from "@/components/portal/route-guard";

const STAFF_ROLES = ["platform_admin", "platform_finance", "platform_support", "platform_auditor", "platform_operations", "platform_compliance"] as const;

export default function PlatformLayout({ children }: { children: ReactNode }) {
    return <RouteGuard allowedRoles={STAFF_ROLES}><PlatformShell>{children}</PlatformShell></RouteGuard>;
}
