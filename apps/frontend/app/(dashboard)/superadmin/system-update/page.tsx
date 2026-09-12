"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertTriangle,
    CheckCircle2,
    Clock3,
    RefreshCw,
    ServerCog,
    ShieldCheck,
    XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";


type UpdateStep = {
    name: string;
    status: string;
    message?: string | null;
    started_at?: string | null;
    finished_at?: string | null;
};

type UpdateStatus = {
    configured: boolean;
    state: string;
    message?: string | null;
    started_at?: string | null;
    finished_at?: string | null;
    previous_image?: string | null;
    current_image?: string | null;
    target_image?: string | null;
    last_error?: string | null;
    steps: UpdateStep[];
    details: Record<string, unknown>;
};

const ACTIVE_STATES = new Set([
    "queued",
    "validating",
    "pulling",
    "recreating",
    "verifying",
    "rolling_back",
]);

function statusTone(state: string) {
    if (state === "succeeded") return "text-emerald-700 bg-emerald-500/10";
    if (state === "failed") return "text-red-700 bg-red-500/10";
    if (ACTIVE_STATES.has(state)) return "text-amber-700 bg-amber-500/10";
    if (state === "unavailable") return "text-red-700 bg-red-500/10";
    return "text-primary bg-primary/10";
}

function StepIcon({ status }: { status: string }) {
    if (status === "succeeded") return <CheckCircle2 className="h-5 w-5 text-emerald-600" />;
    if (status === "failed") return <XCircle className="h-5 w-5 text-red-600" />;
    if (status === "running") return <RefreshCw className="h-5 w-5 animate-spin text-amber-600" />;
    return <Clock3 className="h-5 w-5 text-muted-foreground" />;
}

function displayTime(value?: string | null) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-LS");
}

export default function SystemUpdatePage() {
    const [status, setStatus] = useState<UpdateStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [confirmation, setConfirmation] = useState("");
    const [error, setError] = useState<string | null>(null);

    const loadStatus = useCallback(async () => {
        try {
            const response = await api.get<UpdateStatus>("/system-updates/status");
            setStatus(response.data);
            setError(null);
        } catch (requestError: any) {
            const message = requestError?.response?.data?.detail ?? requestError?.message ?? "Could not read update status";
            setError(String(message));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadStatus();
    }, [loadStatus]);

    const active = useMemo(() => Boolean(status && ACTIVE_STATES.has(status.state)), [status]);

    useEffect(() => {
        if (!active) return;
        const timer = window.setInterval(() => {
            void loadStatus();
        }, 2500);
        return () => window.clearInterval(timer);
    }, [active, loadStatus]);

    async function runUpdate() {
        if (confirmation !== "UPDATE" || submitting || active) return;
        setSubmitting(true);
        setError(null);
        try {
            const response = await api.post<UpdateStatus>("/system-updates/update", {
                confirmation,
            });
            setStatus(response.data);
            setConfirmation("");
        } catch (requestError: any) {
            const message = requestError?.response?.data?.detail ?? requestError?.message ?? "Update request failed";
            setError(String(message));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-16 -top-16 h-52 w-52 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.18em] text-primary">Super Admin only</p>
                        <h1 className="mt-2 text-3xl font-black">System update</h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Pull and recreate the production LoanHub service through the root-owned VPS updater. No SSH or root password is exposed to the browser or application container.
                        </p>
                    </div>
                    <div className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-black ${statusTone(status?.state ?? "unknown")}`}>
                        <ServerCog className="h-4 w-4" />
                        {(status?.state ?? (loading ? "loading" : "unknown")).replaceAll("_", " ")}
                    </div>
                </div>
            </section>

            {error ? (
                <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                    <div><p className="font-black">Update service warning</p><p className="mt-1">{error}</p></div>
                </div>
            ) : null}

            <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
                <Card>
                    <CardHeader className="border-b">
                        <CardTitle>Deployment status</CardTitle>
                        <CardDescription>The host agent survives the LoanHub container restart and reports progress when the application reconnects.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-5 pt-2">
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                            <div className="rounded-2xl bg-muted/40 p-4"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Host updater</p><p className="mt-2 font-black">{status?.configured ? "Connected" : "Not configured"}</p></div>
                            <div className="rounded-2xl bg-muted/40 p-4"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Started</p><p className="mt-2 text-sm font-black">{displayTime(status?.started_at)}</p></div>
                            <div className="rounded-2xl bg-muted/40 p-4"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Finished</p><p className="mt-2 text-sm font-black">{displayTime(status?.finished_at)}</p></div>
                            <div className="rounded-2xl bg-muted/40 p-4"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Service</p><p className="mt-2 font-black">LoanHub</p></div>
                        </div>

                        <div className="space-y-2">
                            {(status?.steps ?? []).length ? status?.steps.map((step) => (
                                <div key={step.name} className="flex items-start gap-3 rounded-2xl border p-4">
                                    <StepIcon status={step.status} />
                                    <div className="min-w-0 flex-1">
                                        <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-black capitalize">{step.name.replaceAll("_", " ")}</p><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{step.status}</p></div>
                                        {step.message ? <p className="mt-1 text-sm text-muted-foreground">{step.message}</p> : null}
                                    </div>
                                </div>
                            )) : (
                                <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground">No deployment is currently running.</div>
                            )}
                        </div>

                        {status?.last_error ? <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><p className="font-black">Last deployment error</p><pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs">{status.last_error}</pre></div> : null}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="border-b">
                        <CardTitle>Install latest LoanHub image</CardTitle>
                        <CardDescription>This action is restricted to the platform owner and restarts the production LoanHub container.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4 pt-2">
                        <div className="flex gap-3 rounded-2xl bg-primary/5 p-4">
                            <ShieldCheck className="h-5 w-5 shrink-0 text-primary" />
                            <p className="text-sm leading-6 text-muted-foreground">The updater can only validate, pull, recreate and verify the configured <strong className="text-foreground">loanhub</strong> Compose service. It cannot accept arbitrary shell commands.</p>
                        </div>

                        <div>
                            <label htmlFor="update-confirmation" className="text-sm font-black">Type UPDATE to confirm</label>
                            <Input id="update-confirmation" className="mt-2" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder="UPDATE" autoComplete="off" disabled={!status?.configured || active || submitting} />
                        </div>

                        <Button className="w-full" variant="destructive" size="lg" disabled={!status?.configured || confirmation !== "UPDATE" || active || submitting} onClick={() => void runUpdate()}>
                            {submitting || active ? <RefreshCw className="animate-spin" /> : <ServerCog />}
                            {active ? "Update in progress" : "Update LoanHub"}
                        </Button>

                        <Button className="w-full" variant="outline" onClick={() => void loadStatus()} disabled={loading}>
                            <RefreshCw className={loading ? "animate-spin" : ""} />Refresh status
                        </Button>

                        <p className="text-xs leading-5 text-muted-foreground">Expected host operation: validate `/opt/loanhub`, pull the configured image, recreate only the `loanhub` service, then wait for the container health check.</p>
                    </CardContent>
                </Card>
            </section>
        </main>
    );
}
