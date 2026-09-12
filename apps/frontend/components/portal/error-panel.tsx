import { AlertCircle, RefreshCw } from "lucide-react";

export function ErrorPanel({
    message,
    onRetry,
}: {
    message: string;
    onRetry?: () => void;
}) {
    return (
        <div className="flex flex-col gap-4 rounded-3xl border border-red-200 bg-red-50 p-5 text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
                <div>
                    <p className="font-bold">Data could not be loaded</p>
                    <p className="mt-1 text-sm">{message}</p>
                </div>
            </div>
            {onRetry && (
                <button
                    type="button"
                    onClick={onRetry}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-bold"
                >
                    <RefreshCw className="h-4 w-4" />
                    Retry
                </button>
            )}
        </div>
    );
}
