import {
    CheckCircle2,
    XCircle,
} from "lucide-react";

export function BranchStatusBadge({
    active,
}: {
    active: boolean;
}) {
    return active ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-1 text-xs font-bold text-green-700 dark:bg-green-950/40 dark:text-green-400">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Active
        </span>
    ) : (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700 dark:bg-red-950/40 dark:text-red-400">
            <XCircle className="h-3.5 w-3.5" />
            Inactive
        </span>
    );
}
