"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarClock, Landmark } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";

const ROOT_PATH = "/company/expense-management";
const HISTORICAL_PATH = "/company/expense-management/backdated-opening";

export default function ExpenseManagementLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { activeRole } = useTenant();
  const canUseHistoricalCorrection = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES)
    || activeRole === "finance_officer";

  return (
    <div className="space-y-4">
      <nav
        aria-label="Accounting and expense management"
        className="flex flex-wrap items-center gap-2 rounded-2xl border border-border/70 bg-card/80 p-2 shadow-sm"
      >
        <Button
          asChild
          size="sm"
          variant={pathname === ROOT_PATH ? "secondary" : "ghost"}
        >
          <Link href={ROOT_PATH}>
            <Landmark className="h-4 w-4" />
            Accounting & expenses
          </Link>
        </Button>
        {canUseHistoricalCorrection ? (
          <Button
            asChild
            size="sm"
            variant={pathname === HISTORICAL_PATH ? "secondary" : "ghost"}
          >
            <Link href={HISTORICAL_PATH}>
              <CalendarClock className="h-4 w-4" />
              Back-dated opening balance
            </Link>
          </Button>
        ) : null}
      </nav>
      {children}
    </div>
  );
}
