import { Eye, EyeOff, Power, PowerOff } from "lucide-react";

export function PlanActivityBadge({ active }: { active: boolean }) {
    return (
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${
            active
                ? "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400"
                : "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"
        }`}>
            {active ? <Power className="h-3.5 w-3.5" /> : <PowerOff className="h-3.5 w-3.5" />}
            {active ? "Active" : "Inactive"}
        </span>
    );
}

export function PlanVisibilityBadge({ isPublic }: { isPublic: boolean }) {
    return (
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${
            isPublic
                ? "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400"
                : "bg-muted text-muted-foreground"
        }`}>
            {isPublic ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
            {isPublic ? "Public" : "Private"}
        </span>
    );
}
