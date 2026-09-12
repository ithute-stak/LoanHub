import { Loader2 } from "lucide-react";

export function LoadingPanel({ label = "Loading data..." }: { label?: string }) {
    return (
        <div className="flex min-h-64 items-center justify-center rounded-3xl border bg-card">
            <div className="flex flex-col items-center gap-3 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm font-semibold">{label}</p>
            </div>
        </div>
    );
}
