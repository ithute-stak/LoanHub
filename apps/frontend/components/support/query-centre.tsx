"use client";


import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/ui/native-select";
import { CheckCircle2, Clock3, Loader2, MessageSquarePlus, RefreshCcw, Send, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { professionalApi } from "@/api/professional";
import type { PlatformSuggestionCreate } from "@/types/professional";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { formatDateTime, titleCase } from "@/lib/format";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type QueryItem = {
    id: string;
    reference: string;
    title: string;
    category: string;
    description: string;
    priority: string;
    status: string;
    platform_response: string | null;
    company_id: string | null;
    submitted_by_user_id: string | null;
    created_at: string;
    updated_at: string;
};

export function QueryCentre({ platform = false }: { platform?: boolean }) {
    const [rows, setRows] = useState<QueryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [open, setOpen] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [form, setForm] = useState<PlatformSuggestionCreate>({ title: "", category: "support_query", priority: "normal", description: "" });

    const load = useCallback(async () => {
        setLoading(true);
        try { setRows(await professionalApi.queries()); }
        catch (error) { toast.error(getErrorMessage(error, "Could not load user queries")); }
        finally { setLoading(false); }
    }, []);
    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    const openCount = useMemo(() => rows.filter((item) => !["completed", "closed", "rejected"].includes(item.status)).length, [rows]);

    async function submit() {
        setSubmitting(true);
        try {
            await professionalApi.submitQuery(form);
            toast.success("Your query was sent to the platform owner.");
            setForm({ title: "", category: "support_query", priority: "normal", description: "" });
            setOpen(false);
            await load();
        } catch (error) { toast.error(getErrorMessage(error, "Could not submit the query")); }
        finally { setSubmitting(false); }
    }

    async function respond(item: QueryItem, status: string, response: string) {
        try {
            await professionalApi.updateQuery(item.id, { status, platform_response: response || null });
            toast.success("Query updated.");
            await load();
        } catch (error) { toast.error(getErrorMessage(error, "Could not update the query")); }
    }

    return <main className="space-y-6 pb-24">
        <section className="rounded-3xl border bg-card p-6 shadow-sm md:p-8"><div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs font-black uppercase tracking-[.16em] text-primary">Communication with the platform owner</p><h1 className="mt-2 text-3xl font-black">{platform ? "User queries and suggestions" : "Support query centre"}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{platform ? "Review questions, operational problems and functionality suggestions submitted by borrowers and company users." : "Report a problem, ask how the system works, or suggest functionality. Your reference keeps the conversation traceable."}</p></div><div className="flex gap-2"><button type="button" onClick={() => void load()} disabled={loading} className="inline-flex h-11 items-center gap-2 rounded-xl border px-4 text-sm font-black"><RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</button>{!platform && <button type="button" onClick={() => setOpen(true)} className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground"><MessageSquarePlus className="h-4 w-4" />Submit query</button>}</div></div></section>
        <section className="grid gap-4 sm:grid-cols-3"><Summary icon={MessageSquarePlus} label="Total" value={rows.length} /><Summary icon={Clock3} label="Open" value={openCount} /><Summary icon={CheckCircle2} label="Completed" value={rows.length - openCount} /></section>
        <section className="grid gap-4">{rows.map((item) => <QueryCard key={item.id} item={item} platform={platform} onRespond={respond} />)}{!loading && rows.length === 0 && <div className="rounded-3xl border bg-card p-14 text-center"><ShieldAlert className="mx-auto h-10 w-10 text-muted-foreground" /><p className="mt-4 font-black">No queries have been submitted.</p></div>}</section>
        <CustomDialog open={open} onOpenChange={(value) => !submitting && setOpen(value)} title="Submit a query to the platform owner" contentClassName="sm:max-w-xl">
            <div className="space-y-4 p-5 sm:p-6"><Field label="Title"><Input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} placeholder="Briefly describe the issue or request" className="input" /></Field><div className="grid gap-4 sm:grid-cols-2"><Field label="Category"><NativeSelect value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value as PlatformSuggestionCreate["category"] }))} className="input"><option value="support_query">Support question</option><option value="feature_request">Functionality suggestion</option><option value="payment_issue">Payment issue</option><option value="technical_issue">Technical problem</option><option value="training">Training request</option></NativeSelect></Field><Field label="Priority"><NativeSelect value={form.priority} onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value as PlatformSuggestionCreate["priority"] }))} className="input"><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></NativeSelect></Field></div><Field label="Details"><Textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} placeholder="Include the page, what you were doing, what happened, and the result you expected." className="min-h-36 w-full rounded-xl border bg-background p-3 text-sm" /></Field></div>
            <div className="flex flex-col-reverse gap-3 border-t p-5 sm:flex-row sm:justify-end"><button type="button" onClick={() => setOpen(false)} disabled={submitting} className="h-11 rounded-xl border px-5 text-sm font-black">Cancel</button><button type="button" onClick={() => void submit()} disabled={submitting || form.title.trim().length < 4 || form.description.trim().length < 10} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground disabled:opacity-50">{submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}Send query</button></div>
        </CustomDialog>
    </main>;
}

function QueryCard({ item, platform, onRespond }: { item: QueryItem; platform: boolean; onRespond: (item: QueryItem, status: string, response: string) => Promise<void> }) {
    const [status, setStatus] = useState(item.status);
    const [response, setResponse] = useState(item.platform_response ?? "");
    const [saving, setSaving] = useState(false);
    return <article className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs font-black text-primary">{item.reference}</span><span className="rounded-full bg-muted px-2.5 py-1 text-xs font-bold capitalize">{item.priority}</span><span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary">{titleCase(item.status)}</span></div><h2 className="mt-3 text-lg font-black">{item.title}</h2><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{item.description}</p><p className="mt-3 text-xs text-muted-foreground">{titleCase(item.category)} · submitted {formatDateTime(item.created_at)}</p></div></div>{item.platform_response && !platform && <div className="mt-5 rounded-2xl border border-primary/20 bg-primary/5 p-4"><p className="text-xs font-black uppercase text-primary">Platform-owner response</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6">{item.platform_response}</p></div>}{platform && <div className="mt-5 grid gap-3 border-t pt-5 sm:grid-cols-[180px_1fr_auto]"><NativeSelect value={status} onChange={(event) => setStatus(event.target.value)} className="input"><option value="submitted">Submitted</option><option value="under_review">Under review</option><option value="planned">Planned</option><option value="completed">Completed</option><option value="rejected">Rejected</option><option value="closed">Closed</option></NativeSelect><Textarea value={response} onChange={(event) => setResponse(event.target.value)} placeholder="Response visible to the user" className="min-h-20 rounded-xl border bg-background p-3 text-sm" /><button type="button" onClick={async () => { setSaving(true); await onRespond(item, status, response); setSaving(false); }} disabled={saving} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Save</button></div>}</article>;
}
function Summary({ icon: Icon, label, value }: { icon: typeof MessageSquarePlus; label: string; value: number }) { return <article className="rounded-3xl border bg-card p-5 shadow-sm"><div className="flex items-center gap-4"><div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div><div><p className="text-sm text-muted-foreground">{label}</p><p className="text-2xl font-black">{value}</p></div></div></article>; }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="block"><span className="mb-2 block text-sm font-black">{label}</span>{children}</label>; }
