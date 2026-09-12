import { titleCase } from "@/lib/format";

const GOOD = new Set(["active", "approved", "accepted", "succeeded", "paid", "unlocked", "completed"]);
const BAD = new Set(["failed", "rejected", "defaulted", "cancelled", "inactive", "overdue", "expired"]);
const WARNING = new Set(["pending", "processing", "submitted", "open", "offered", "under_review", "partially_paid"]);

export function StatusBadge({ value }: { value: string | null | undefined }) {
    const normalized = String(value ?? "unknown").toLowerCase();
    const className = GOOD.has(normalized)
        ? "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400"
        : BAD.has(normalized)
          ? "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"
          : WARNING.has(normalized)
            ? "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
            : "bg-muted text-muted-foreground";

    return (
        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${className}`}>
            {titleCase(normalized)}
        </span>
    );
}
