"use client";

import type { ReactNode } from "react";

import { PortalShell } from "@/components/portal/portal-shell";
import { RouteGuard } from "@/components/portal/route-guard";

export default function BorrowerLayout({ children }: { children: ReactNode }) {
    return (
        <RouteGuard allowedRoles={["borrower"]}>
            <div
                data-loanhub-borrower-scroll
                data-loanhub-scroll-root
                className="min-h-[100dvh] w-full min-w-0 overflow-x-hidden overflow-y-visible overscroll-y-auto touch-pan-y"
            >
                <PortalShell mode="borrower">{children}</PortalShell>
            </div>
        </RouteGuard>
    );
}
