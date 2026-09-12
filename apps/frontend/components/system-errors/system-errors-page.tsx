"use client";


import { Input } from "@/components/ui/input";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { Textarea } from "@/components/ui/textarea";
import {
    AlertTriangle,
    CheckCircle2,
    Eye,
    Loader2,
    RefreshCcw,
    RotateCcw,
    Search,
    ServerCrash,
    ShieldAlert,
} from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import {
    type FormEvent,
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";
import { toast } from "@/utils/toast";

import {
    listSystemErrors,
    reopenSystemError,
    resolveSystemError,
} from "@/api/systemErrors";
import { Button } from "@/components/ui/button";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { LoadingButton } from "@/components/ui/loading-button";
import type { SystemErrorLog } from "@/types/systemError";
import { getErrorMessage } from "@/utils/apiError";

export function SystemErrorsPage() {
    const [items, setItems] = useState<SystemErrorLog[]>([]);
    const [unresolvedCount, setUnresolvedCount] = useState(0);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [unresolvedOnly, setUnresolvedOnly] = useState(true);
    const [selected, setSelected] = useState<SystemErrorLog | null>(null);
    const [resolution, setResolution] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await listSystemErrors({
                page: 1,
                page_size: 100,
                unresolved_only: unresolvedOnly,
                search: search.trim() || undefined,
            });
            setItems(result.items);
            setTotal(result.total);
            setUnresolvedCount(result.unresolved_count);
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "Could not load system errors."));
        } finally {
            setLoading(false);
        }
    }, [search, unresolvedOnly]);

    useEffect(() => {
        const timeout = window.setTimeout(() => void load(), 250);
        return () => window.clearTimeout(timeout);
    }, [load]);

    const criticalCount = useMemo(
        () => items.filter((item) => item.severity === "critical").length,
        [items],
    );

    async function resolve(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!selected) return;
        setSubmitting(true);
        try {
            const updated = await resolveSystemError(selected.id, resolution);
            setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
            setSelected(updated);
            setResolution("");
            setUnresolvedCount((current) => Math.max(0, current - 1));
            toast.success("System error marked as resolved.");
        } catch (requestError: unknown) {
            toast.error(getErrorMessage(requestError, "Could not resolve the error."));
        } finally {
            setSubmitting(false);
        }
    }

    async function reopen(item: SystemErrorLog) {
        try {
            const updated = await reopenSystemError(item.id);
            setItems((current) => current.map((entry) => entry.id === updated.id ? updated : entry));
            setSelected(updated);
            setUnresolvedCount((current) => current + 1);
            toast.success("System error reopened.");
        } catch (requestError: unknown) {
            toast.error(getErrorMessage(requestError, "Could not reopen the error."));
        }
    }

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-red-500/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.16em] text-red-600">Platform observability</p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight">System error centre</h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Automatically group exceptions by fingerprint, inspect stack traces and document every resolution.
                        </p>
                    </div>
                    <button type="button" onClick={() => void load()} disabled={loading} className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50">
                        <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                        Refresh errors
                    </button>
                </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-3">
                <Metric icon={ShieldAlert} label="Unresolved" value={unresolvedCount} tone="red" />
                <Metric icon={ServerCrash} label="Visible records" value={total} tone="amber" />
                <Metric icon={AlertTriangle} label="Critical on page" value={criticalCount} tone="red" />
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="grid gap-3 border-b p-4 sm:grid-cols-[1fr_auto] sm:p-5">
                    <SuggestionSearch
                        value={search}
                        onValueChange={setSearch}
                        suggestions={items.map((item) => ({
                            value: item.path,
                            label: item.path,
                            description: `${item.error_type} · ${item.message}`,
                            keywords: [item.id, item.request_id ?? "", item.fingerprint, item.method ?? "", item.severity, String(item.status_code)],
                        }))}
                        placeholder="Type an endpoint, exception, fingerprint or request ID..."
                        suggestionLabel="System errors"
                        emptyMessage="No loaded error matches that text."
                    />
                    <label className="flex h-11 items-center gap-2 rounded-xl border px-4 text-sm font-black">
                        <Input type="checkbox" checked={unresolvedOnly} onChange={(event) => setUnresolvedOnly(event.target.checked)} />
                        Unresolved only
                    </label>
                </div>

                {error && <div className="border-b border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[1050px] text-sm">
                        <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                            <tr>
                                <th className="px-5 py-4">Error</th>
                                <th className="px-4 py-4">Endpoint</th>
                                <th className="px-4 py-4">Occurrences</th>
                                <th className="px-4 py-4">Last seen</th>
                                <th className="px-4 py-4">Status</th>
                                <th className="px-5 py-4 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading && items.length === 0 ? (
                                <tr><td colSpan={6} className="py-20 text-center"><Loader2 className="mx-auto h-7 w-7 animate-spin text-primary" /></td></tr>
                            ) : items.map((item) => (
                                <tr key={item.id} className="border-t hover:bg-muted/30">
                                    <td className="px-5 py-4">
                                        <div className="flex items-start gap-3">
                                            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"><AlertTriangle className="h-5 w-5" /></span>
                                            <div className="max-w-md">
                                                <p className="font-black">{item.error_type}</p>
                                                <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{item.message}</p>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-4 py-4"><p className="font-bold">{item.method} {item.path}</p><p className="mt-1 text-xs text-muted-foreground">HTTP {item.status_code}</p></td>
                                    <td className="px-4 py-4 text-xl font-black">{item.occurrence_count}</td>
                                    <td className="px-4 py-4"><p className="font-bold">{formatDistanceToNow(new Date(item.last_seen_at), { addSuffix: true })}</p><p className="mt-1 text-xs text-muted-foreground">{format(new Date(item.last_seen_at), "dd MMM HH:mm")}</p></td>
                                    <td className="px-4 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-black ${item.is_resolved ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{item.is_resolved ? "Resolved" : "Open"}</span></td>
                                    <td className="px-5 py-4 text-right"><button type="button" onClick={() => { setSelected(item); setResolution(""); }} className="inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-black hover:border-primary hover:text-primary"><Eye className="h-4 w-4" />Inspect</button></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {!loading && items.length === 0 && <div className="flex min-h-64 flex-col items-center justify-center p-8 text-center"><CheckCircle2 className="h-12 w-12 text-green-600" /><h2 className="mt-4 font-black">No matching system errors</h2><p className="mt-1 text-sm text-muted-foreground">The selected error queue is clear.</p></div>}
            </section>

            <CustomDialog open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)} title="System error investigation" description="Request, stack trace and resolution record." contentClassName="max-w-5xl">
                <div className="p-6 sm:p-8">
                    {selected && <div className="space-y-5">
                        <div className="grid gap-3 sm:grid-cols-4">
                            <Detail label="Exception" value={selected.error_type} />
                            <Detail label="Request ID" value={selected.request_id ?? "Not available"} />
                            <Detail label="Occurrences" value={selected.occurrence_count.toString()} />
                            <Detail label="Environment" value={selected.environment ?? "Unknown"} />
                        </div>
                        <section className="rounded-2xl border p-4"><h3 className="font-black">Message</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{selected.message}</p></section>
                        <section className="overflow-hidden rounded-2xl border"><h3 className="border-b bg-muted/60 px-4 py-3 font-black">Stack trace</h3><pre className="max-h-96 overflow-auto whitespace-pre-wrap p-4 text-xs leading-5">{selected.stack_trace ?? "No stack trace was captured."}</pre></section>
                        {selected.is_resolved ? <div className="rounded-2xl border border-green-200 bg-green-50 p-4 text-sm text-green-800"><p className="font-black">Resolution</p><p className="mt-1">{selected.resolution_notes ?? "Resolved without notes."}</p><Button type="button" variant="outline" onClick={() => void reopen(selected)} className="mt-4 border-green-300"><RotateCcw className="h-4 w-4" />Reopen</Button></div> : <form onSubmit={resolve} className="rounded-2xl border p-4"><label><span className="mb-2 block text-sm font-black">Resolution notes</span><Textarea required minLength={2} value={resolution} onChange={(event) => setResolution(event.target.value)} className="min-h-28" placeholder="Describe the root cause, correction and prevention steps." /></label><DialogFooter className="mx-0 mb-0 mt-4"><LoadingButton type="submit" loading={submitting} loadingText="Marking resolved…"><CheckCircle2 className="h-4 w-4" />Mark resolved</LoadingButton></DialogFooter></form>}
                    </div>}
                </div>
            </CustomDialog>
        </main>
    );
}

function Metric({ icon: Icon, label, value, tone }: { icon: typeof ShieldAlert; label: string; value: number; tone: "red" | "amber" }) { return <article className="rounded-3xl border bg-card p-5 shadow-sm"><div className="flex items-center justify-between"><div><p className="text-sm font-bold text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-black">{value}</p></div><div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${tone === "red" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}><Icon className="h-5 w-5" /></div></div></article>; }
function Detail({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-muted/60 p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 break-all font-black">{value}</p></div>; }
