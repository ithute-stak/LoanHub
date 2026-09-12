"use client";

import type { ReactNode } from "react";

import { CompanyStatusGate } from "@/components/portal/company-status-gate";
import { PortalShell } from "@/components/portal/portal-shell";
import { RouteGuard } from "@/components/portal/route-guard";

export default function CompanyLayout({ children }: { children: ReactNode }) {
    return (
        <RouteGuard allowCompanyRoles>
            <CompanyStatusGate>
                <PortalShell mode="company">{children}</PortalShell>
            </CompanyStatusGate>
        </RouteGuard>
    );
}
