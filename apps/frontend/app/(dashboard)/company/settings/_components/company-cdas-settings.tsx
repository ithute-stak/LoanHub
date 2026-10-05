"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CircleCheck, CircleX, Loader2, RefreshCcw, ShieldCheck, WalletCards } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatMoney, titleCase } from "@/lib/format";
import { useTenant } from "@/provider/tenantProvider";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type CdasEnvironment = "test" | "live";

type ProfileState = {
    configured: boolean;
    last_test_status: string | null;
    last_tested_at: string | null;
};

type Subscription = {
    status: string;
    approved: boolean;
    currency: string;
    pricing: Record<string, number>;
    credit_limit: number | null;
    warning_threshold: number | null;
    auto_suspend_on_limit: boolean;
    rejection_reason?: string | null;
    usage?: {
        live_transaction_count: number;
        outstanding_balance: number;
        credit_limit: number | null;
        remaining_credit: number | null;
        currency: string;
    };
};

type CdasConfiguration = {
    provider: "cdas";
    environment: CdasEnvironment;
    enabled: boolean;
    configured: boolean;
    last_test_status: string | null;
    last_tested_at: string | null;
    profiles: { test: ProfileState; live: ProfileState };
    subscription: Subscription;
};

type CdasTransaction = {
    id: string;
    environment: CdasEnvironment;
    operation_type: string;
    transaction_reference: string;
    amount: number;
    currency: string;
    status: string;
    accrued_at: string;
};

type Props = { canManage: boolean };

const OPERATION_LABELS: Record<string, string> = {
    employee_verification: "Employee verification",
    affordability: "Affordability check",
    deduction_lookup: "Deduction lookup",
    registration: "Deduction registration",
    lifecycle: "Lifecycle action",
    modification: "Active deduction modification",
    settlement: "Settlement",
    document: "Statement / document",
};

export function CompanyCdasSettings({ canManage }: Props) {
    const { activeRole } = useTenant();
    const canSwitchEnvironment = activeRole === "company_owner";
    const [configuration, setConfiguration] = useState<CdasConfiguration | null>(null);
    const [transactions, setTransactions] = useState<CdasTransaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [requesting, setRequesting] = useState(false);
    const [switching, setSwitching] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setLoadError(null);
        try {
            const [configResponse, transactionResponse] = await Promise.all([
                api.get<CdasConfiguration>("/cdas/configuration"),
                api.get<CdasTransaction[]>("/cdas/transactions?limit=10"),
            ]);
            setConfiguration(configResponse.data);
            setTransactions(transactionResponse.data);
        } catch (error: unknown) {
            setLoadError(getErrorMessage(error, "CDAS service status could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void load(); }, [load]);

    async function requestSubscription() {
        if (!canManage || requesting) return;
        setRequesting(true);
        try {
            await api.post("/cdas/subscription");
            toast.success("CDAS subscription requested", {
                description: "The LoanHub Platform Owner must configure your company-specific CDAS profile and approve access.",
            });
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS subscription request could not be submitted."));
        } finally {
            setRequesting(false);
        }
    }

    async function switchEnvironment(environment: CdasEnvironment) {
        if (!canSwitchEnvironment || switching || environment === configuration?.environment) return;
        setSwitching(true);
        try {
            const response = await api.put<CdasConfiguration>("/cdas/environment", { environment });
            setConfiguration(response.data);
            toast.success(`CDAS switched to ${environment === "live" ? "Live" : "Test"}`);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS environment could not be changed."));
        } finally {
            setSwitching(false);
        }
    }

    if (loading) {
        return <Card><CardContent className="flex min-h-48 items-center justify-center gap-3 text-sm text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /> Loading CDAS service…</CardContent></Card>;
    }

    if (loadError) {
        return (
            <Alert variant="destructive">
                <CircleX className="h-4 w-4" />
                <AlertTitle>CDAS service unavailable</AlertTitle>
                <AlertDescription className="space-y-3">
                    <p>{loadError}</p>
                    <Button type="button" variant="outline" size="sm" onClick={() => void load()}><RefreshCcw className="h-4 w-4" /> Retry</Button>
                </AlertDescription>
            </Alert>
        );
    }

    const subscription = configuration?.subscription;
    const profile = configuration?.profiles?.[configuration.environment];
    const usage = subscription?.usage;

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                            <CardTitle className="flex items-center gap-2"><WalletCards className="h-5 w-5" /> CDAS platform service</CardTitle>
                            <CardDescription className="mt-2 max-w-3xl">
                                Your company uses its own CDAS account and Item Code, but credentials are held securely by the LoanHub Platform Owner. Your company never sees or replaces CDAS passwords, usernames or provider endpoints.
                            </CardDescription>
                        </div>
                        <Badge variant={subscription?.status === "approved" ? "default" : "secondary"}>{titleCase(subscription?.status || "not subscribed")}</Badge>
                    </div>
                </CardHeader>
                <CardContent className="space-y-5">
                    {subscription?.rejection_reason ? <Alert variant="destructive"><CircleX className="h-4 w-4" /><AlertTitle>Subscription rejected</AlertTitle><AlertDescription>{subscription.rejection_reason}</AlertDescription></Alert> : null}

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <Status label="Selected mode" value={configuration?.environment === "live" ? "Live" : "Test"} good={Boolean(profile?.configured)} />
                        <Status label="Profile configured" value={profile?.configured ? "Yes" : "No"} good={Boolean(profile?.configured)} />
                        <Status label="Connection test" value={profile?.last_test_status ? titleCase(profile.last_test_status) : "Not tested"} good={profile?.last_test_status === "connected"} />
                        <Status label="Platform approval" value={subscription?.approved ? "Approved" : "Required"} good={Boolean(subscription?.approved)} />
                    </div>

                    {!subscription?.approved && subscription?.status !== "pending" && canManage ? (
                        <Button onClick={() => void requestSubscription()} disabled={requesting}>
                            {requesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                            Request CDAS subscription
                        </Button>
                    ) : null}

                    <div className="rounded-2xl border p-4">
                        <p className="text-sm font-black">Company environment</p>
                        <p className="mt-1 text-xs text-muted-foreground">Only the Loan Company Owner can switch Test ↔ Live. Live can be selected only after the Platform Owner has configured and successfully tested your Live profile.</p>
                        <div className="mt-4 flex flex-wrap gap-2">
                            <Button type="button" variant={configuration?.environment === "test" ? "default" : "outline"} disabled={!canSwitchEnvironment || switching || !subscription?.approved || !configuration?.profiles.test.configured} onClick={() => void switchEnvironment("test")}>Test</Button>
                            <Button type="button" variant={configuration?.environment === "live" ? "default" : "outline"} disabled={!canSwitchEnvironment || switching || !subscription?.approved || configuration?.profiles.live.last_test_status !== "connected"} onClick={() => void switchEnvironment("live")}>Live</Button>
                        </div>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-2">
                        {(["test", "live"] as CdasEnvironment[]).map((environment) => {
                            const state = configuration?.profiles[environment];
                            return (
                                <div key={environment} className="rounded-2xl border p-4">
                                    <p className="font-black">{environment === "live" ? "Live" : "Test"} profile</p>
                                    <p className="mt-2 text-sm text-muted-foreground">{state?.configured ? "Configured centrally by Platform Owner" : "Not configured yet"}</p>
                                    <div className="mt-3 flex items-center gap-2 text-xs font-bold">
                                        {state?.last_test_status === "connected" ? <CircleCheck className="h-4 w-4 text-emerald-600" /> : <CircleX className="h-4 w-4 text-muted-foreground" />}
                                        {state?.last_test_status ? titleCase(state.last_test_status) : "Not tested"}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Status label="Live operations" value={String(usage?.live_transaction_count ?? 0)} />
                <Status label="Outstanding" value={formatMoney(usage?.outstanding_balance ?? 0)} />
                <Status label="Credit limit" value={usage?.credit_limit == null ? "Unlimited" : formatMoney(usage.credit_limit)} />
                <Status label="Remaining credit" value={usage?.remaining_credit == null ? "Unlimited" : formatMoney(usage.remaining_credit)} />
            </div>

            <Card>
                <CardHeader><CardTitle>Live PAYG pricing</CardTitle><CardDescription>Test operations cost M0.00. Pricing below applies only to successful Live business operations; login, token refresh and reconciliation traffic is not billed.</CardDescription></CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    {Object.entries(subscription?.pricing || {}).map(([key, price]) => (
                        <div key={key} className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">{OPERATION_LABELS[key] || titleCase(key)}</p><p className="mt-2 text-lg font-black">{formatMoney(price)}</p></div>
                    ))}
                </CardContent>
            </Card>

            <Card>
                <CardHeader><CardTitle>Recent CDAS usage</CardTitle><CardDescription>Successful metered business operations for this company.</CardDescription></CardHeader>
                <CardContent className="space-y-2">
                    {transactions.length ? transactions.map((row) => (
                        <div key={row.id} className="flex flex-col gap-2 rounded-xl border p-3 sm:flex-row sm:items-center sm:justify-between">
                            <div><p className="text-sm font-black">{OPERATION_LABELS[row.operation_type] || titleCase(row.operation_type)}</p><p className="text-xs text-muted-foreground">{row.transaction_reference} · {row.environment.toUpperCase()}</p></div>
                            <div className="text-sm font-black">{formatMoney(row.amount)}</div>
                        </div>
                    )) : <p className="text-sm text-muted-foreground">No CDAS usage has been recorded yet.</p>}
                </CardContent>
            </Card>

            <div className="flex flex-wrap gap-2">
                <Button asChild><Link href="/company/cdas"><ShieldCheck className="h-4 w-4" /> Open CDAS workspace</Link></Button>
                <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" /> Refresh</Button>
            </div>
        </div>
    );
}

function Status({ label, value, good }: { label: string; value: string; good?: boolean }) {
    return <div className="rounded-2xl border p-4"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p><p className={`mt-2 text-sm font-black ${good ? "text-emerald-600" : ""}`}>{value}</p></div>;
}
