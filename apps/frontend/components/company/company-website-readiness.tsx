"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, ShieldCheck } from "lucide-react";

import { getCompanyWebsiteReadiness, type CompanyWebsiteReadiness } from "@/api/companyWebsite";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";


export function CompanyWebsiteReadinessPanel() {
    const [readiness, setReadiness] = useState<CompanyWebsiteReadiness | null>(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            setReadiness(await getCompanyWebsiteReadiness());
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not evaluate website readiness."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void load(); }, [load]);

    if (loading) {
        return (
            <section className="flex min-h-24 items-center justify-center rounded-3xl border bg-card shadow-sm">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
            </section>
        );
    }
    if (!readiness) return null;

    const failedRequired = readiness.checks.filter((check) => check.required && !check.passed);

    return (
        <section className="rounded-3xl border bg-card p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-start gap-3">
                    <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${readiness.ready_to_publish ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-amber-500/10 text-amber-700 dark:text-amber-300"}`}>
                        {readiness.ready_to_publish ? <ShieldCheck className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
                    </span>
                    <div>
                        <div className="flex flex-wrap items-center gap-2">
                            <h2 className="font-black">Website quality & publish readiness</h2>
                            <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-black text-primary">{readiness.score}/100</span>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            {readiness.ready_to_publish
                                ? "Required publishing checks are complete. Optional quality checks can still improve the public site."
                                : `${failedRequired.length} required check${failedRequired.length === 1 ? "" : "s"} must be completed before publishing.`}
                        </p>
                    </div>
                </div>
                <button type="button" onClick={() => void load()} className="inline-flex h-9 items-center justify-center gap-2 rounded-xl border px-3 text-xs font-black hover:bg-muted">
                    <RefreshCw className="h-3.5 w-3.5" /> Recheck
                </button>
            </div>

            <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {readiness.checks.map((check) => (
                    <article key={check.key} className="rounded-2xl border bg-background p-3">
                        <div className="flex items-start gap-2">
                            {check.passed
                                ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                                : <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${check.required ? "text-destructive" : "text-amber-600"}`} />}
                            <div className="min-w-0">
                                <p className="text-xs font-black">{check.label}</p>
                                <p className="mt-1 text-[11px] leading-4 text-muted-foreground">{check.detail}</p>
                                <p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{check.required ? "Required" : "Quality"} · {check.weight} points</p>
                            </div>
                        </div>
                    </article>
                ))}
            </div>
        </section>
    );
}
