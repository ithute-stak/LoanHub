"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
    CircleCheck,
    CircleX,
    KeyRound,
    Loader2,
    PlugZap,
    RefreshCcw,
    Save,
    ServerCog,
    ShieldCheck,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type CdasEnvironment = "test" | "live";

type CdasConfiguration = {
    provider: "cdas";
    environment: CdasEnvironment;
    enabled: boolean;
    base_url: string;
    username: string;
    timeout_seconds: number;
    password_configured: boolean;
    configured: boolean;
    last_test_status: string | null;
    last_tested_at: string | null;
};

type CdasForm = {
    environment: CdasEnvironment;
    enabled: boolean;
    base_url: string;
    username: string;
    password: string;
    clear_password: boolean;
    timeout_seconds: number;
};

type Props = {
    canManage: boolean;
};

const CDAS_TEST_BASE_URL = "https://test-cdas-thirdpartyapi.sentraptt.com";

const DEFAULT_FORM: CdasForm = {
    environment: "test",
    enabled: false,
    base_url: CDAS_TEST_BASE_URL,
    username: "",
    password: "",
    clear_password: false,
    timeout_seconds: 20,
};

function formFromConfiguration(configuration: CdasConfiguration): CdasForm {
    return {
        environment: configuration.environment,
        enabled: configuration.enabled,
        base_url: configuration.base_url,
        username: configuration.username,
        password: "",
        clear_password: false,
        timeout_seconds: configuration.timeout_seconds,
    };
}

export function CompanyCdasSettings({ canManage }: Props) {
    const [configuration, setConfiguration] = useState<CdasConfiguration | null>(null);
    const [form, setForm] = useState<CdasForm>(DEFAULT_FORM);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);

    const environmentChanged = Boolean(
        configuration && form.environment !== configuration.environment,
    );

    const load = useCallback(async () => {
        setLoading(true);
        setLoadError(null);
        try {
            const response = await api.get<CdasConfiguration>("/cdas/configuration");
            setConfiguration(response.data);
            setForm(formFromConfiguration(response.data));
        } catch (error: unknown) {
            setLoadError(getErrorMessage(error, "CDAS configuration could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    function changeEnvironment(environment: CdasEnvironment) {
        setForm((current) => {
            if (environment === current.environment) return current;
            return {
                ...current,
                environment,
                enabled: false,
                base_url: environment === "test" ? CDAS_TEST_BASE_URL : "",
                username: "",
                password: "",
                clear_password: false,
            };
        });
    }

    async function save(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canManage || saving) return;

        if (!form.base_url.trim() || !form.username.trim()) {
            toast.error("CDAS base URL and username are required.");
            return;
        }
        if (
            form.enabled &&
            (!configuration?.password_configured || environmentChanged) &&
            !form.password.trim()
        ) {
            toast.error("Enter the CDAS password for the selected environment before enabling the integration.");
            return;
        }

        setSaving(true);
        try {
            const response = await api.put<CdasConfiguration>("/cdas/configuration", {
                environment: form.environment,
                enabled: form.enabled,
                base_url: form.base_url.trim(),
                username: form.username.trim(),
                password: form.password.trim() || null,
                clear_password: form.clear_password,
                timeout_seconds: Number(form.timeout_seconds),
            });
            setConfiguration(response.data);
            setForm(formFromConfiguration(response.data));
            toast.success("CDAS company configuration saved.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS configuration could not be saved."));
        } finally {
            setSaving(false);
        }
    }

    async function testConnection() {
        if (!canManage || testing) return;
        setTesting(true);
        try {
            const response = await api.post<{ ok: boolean; configuration: CdasConfiguration }>(
                "/cdas/configuration/test",
            );
            setConfiguration(response.data.configuration);
            setForm(formFromConfiguration(response.data.configuration));
            toast.success("CDAS connection verified successfully.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS connection test failed."));
            await load();
        } finally {
            setTesting(false);
        }
    }

    if (loading) {
        return (
            <Card>
                <CardContent className="flex min-h-56 items-center justify-center gap-3 text-sm text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" /> Loading CDAS company configuration…
                </CardContent>
            </Card>
        );
    }

    if (loadError) {
        return (
            <Alert variant="destructive">
                <CircleX className="h-4 w-4" />
                <AlertTitle>CDAS configuration unavailable</AlertTitle>
                <AlertDescription className="space-y-3">
                    <p>{loadError}</p>
                    <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
                        <RefreshCcw className="h-4 w-4" /> Retry
                    </Button>
                </AlertDescription>
            </Alert>
        );
    }

    return (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
            <Card>
                <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                            <CardTitle className="flex items-center gap-2">
                                <ServerCog className="h-5 w-5" /> CDAS integration
                            </CardTitle>
                            <CardDescription className="mt-2 max-w-3xl">
                                Configure the CDAS account for this company. Test and live credentials are stored separately from application deployment settings, and the password is encrypted before it is stored.
                            </CardDescription>
                        </div>
                        <Badge variant={configuration?.enabled ? "default" : "secondary"}>
                            {configuration?.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                    </div>
                </CardHeader>
                <CardContent>
                    <form className="space-y-6" onSubmit={save}>
                        <div className="grid gap-5 md:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="cdas-environment">Environment</Label>
                                <select
                                    id="cdas-environment"
                                    value={form.environment}
                                    disabled={!canManage || saving}
                                    onChange={(event) => changeEnvironment(event.target.value as CdasEnvironment)}
                                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    <option value="test">Test</option>
                                    <option value="live">Live</option>
                                </select>
                                <p className="text-xs text-muted-foreground">
                                    Changing environment disables CDAS and clears environment-specific credential fields so Test credentials cannot carry into Live.
                                </p>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="cdas-timeout">Request timeout (seconds)</Label>
                                <Input
                                    id="cdas-timeout"
                                    type="number"
                                    min={1}
                                    max={120}
                                    value={form.timeout_seconds}
                                    disabled={!canManage || saving}
                                    onChange={(event) => setForm((current) => ({
                                        ...current,
                                        timeout_seconds: Number(event.target.value),
                                    }))}
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="cdas-base-url">CDAS base URL</Label>
                            <Input
                                id="cdas-base-url"
                                type="url"
                                autoComplete="off"
                                value={form.base_url}
                                disabled={!canManage || saving || form.environment === "test"}
                                onChange={(event) => setForm((current) => ({ ...current, base_url: event.target.value }))}
                                placeholder={form.environment === "live" ? "Enter the Live CDAS HTTPS URL" : CDAS_TEST_BASE_URL}
                            />
                            <p className="text-xs text-muted-foreground">
                                {form.environment === "test"
                                    ? "The Test environment is locked to the official CDAS Test URL."
                                    : "Enter only the HTTPS Live URL supplied by CDAS. The known Test URL is rejected for Live."}
                            </p>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="cdas-username">Username</Label>
                                <Input
                                    id="cdas-username"
                                    autoComplete="off"
                                    value={form.username}
                                    disabled={!canManage || saving}
                                    onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                                />
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="cdas-password">Password</Label>
                                <Input
                                    id="cdas-password"
                                    type="password"
                                    autoComplete="new-password"
                                    value={form.password}
                                    disabled={!canManage || saving || form.clear_password}
                                    onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                                    placeholder={configuration?.password_configured && !environmentChanged ? "Stored securely — enter only to replace" : "Enter CDAS password"}
                                />
                                <p className="text-xs text-muted-foreground">
                                    {configuration?.password_configured && !environmentChanged
                                        ? "A password is stored for the saved environment. LoanHub never sends it back to the browser."
                                        : environmentChanged
                                            ? "Enter the password for the newly selected environment; the previous environment's password will not be reused."
                                            : "No CDAS password is stored for this company yet."}
                                </p>
                            </div>
                        </div>

                        <div className="grid gap-3 rounded-2xl border bg-muted/20 p-4 sm:grid-cols-2">
                            <label className="flex items-start gap-3 text-sm">
                                <Checkbox
                                    checked={form.enabled}
                                    disabled={!canManage || saving}
                                    onCheckedChange={(checked) => setForm((current) => ({ ...current, enabled: checked === true }))}
                                />
                                <span>
                                    <span className="font-bold">Enable CDAS for this company</span>
                                    <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                                        Official CDAS employee, affordability, deduction and document requests will use this account.
                                    </span>
                                </span>
                            </label>

                            <label className="flex items-start gap-3 text-sm">
                                <Checkbox
                                    checked={form.clear_password}
                                    disabled={!canManage || saving || !configuration?.password_configured || environmentChanged}
                                    onCheckedChange={(checked) => setForm((current) => ({
                                        ...current,
                                        clear_password: checked === true,
                                        password: checked === true ? "" : current.password,
                                        enabled: checked === true ? false : current.enabled,
                                    }))}
                                />
                                <span>
                                    <span className="font-bold">Remove stored password</span>
                                    <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                                        This disables the integration until a new password is saved.
                                    </span>
                                </span>
                            </label>
                        </div>

                        {!canManage && (
                            <Alert>
                                <ShieldCheck className="h-4 w-4" />
                                <AlertTitle>Read-only configuration</AlertTitle>
                                <AlertDescription>Only a Company Owner or Company Admin can change or test CDAS credentials.</AlertDescription>
                            </Alert>
                        )}

                        {environmentChanged && (
                            <Alert>
                                <ShieldCheck className="h-4 w-4" />
                                <AlertTitle>Environment change requires new credentials</AlertTitle>
                                <AlertDescription>
                                    Save the URL, username and password for {form.environment === "live" ? "Live" : "Test"}. LoanHub will discard the password stored for the previous environment instead of carrying it across.
                                </AlertDescription>
                            </Alert>
                        )}

                        {form.environment === "live" && (
                            <Alert>
                                <PlugZap className="h-4 w-4" />
                                <AlertTitle>Live CDAS selected</AlertTitle>
                                <AlertDescription>
                                    Confirm the live URL and credentials supplied by CDAS before enabling. LoanHub does not copy test credentials into the live environment automatically.
                                </AlertDescription>
                            </Alert>
                        )}

                        <div className="flex flex-wrap gap-3">
                            <Button type="submit" disabled={!canManage || saving}>
                                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                                Save configuration
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                disabled={!canManage || testing || !configuration?.configured || environmentChanged}
                                onClick={() => void testConnection()}
                            >
                                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlugZap className="h-4 w-4" />}
                                Test saved connection
                            </Button>
                        </div>
                    </form>
                </CardContent>
            </Card>

            <div className="space-y-4">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <KeyRound className="h-4 w-4" /> Credential status
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4 text-sm">
                        <StatusRow label="Environment" value={(configuration?.environment ?? "test").toUpperCase()} />
                        <StatusRow label="URL & username" value={configuration?.base_url && configuration?.username ? "Configured" : "Incomplete"} />
                        <StatusRow label="Password" value={configuration?.password_configured ? "Encrypted & stored" : "Not configured"} />
                        <StatusRow label="Operational state" value={configuration?.enabled ? "Enabled" : "Disabled"} />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            {configuration?.last_test_status === "connected" ? (
                                <CircleCheck className="h-4 w-4 text-emerald-600" />
                            ) : (
                                <PlugZap className="h-4 w-4" />
                            )}
                            Connection test
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm">
                        <p className="font-bold">
                            {configuration?.last_test_status === "connected"
                                ? "Connection verified"
                                : configuration?.last_test_status === "failed"
                                    ? "Last test failed"
                                    : "Not tested since last change"}
                        </p>
                        <p className="text-xs leading-5 text-muted-foreground">
                            {configuration?.last_tested_at
                                ? `Last tested ${new Date(configuration.last_tested_at).toLocaleString()}`
                                : "Save the credentials, then use Test saved connection. The CDAS authorization token is never displayed."}
                        </p>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

function StatusRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-start justify-between gap-4 border-b pb-3 last:border-b-0 last:pb-0">
            <span className="text-muted-foreground">{label}</span>
            <span className="text-right font-bold">{value}</span>
        </div>
    );
}
