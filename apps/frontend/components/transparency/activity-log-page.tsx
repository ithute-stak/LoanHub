"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import {
    Activity,
    AlertCircle,
    CheckCircle2,
    Eye,
    History,
    Loader2,
    RefreshCcw,
    Search,
    ShieldCheck,
    Trash2,
} from "lucide-react";
import {
    format,
    formatDistanceToNow,
} from "date-fns";
import {
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import {
    listAuditEvents,
} from "@/api/audit";
import { CustomDialog } from "@/components/ui/custom-dialog";
import type { AuditLog } from "@/types/audit";
import { getErrorMessage } from "@/utils/apiError";

function titleCase(value: string): string {
    return value
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) =>
            letter.toUpperCase(),
        );
}

function actionStyle(action: string): string {
    if (action === "created") {
        return "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400";
    }
    if (action === "deleted") {
        return "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400";
    }
    return "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400";
}

export function ActivityLogPage({
    mode,
}: {
    mode: "company" | "platform";
}) {
    const [events, setEvents] = useState<AuditLog[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [action, setAction] = useState("all");
    const [entity, setEntity] = useState("all");
    const [selected, setSelected] =
        useState<AuditLog | null>(null);

    const pageSize = 30;

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await listAuditEvents({
                page,
                page_size: pageSize,
                action: action === "all" ? undefined : action,
                entity_type:
                    entity === "all" ? undefined : entity,
                search: search.trim() || undefined,
            });
            setEvents(result.items);
            setTotal(result.total);
        } catch (requestError: unknown) {
            setError(
                getErrorMessage(
                    requestError,
                    "Could not load the activity log.",
                ),
            );
        } finally {
            setLoading(false);
        }
    }, [action, entity, page, search]);

    useEffect(() => {
        const timeout = window.setTimeout(() => {
            void load();
        }, 250);
        return () => window.clearTimeout(timeout);
    }, [load]);

    const entityOptions = useMemo(
        () =>
            Array.from(
                new Set(
                    events
                        .map((event) => event.entity_type)
                        .filter(
                            (value): value is string =>
                                Boolean(value),
                        ),
                ),
            ).sort(),
        [events],
    );

    const totalPages = Math.max(
        1,
        Math.ceil(total / pageSize),
    );

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                            Immutable transparency stream
                        </p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight">
                            {mode === "platform"
                                ? "Platform activity log"
                                : "Company activity log"}
                        </h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Every tracked create, update and delete
                            action is recorded with actor, scope,
                            changed fields and timestamps.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => void load()}
                        disabled={loading}
                        className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50"
                    >
                        <RefreshCcw
                            className={`h-4 w-4 ${
                                loading ? "animate-spin" : ""
                            }`}
                        />
                        Refresh events
                    </button>
                </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-3">
                <Summary
                    icon={History}
                    label="Recorded events"
                    value={total}
                />
                <Summary
                    icon={CheckCircle2}
                    label="Visible on this page"
                    value={events.length}
                />
                <Summary
                    icon={ShieldCheck}
                    label="Delete events"
                    value={events.filter(
                        (item) => item.action === "deleted",
                    ).length}
                />
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="grid gap-3 border-b p-4 lg:grid-cols-[1fr_180px_220px] sm:p-5">
                    <SuggestionSearch
                        value={search}
                        onValueChange={(value) => {
                            setSearch(value);
                            setPage(1);
                        }}
                        suggestions={events.map((event) => ({
                            value: event.entity_reference || event.description || event.request_id || event.id,
                            label: event.entity_reference || event.description || `${titleCase(event.action)} event`,
                            description: [event.actor_name, event.company_name, event.branch_name].filter(Boolean).join(" · "),
                            keywords: [
                                event.id,
                                event.action,
                                event.entity_type ?? "",
                                event.table_name ?? "",
                                event.actor_role ?? "",
                                event.request_id ?? "",
                                event.description ?? "",
                            ],
                        }))}
                        placeholder="Type a description, entity, actor or request ID..."
                        suggestionLabel="Audit events"
                        emptyMessage="No loaded event matches that text."
                    />
                    <NativeSelect
                        value={action}
                        onChange={(event) => {
                            setAction(event.target.value);
                            setPage(1);
                        }}
                        className="h-11 rounded-xl border bg-background px-3 text-sm font-bold"
                    >
                        <option value="all">All actions</option>
                        <option value="created">Created</option>
                        <option value="updated">Updated</option>
                        <option value="deleted">Deleted</option>
                    </NativeSelect>
                    <NativeSelect
                        value={entity}
                        onChange={(event) => {
                            setEntity(event.target.value);
                            setPage(1);
                        }}
                        className="h-11 rounded-xl border bg-background px-3 text-sm font-bold"
                    >
                        <option value="all">All entity types</option>
                        {entityOptions.map((option) => (
                            <option key={option} value={option}>
                                {titleCase(option)}
                            </option>
                        ))}
                    </NativeSelect>
                </div>

                {error && (
                    <div className="flex items-start gap-3 border-b border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                        <AlertCircle className="mt-0.5 h-5 w-5" />
                        {error}
                    </div>
                )}

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[980px] text-sm">
                        <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                            <tr>
                                <th className="px-5 py-4">Event</th>
                                <th className="px-4 py-4">Entity</th>
                                <th className="px-4 py-4">Actor</th>
                                <th className="px-4 py-4">Changed fields</th>
                                <th className="px-4 py-4">Time</th>
                                <th className="px-5 py-4 text-right">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading && events.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="py-20 text-center">
                                        <Loader2 className="mx-auto h-7 w-7 animate-spin text-primary" />
                                    </td>
                                </tr>
                            ) : (
                                events.map((event) => (
                                    <tr key={event.id} className="border-t hover:bg-muted/30">
                                        <td className="px-5 py-4">
                                            <div className="flex items-start gap-3">
                                                <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${actionStyle(event.action)}`}>
                                                    {event.action === "deleted" ? <Trash2 className="h-4 w-4" /> : <Activity className="h-4 w-4" />}
                                                </span>
                                                <div>
                                                    <p className="font-black">{titleCase(event.action)}</p>
                                                    <p className="mt-1 max-w-md text-xs leading-5 text-muted-foreground">{event.description ?? "No description"}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <p className="font-bold">{titleCase(event.entity_type ?? event.table_name ?? "unknown")}</p>
                                            <p className="mt-1 max-w-48 truncate text-xs font-semibold text-muted-foreground">
                                                {event.entity_reference ?? "Reference unavailable"}
                                            </p>
                                        </td>
                                        <td className="px-4 py-4">
                                            <p className="font-bold">
                                                {event.actor_name ?? "Automated process"}
                                            </p>
                                            <p className="mt-1 text-xs text-muted-foreground">
                                                {titleCase(event.actor_role ?? "system")}
                                            </p>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex max-w-64 flex-wrap gap-1">
                                                {event.changed_fields.length > 0 ? event.changed_fields.slice(0, 5).map((field) => (
                                                    <span key={field} className="rounded-md bg-muted px-2 py-1 text-[10px] font-bold">{field}</span>
                                                )) : <span className="text-xs text-muted-foreground">Entire record</span>}
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <p className="font-bold">{formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}</p>
                                            <p className="mt-1 text-xs text-muted-foreground">{format(new Date(event.created_at), "dd MMM yyyy HH:mm")}</p>
                                        </td>
                                        <td className="px-5 py-4 text-right">
                                            <button type="button" onClick={() => setSelected(event)} className="inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-black hover:border-primary hover:text-primary">
                                                <Eye className="h-4 w-4" />
                                                Inspect
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                <div className="flex items-center justify-between border-t p-4 text-sm">
                    <span className="text-muted-foreground">
                        Page <strong className="text-foreground">{page}</strong> of <strong className="text-foreground">{totalPages}</strong>
                    </span>
                    <div className="flex gap-2">
                        <button type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))} className="h-9 rounded-lg border px-3 font-bold disabled:opacity-40">Previous</button>
                        <button type="button" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))} className="h-9 rounded-lg border px-3 font-bold disabled:opacity-40">Next</button>
                    </div>
                </div>
            </section>

            <CustomDialog open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)} title="Audit event details" description="Review the before and after state captured for this transaction." contentClassName="max-w-4xl">
                <div className="p-6 sm:p-8">
                    {selected && (
                        <div className="space-y-5">
                            <div className="grid gap-3 sm:grid-cols-3">
                                <Detail label="Action" value={titleCase(selected.action)} />
                                <Detail label="Entity" value={titleCase(selected.entity_type ?? "Unknown")} />
                                <Detail label="Actor role" value={titleCase(selected.actor_role ?? "System")} />
                            </div>
                            <div className="grid gap-4 lg:grid-cols-2">
                                <JsonPanel title="Before" data={selected.before_data} />
                                <JsonPanel title="After" data={selected.after_data} />
                            </div>
                        </div>
                    )}
                </div>
            </CustomDialog>
        </main>
    );
}

function Summary({ icon: Icon, label, value }: { icon: typeof History; label: string; value: number }) {
    return (
        <article className="rounded-3xl border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm font-bold text-muted-foreground">{label}</p>
                    <p className="mt-2 text-3xl font-black">{value}</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
            </div>
        </article>
    );
}

function Detail({ label, value }: { label: string; value: string }) {
    return <div className="rounded-xl bg-muted/60 p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-black">{value}</p></div>;
}

function JsonPanel({ title, data }: { title: string; data: Record<string, unknown> }) {
    return (
        <section className="overflow-hidden rounded-2xl border">
            <h3 className="border-b bg-muted/60 px-4 py-3 font-black">{title}</h3>
            <pre className="max-h-96 overflow-auto p-4 text-xs leading-5">{JSON.stringify(data, null, 2)}</pre>
        </section>
    );
}
