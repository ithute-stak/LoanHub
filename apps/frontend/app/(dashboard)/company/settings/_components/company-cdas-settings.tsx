"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CircleCheck, CircleX, KeyRound, Loader2, PlugZap, RefreshCcw, Save, ShieldCheck } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
    reintegration_phase: "manual_documented_operations";
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

type Props = { canManage: boolean };

const TEST_URL = "https://test-cdas-thirdpartyapi.sentraptt.com";

const EMPTY_FORM: CdasForm = {
    environment: "test",
    enabled: false,
    base_url: TEST_URL,
    username: "",
    password: "",
    clear_password: false,
    timeout_seconds: 20,
};

function fromConfiguration(configuration: CdasConfiguration): CdasForm {
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
    const [form, setForm] = useState<CdasForm>(EMPTY_FORM);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setLoadError(null);
        try {
            const response = await api.get<CdasConfiguration>("/cdas/configuration");
            setConfiguration(response.data);
            setForm(fromConfiguration(response.data));
        } catch (error: unknown) {
            setLoadError(getErrorMessage(error, "CDAS authentication configuration could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    function changeEnvironment(environment: CdasEnvironment) {
        setForm((current) => ({
            ...current,
            environment,
            enabled: false,
            base_url: environment === "test" ? TEST_URL : "",
            username: "",
            password: "",
            clear_password: false,
        }));
    }

    async function save(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canManage || saving) return;
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
            setForm(fromConfiguration(response.data));
            toast.success("CDAS authentication configuration saved.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS authentication configuration could not be saved."));
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
            setForm(fromConfiguration(response.data.configuration));
            toast.success("CDAS login verified successfully.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS login test failed."));
            await load();
        } finally {
            setTesting(false);
        }
    }

    if (loading) {
        return (
            <Card>
                <CardContent className="flex min-h-48 items-center justify-center gap-3 text-sm text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" /> Loading CDAS authentication configuration…
                </CardContent>
            </Card>
        );
    }

    if (loadError) {
        return (
            <Alert variant="destructive">
                <CircleX className="h-4 w-4" />
                <AlertTitle>CDAS authentication unavailable</AlertTitle>
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
                                <KeyRound className="h-5 w-5" /> CDAS authentication
                            </CardTitle>
                            <CardDescription className="mt-2 max-w-3xl">
                                Secure company-specific CDAS credentials. LoanHub uses this authentication foundation for deliberate, documented CDAS operations only. Employee, affordability, deduction and document requests are initiated by a user; no background CDAS crawling or automatic lifecycle processing is enabled.
                            </CardDescription>
                        </div>
                        <Badge variant={configuration?.enabled ? "default" : "secondary"}>
                            {configuration?.enabled ? "CDAS enabled" : "CDAS disabled"}
                        </Badge>
                    </div>
                </CardHeader>
                <CardContent>
                    <form className="space-y-5" onSubmit={save}>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="cdas-environment">Environment</Label>
                                <select
                                    id="cdas-environment"
                                    value={form.environment}
                                    disabled={!canManage || saving}
                                    onChange={(event) => changeEnvironment(event.target.value as CdasEnvironment)}
                                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                                >
                                    <option value="test">Test</option>
                                    <option value="live">Live</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="cdas-timeout">Timeout seconds</Label>
                                <Input
                                    id="cdas-timeout"
                                    type="number"
                                    min={1}
                                    max={120}
                                    value={form.timeout_seconds}
                                    disabled={!canManage || saving}
                                    onChange={(event) => setForm((current) => ({ ...current, timeout_seconds: Number(event.target.value) }))}
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="cdas-base-url">Base URL</Label>
                            <Input
                                id="cdas-base-url"
                                value={form.base_url}
                                disabled={!canManage || saving || form.environment === "test"}
                                onChange={(event) => setForm((current) => ({ ...current, base_url: event.target.value }))}
                                placeholder="https://..."
                            />
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="cdas-username">Username</Label>
                                <Input
                                    id="cdas-username"
                                    value={form.username}
                                    disabled={!canManage || saving}
                                    onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                                    autoComplete="off"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="cdas-password">Password</Label>
                                <Input
                                    id="cdas-password"
                                    type="password"
                                    value={form.password}
                                    disabled={!canManage || saving || form.clear_password}
                                    onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                                    placeholder={configuration?.password_configured ? "Leave blank to keep stored password" : "Enter CDAS password"}
                                    autoComplete="new-password"
                                />
                            </div>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2">
                            <label className="flex items-center gap-2 rounded-xl border p-3 text-sm font-medium">
                                <input
                                    type="checkbox"
                                    checked={form.enabled}
                                    disabled={!canManage || saving}
                                    onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))}
                                />
                                Enable CDAS
                            </label>
                            <label className="flex items-center gap-2 rounded-xl border p-3 text-sm font-medium">
                                <input
                                    type="checkbox"
                                    checked={form.clear_password}
                                    disabled={!canManage || saving || Boolean(form.password)}
                                    onChange={(event) => setForm((current) => ({ ...current, clear_password: event.target.checked }))}
                                />
                                Clear stored password
                            </label>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            <Button type="submit" disabled={!canManage || saving}>
                                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                                Save configuration
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                disabled={!canManage || testing || !configuration?.configured}
                                onClick={() => void testConnection()}
                            >
                                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlugZap className="h-4 w-4" />}
                                Test login
                            </Button>
                            <Button asChild type="button" variant="outline">
                                <Link href="/company/cdas"><ShieldCheck className="h-4 w-4" /> Open CDAS workspace</Link>
                            </Button>
                        </div>
                    </form>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Integration status</CardTitle>
                    <CardDescription>Manual documented CDAS operations with no background provider polling.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Credential storage</span>
                        <strong>{configuration?.password_configured ? "Configured" : "Not configured"}</strong>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Last login test</span>
                        <strong>{configuration?.last_test_status ?? "Not tested"}</strong>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Tested at</span>
                        <strong>{configuration?.last_tested_at ? new Date(configuration.last_tested_at).toLocaleString() : "—"}</strong>
                    </div>
                    <Alert>
                        {configuration?.last_test_status === "connected" ? <CircleCheck className="h-4 w-4" /> : <KeyRound className="h-4 w-4" />}
                        <AlertTitle>Authentication foundation</AlertTitle>
                        <AlertDescription>
                            A successful login test proves token acquisition only. Each employee, affordability, deduction or document operation remains a separate deliberate request in the CDAS workspace.
                        </AlertDescription>
                    </Alert>
                </CardContent>
            </Card>
        </div>
    );
}
