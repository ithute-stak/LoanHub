import {
    CheckCircle2,
    Clock3,
    XCircle,
} from "lucide-react";

import {
    normalizeCompanyStatus,
} from "../_lib/company-utils";

export function CompanyStatusBadge({
                                       status,
                                   }: {
    status: unknown;
}) {
    const normalized =
        normalizeCompanyStatus(status);

    if (normalized === "approved") {
        return (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-1 text-xs font-bold text-green-700 dark:bg-green-950/40 dark:text-green-400">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Approved
            </span>
        );
    }

    if (normalized === "pending") {
        return (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">
                <Clock3 className="h-3.5 w-3.5" />
                Pending
            </span>
        );
    }

    if (normalized === "rejected") {
        return (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700 dark:bg-red-950/40 dark:text-red-400">
                <XCircle className="h-3.5 w-3.5" />
                Rejected
            </span>
        );
    }

    return (
        <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-bold text-muted-foreground">
            {String(status || "Unknown")}
        </span>
    );
}

export function CompanyActivityBadge({
                                         active,
                                     }: {
    active: boolean;
}) {
    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${
                active
                    ? "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400"
                    : "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"
            }`}
        >
            <span
                className={`h-1.5 w-1.5 rounded-full ${
                    active
                        ? "bg-green-500"
                        : "bg-red-500"
                }`}
            />

            {active
                ? "Active"
                : "Inactive"}
        </span>
    );
}