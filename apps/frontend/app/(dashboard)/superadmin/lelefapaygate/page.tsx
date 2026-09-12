"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertTriangle,
    CheckCircle2,
    EyeOff,
    KeyRound,
    RefreshCw,
    Save,
    ServerCog,
    ShieldCheck,
    WalletCards,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";


type LelefaConfiguration = {
    enabled: boolean;
    effective_enabled: boolean;
    environment: string;
    base_url: string;
    api_key_configured: boolean;
    api_key_hint?: string | null;
    webhook_secret_configured: boolean;
    request_signing_enabled: boolean;
    timeout_seconds: number;
    webhook_tolerance_seconds: number;
    collection_provider: string;
    payout_provider: string;
    updated_at?: string | null;
};

type FormState = {
    enabled: boolean;
    baseUrl: string;
    apiKey: string;
    webhookSecret: string;
    clearApiKey: boolean;
    clearWebhookSecret: boolean;
    requestSigningEnabled: boolean;
    timeoutSeconds: string;
    webhookToleranceSeconds: string;
    collectionProvider: string;
    payoutProvider: string;
};

const DEFAULT_FORM: FormState = {
    enabled: false,
    baseUrl: "http://169.255.58.185:8081/api/v1",
    apiKey: "",
    webhookSecret: "",
    clearApiKey: false,
    clearWebhookSecret: false,
    requestSigningEnabled: true,
    timeoutSeconds: "15",
    webhookToleranceSeconds: "300",
    collectionProvider: "mpesa",
    payoutProvider: "mpesa",
};

function formFromConfiguration(configuration: LelefaConfiguration): FormState {
    return {
        enabled: configuration.enabled,
        baseUrl: configuration.base_url,
        apiKey: "",
        webhookSecret: "",
        clearApiKey: false,
        clearWebhookSecret: false,
        requestSigningEnabled: configuration.request_signing_enabled,
        timeoutSeconds: String(configuration.timeout_seconds),
        webhookToleranceSeconds: String(configuration.webhook_tolerance_seconds),
        collectionProvider: configuration.collection_provider,
        payoutProvider: configuration.payout_provider,
    };
}

function requestErrorMessage(error: any, fallback: string): string {
    const detail = error?.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) return String(detail.message);
    return String(error?.message ?? fallback);
}

function updatedLabel(value?: string | null) {
    if (!value) return "Not saved yet";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-LS");
}

export default function LelefaPayGateConfigurationPage() {
    const [configuration, setConfiguration] = useState<LelefaConfiguration | null>(null);
    const [form, setForm] = useState<FormState>(DEFAULT_FORM);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const loadConfiguration = useCallback(async () => {
        setLoading(true);
        try {
            const response = await api.get<LelefaConfiguration>("/lelefapaygate/admin/configuration");
            setConfiguration(response.data);
            setForm(formFromConfiguration(response.data));
            setError(null);
        } catch (requestError: any) {
            setError(requestErrorMessage(requestError, "Could not load LelefaPayGate configuration"));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadConfiguration();
    }, [loadConfiguration]);

    const statusLabel = useMemo(() => {
        if (configuration?.effective_enabled) return "Available";
        if (configuration?.enabled) return "Configuration incomplete";
        return "Disabled";
    }, [configuration]);

    function update<K extends keyof FormState>(key: K, value: FormState[K]) {
        setForm((current) => ({ ...current, [key]: value }));
        setSuccess(null);
    }

    async function saveConfiguration() {
        if (saving) return;
        setSaving(true);
        setError(null);
        setSuccess(null);
        try {
            const response = await api.put<LelefaConfiguration>("/lelefapaygate/admin/configuration", {
                enabled: form.enabled,
                base_url: form.baseUrl.trim(),
                api_key: form.apiKey.trim() || null,
                webhook_secret: form.webhookSecret.trim() || null,
                clear_api_key: form.clearApiKey,
                clear_webhook_secret: form.clearWebhookSecret,
                request_signing_enabled: form.requestSigningEnabled,
                timeout_seconds: Number(form.timeoutSeconds),
                webhook_tolerance_seconds: Number(form.webhookToleranceSeconds),
                collection_provider: form.collectionProvider.trim(),
                payout_provider: form.payoutProvider.trim(),
            });
            setConfiguration(response.data);
            setForm(formFromConfiguration(response.data));
            setSuccess(
                response.data.effective_enabled
                    ? "LelefaPayGate is enabled and available to LoanHub."
                    : "LelefaPayGate configuration was saved.",
            );
        } catch (requestError: any) {
            setError(requestErrorMessage(requestError, "Could not save LelefaPayGate configuration"));
        } finally {
            setSaving(false);
        }
    }

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-16 -top-16 h-52 w-52 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.18em] text-primary">Super Admin · payment infrastructure</p>
                        <h1 className="mt-2 text-3xl font-black">LelefaPayGate configuration</h1>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Connect LoanHub to LelefaPayGate from the control centre. Operational credentials are encrypted in PostgreSQL and are never returned to this screen after saving.
                        </p>
                    </div>
                    <div className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-black ${configuration?.effective_enabled ? "bg-emerald-500/10 text-emerald-700" : configuration?.enabled ? "bg-amber-500/10 text-amber-700" : "bg-muted text-muted-foreground"}`}>
                        {configuration?.effective_enabled ? <CheckCircle2 className="h-4 w-4" /> : <ServerCog className="h-4 w-4" />}
                        {loading ? "Loading" : statusLabel}
                    </div>
                </div>
            </section>

            {error ? (
                <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                    <div><p className="font-black">LelefaPayGate configuration warning</p><p className="mt-1">{error}</p></div>
                </div>
            ) : null}

            {success ? (
                <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
                    <p className="font-bold">{success}</p>
                </div>
            ) : null}

            <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
                <div className="space-y-5">
                    <Card>
                        <CardHeader className="border-b">
                            <CardTitle>Gateway availability</CardTitle>
                            <CardDescription>Enable this only after the API key and webhook signing secret have been saved.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-5 pt-6">
                            <label className="flex cursor-pointer items-start justify-between gap-4 rounded-2xl border p-4">
                                <div>
                                    <p className="font-black">Make LelefaPayGate available to LoanHub</p>
                                    <p className="mt-1 text-sm leading-6 text-muted-foreground">When enabled, borrower payments, cashier collections and supported payouts can use the gateway.</p>
                                </div>
                                <input
                                    type="checkbox"
                                    className="mt-1 h-5 w-5 accent-primary"
                                    checked={form.enabled}
                                    onChange={(event) => update("enabled", event.target.checked)}
                                    disabled={loading || saving}
                                />
                            </label>

                            <div>
                                <label htmlFor="lelefa-base-url" className="text-sm font-black">Gateway API base URL</label>
                                <Input id="lelefa-base-url" className="mt-2" value={form.baseUrl} onChange={(event) => update("baseUrl", event.target.value)} placeholder="https://gateway.example/api/v1" disabled={loading || saving} />
                                <p className="mt-2 text-xs text-muted-foreground">Use the LelefaPayGate API URL reachable from the LoanHub backend. Never put credentials in this URL.</p>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="border-b">
                            <CardTitle>Encrypted credentials</CardTitle>
                            <CardDescription>Blank fields preserve the currently stored credential. Enter a value only when creating or rotating it.</CardDescription>
                        </CardHeader>
                        <CardContent className="grid gap-5 pt-6 lg:grid-cols-2">
                            <div className="space-y-3 rounded-2xl border p-4">
                                <div className="flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-primary" /><p className="font-black">Merchant API key</p></div>
                                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-black ${configuration?.api_key_configured ? "bg-emerald-500/10 text-emerald-700" : "bg-amber-500/10 text-amber-700"}`}>{configuration?.api_key_configured ? "Configured" : "Missing"}</span>
                                </div>
                                {configuration?.api_key_hint ? <p className="font-mono text-xs text-muted-foreground">{configuration.api_key_hint}</p> : null}
                                <Input aria-label="Merchant API key" type="password" value={form.apiKey} onChange={(event) => update("apiKey", event.target.value)} placeholder={configuration?.api_key_configured ? "Leave blank to keep existing key" : "ipb_test_… or ipb_live_…"} autoComplete="new-password" disabled={loading || saving || form.clearApiKey} />
                                <label className="flex items-center gap-2 text-xs font-semibold text-muted-foreground"><input type="checkbox" checked={form.clearApiKey} onChange={(event) => update("clearApiKey", event.target.checked)} disabled={loading || saving} />Remove stored API key on save</label>
                            </div>

                            <div className="space-y-3 rounded-2xl border p-4">
                                <div className="flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-primary" /><p className="font-black">Webhook signing secret</p></div>
                                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-black ${configuration?.webhook_secret_configured ? "bg-emerald-500/10 text-emerald-700" : "bg-amber-500/10 text-amber-700"}`}>{configuration?.webhook_secret_configured ? "Configured" : "Missing"}</span>
                                </div>
                                <p className="flex items-center gap-2 text-xs text-muted-foreground"><EyeOff className="h-3.5 w-3.5" />The stored secret is never displayed again.</p>
                                <Input aria-label="Webhook signing secret" type="password" value={form.webhookSecret} onChange={(event) => update("webhookSecret", event.target.value)} placeholder={configuration?.webhook_secret_configured ? "Leave blank to keep existing secret" : "Enter webhook signing secret"} autoComplete="new-password" disabled={loading || saving || form.clearWebhookSecret} />
                                <label className="flex items-center gap-2 text-xs font-semibold text-muted-foreground"><input type="checkbox" checked={form.clearWebhookSecret} onChange={(event) => update("clearWebhookSecret", event.target.checked)} disabled={loading || saving} />Remove stored webhook secret on save</label>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="border-b">
                            <CardTitle>Runtime policy</CardTitle>
                            <CardDescription>These values are stored with the gateway configuration and apply to LoanHub server-to-server calls.</CardDescription>
                        </CardHeader>
                        <CardContent className="grid gap-5 pt-6 md:grid-cols-2">
                            <div><label htmlFor="lelefa-collection-provider" className="text-sm font-black">Collection provider</label><Input id="lelefa-collection-provider" className="mt-2" value={form.collectionProvider} onChange={(event) => update("collectionProvider", event.target.value)} disabled={loading || saving} /></div>
                            <div><label htmlFor="lelefa-payout-provider" className="text-sm font-black">Payout provider</label><Input id="lelefa-payout-provider" className="mt-2" value={form.payoutProvider} onChange={(event) => update("payoutProvider", event.target.value)} disabled={loading || saving} /></div>
                            <div><label htmlFor="lelefa-request-timeout" className="text-sm font-black">Request timeout (seconds)</label><Input id="lelefa-request-timeout" className="mt-2" type="number" min="1" max="60" step="1" value={form.timeoutSeconds} onChange={(event) => update("timeoutSeconds", event.target.value)} disabled={loading || saving} /></div>
                            <div><label htmlFor="lelefa-webhook-tolerance" className="text-sm font-black">Webhook tolerance (seconds)</label><Input id="lelefa-webhook-tolerance" className="mt-2" type="number" min="30" max="900" step="1" value={form.webhookToleranceSeconds} onChange={(event) => update("webhookToleranceSeconds", event.target.value)} disabled={loading || saving} /></div>
                            <label className="flex items-start gap-3 rounded-2xl border p-4 md:col-span-2"><input type="checkbox" className="mt-1 h-4 w-4 accent-primary" checked={form.requestSigningEnabled} onChange={(event) => update("requestSigningEnabled", event.target.checked)} disabled={loading || saving} /><div><p className="font-black">Sign outbound gateway requests</p><p className="mt-1 text-sm text-muted-foreground">Keep HMAC request signing enabled unless LelefaPayGate explicitly instructs otherwise.</p></div></label>
                        </CardContent>
                    </Card>
                </div>

                <div className="space-y-5">
                    <Card>
                        <CardHeader className="border-b">
                            <CardTitle>Connection summary</CardTitle>
                            <CardDescription>Safe status only. Full secrets are never returned by the API.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3 pt-6 text-sm">
                            <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Environment</span><strong className="uppercase">{configuration?.environment ?? "—"}</strong></div>
                            <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">API key</span><strong>{configuration?.api_key_configured ? "Stored" : "Missing"}</strong></div>
                            <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Webhook secret</span><strong>{configuration?.webhook_secret_configured ? "Stored" : "Missing"}</strong></div>
                            <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Request signing</span><strong>{configuration?.request_signing_enabled ? "On" : "Off"}</strong></div>
                            <div className="border-t pt-3"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Last changed</p><p className="mt-1 font-semibold">{updatedLabel(configuration?.updated_at)}</p></div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="border-b">
                            <CardTitle>Save and publish</CardTitle>
                            <CardDescription>The database becomes the runtime source immediately after a successful save.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4 pt-6">
                            <div className="rounded-2xl bg-primary/5 p-4 text-sm leading-6 text-muted-foreground">
                                <p className="font-black text-foreground">No Lelefa credentials in .env</p>
                                <p className="mt-1">Only LoanHub&apos;s platform encryption master key stays in deployment configuration. Gateway credentials are encrypted before they are written to PostgreSQL.</p>
                            </div>
                            <Button className="w-full" size="lg" onClick={() => void saveConfiguration()} disabled={loading || saving}>
                                {saving ? <RefreshCw className="animate-spin" /> : <Save />}
                                {saving ? "Saving configuration" : "Save configuration"}
                            </Button>
                            <Button className="w-full" variant="outline" onClick={() => void loadConfiguration()} disabled={loading || saving}>
                                <RefreshCw className={loading ? "animate-spin" : ""} />Refresh
                            </Button>
                        </CardContent>
                    </Card>

                    <div className="flex gap-3 rounded-2xl border bg-card p-4 text-sm leading-6 text-muted-foreground">
                        <WalletCards className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                        <p>When the status becomes <strong className="text-foreground">Available</strong>, borrower payment screens can load LelefaPayGate payment methods. Borrowers still need an active/defaulted loan that accepts repayments.</p>
                    </div>
                </div>
            </section>
        </main>
    );
}
