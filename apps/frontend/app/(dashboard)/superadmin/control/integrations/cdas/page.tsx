"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, CircleCheck, KeyRound, RefreshCcw, Save, ShieldCheck, TestTube2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { formatMoney, titleCase } from "@/lib/format";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type Environment = "test" | "live";

type Profile = {
    id?: string;
    environment: Environment | null;
    configured: boolean;
    base_url?: string;
    username?: string;
    item_code?: string | null;
    timeout_seconds?: number;
    password_configured?: boolean;
    last_test_status: string | null;
    last_tested_at: string | null;
};

type Subscription = {
    id?: string;
    company_id?: string;
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
    company?: { id: string; name: string; registration_number?: string | null; license_number?: string | null };
    profiles?: { test: Profile; live: Profile };
};

const TEST_URL = "https://test-cdas-thirdpartyapi.sentraptt.com";
const PRICE_FIELDS = [
    ["employee_verification", "Employee verification"],
    ["affordability", "Affordability"],
    ["deduction_lookup", "Deduction lookup"],
    ["registration", "Registration"],
    ["lifecycle", "Lifecycle"],
    ["modification", "Modification"],
    ["settlement", "Settlement"],
    ["document", "Document"],
] as const;

export default function PlatformCdasPage() {
    const [loading, setLoading] = useState(true);
    const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
    const [selectedCompanyId, setSelectedCompanyId] = useState("");
    const [environment, setEnvironment] = useState<Environment>("test");
    const [baseUrl, setBaseUrl] = useState(TEST_URL);
    const [username, setUsername] = useState("");
    const [itemCode, setItemCode] = useState("");
    const [password, setPassword] = useState("");
    const [timeoutSeconds, setTimeoutSeconds] = useState("20");
    const [pricing, setPricing] = useState<Record<string, string>>({});
    const [currency, setCurrency] = useState("LSL");
    const [creditLimit, setCreditLimit] = useState("");
    const [warningThreshold, setWarningThreshold] = useState("");
    const [autoSuspend, setAutoSuspend] = useState(true);
    const [savingProfile, setSavingProfile] = useState(false);
    const [testingProfile, setTestingProfile] = useState(false);
    const [savingDecision, setSavingDecision] = useState(false);

    const selected = useMemo(
        () => subscriptions.find((item) => item.company_id === selectedCompanyId) ?? null,
        [subscriptions, selectedCompanyId],
    );
    const selectedProfile = selected?.profiles?.[environment];

    const hydrateCommercial = useCallback((row: Subscription | null) => {
        setCurrency(row?.currency || "LSL");
        setCreditLimit(row?.credit_limit == null ? "" : String(row.credit_limit));
        setWarningThreshold(row?.warning_threshold == null ? "" : String(row.warning_threshold));
        setAutoSuspend(row?.auto_suspend_on_limit !== false);
        setPricing(Object.fromEntries(PRICE_FIELDS.map(([key]) => [key, String(row?.pricing?.[key] ?? 0)])));
    }, []);

    const hydrateProfile = useCallback((row: Subscription | null, env: Environment) => {
        const profile = row?.profiles?.[env];
        setBaseUrl(profile?.base_url || (env === "test" ? TEST_URL : ""));
        setUsername(profile?.username || "");
        setItemCode(profile?.item_code || "");
        setPassword("");
        setTimeoutSeconds(String(profile?.timeout_seconds ?? 20));
    }, []);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const response = await api.get<Subscription[]>("/platform-owner/cdas/subscriptions");
            setSubscriptions(response.data);
            const nextId = selectedCompanyId || response.data[0]?.company_id || "";
            setSelectedCompanyId(nextId);
            const row = response.data.find((item) => item.company_id === nextId) ?? null;
            hydrateCommercial(row);
            hydrateProfile(row, environment);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Platform CDAS service could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, [environment, hydrateCommercial, hydrateProfile, selectedCompanyId]);

    useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

    function chooseCompany(companyId: string) {
        setSelectedCompanyId(companyId);
        const row = subscriptions.find((item) => item.company_id === companyId) ?? null;
        hydrateCommercial(row);
        hydrateProfile(row, environment);
    }

    function chooseEnvironment(value: Environment) {
        setEnvironment(value);
        hydrateProfile(selected, value);
    }

    async function saveProfile() {
        if (!selectedCompanyId) return;
        setSavingProfile(true);
        try {
            await api.put(`/platform-owner/cdas/companies/${selectedCompanyId}/profiles/${environment}`, {
                base_url: baseUrl.trim(),
                username: username.trim(),
                item_code: itemCode.trim() || null,
                password: password || null,
                timeout_seconds: Number(timeoutSeconds || 20),
            });
            toast.success(`CDAS ${environment.toUpperCase()} profile saved`);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS credential profile could not be saved."));
        } finally {
            setSavingProfile(false);
        }
    }

    async function testProfile() {
        if (!selectedCompanyId) return;
        setTestingProfile(true);
        try {
            await api.post(`/platform-owner/cdas/companies/${selectedCompanyId}/profiles/${environment}/test`);
            toast.success(`CDAS ${environment.toUpperCase()} login verified`);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS profile test failed."));
        } finally {
            setTestingProfile(false);
        }
    }

    async function decide(decision: "approved" | "rejected" | "suspended") {
        if (!selectedCompanyId) return;
        setSavingDecision(true);
        try {
            await api.post(`/platform-owner/cdas/subscriptions/${selectedCompanyId}/decision`, {
                decision,
                currency: currency.trim().toUpperCase() || "LSL",
                pricing: Object.fromEntries(PRICE_FIELDS.map(([key]) => [key, Math.max(0, Number(pricing[key] || 0))])),
                credit_limit: creditLimit.trim() ? Number(creditLimit) : null,
                warning_threshold: warningThreshold.trim() ? Number(warningThreshold) : null,
                auto_suspend_on_limit: autoSuspend,
            });
            toast.success(`CDAS subscription ${decision}`);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS subscription decision could not be saved."));
        } finally {
            setSavingDecision(false);
        }
    }

    if (loading) return <PageLoader rows={10} />;

    return (
        <main className="loanhub-page space-y-6">
            <section className="loanhub-hero p-6 sm:p-8">
                <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
                    <div>
                        <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Platform configuration · CDAS</p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">CDAS platform service</h1>
                        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                            Loan companies retain their own CDAS account identity and Item Code, while LoanHub Platform Owner controls credential custody, profile testing, subscription approval, pricing and credit exposure.
                        </p>
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" asChild><Link href="/superadmin/control/integrations"><ArrowLeft className="h-4 w-4" />API & integrations</Link></Button>
                        <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh</Button>
                    </div>
                </div>
            </section>

            <Alert>
                <ShieldCheck className="h-4 w-4" />
                <AlertTitle>Credential custody boundary</AlertTitle>
                <AlertDescription>CDAS usernames, passwords, Item Codes and endpoints are Platform Owner controlled. Lending companies can only request access and their Company Owner can choose between approved Test and Live profiles.</AlertDescription>
            </Alert>

            <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
                <Card>
                    <CardHeader><CardTitle>Loan companies</CardTitle><CardDescription>Subscription queue and current status.</CardDescription></CardHeader>
                    <CardContent className="space-y-2">
                        {subscriptions.length ? subscriptions.map((row) => (
                            <button key={row.company_id} type="button" onClick={() => row.company_id && chooseCompany(row.company_id)} className={`w-full rounded-2xl border p-4 text-left transition ${row.company_id === selectedCompanyId ? "border-primary bg-primary/5" : "hover:border-primary/40"}`}>
                                <div className="flex items-center justify-between gap-2"><p className="font-black">{row.company?.name || row.company_id}</p><Badge variant={row.status === "approved" ? "default" : "secondary"}>{titleCase(row.status)}</Badge></div>
                                <p className="mt-2 text-xs text-muted-foreground">Outstanding {formatMoney(row.usage?.outstanding_balance ?? 0)} · Live ops {row.usage?.live_transaction_count ?? 0}</p>
                            </button>
                        )) : <p className="text-sm text-muted-foreground">No company has requested CDAS access yet.</p>}
                    </CardContent>
                </Card>

                {selected ? (
                    <div className="space-y-5">
                        <Card>
                            <CardHeader><CardTitle className="flex items-center gap-2"><KeyRound className="h-5 w-5" />Company-specific CDAS profile</CardTitle><CardDescription>Store Test and Live credentials separately. Passwords are never returned after saving.</CardDescription></CardHeader>
                            <CardContent className="space-y-5">
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <div className="space-y-2"><Label>Profile</Label><Select value={environment} onValueChange={(value) => chooseEnvironment(value as Environment)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="test">Test</SelectItem><SelectItem value="live">Live</SelectItem></SelectContent></Select></div>
                                    <div className="rounded-2xl border p-4"><p className="text-xs font-bold uppercase text-muted-foreground">Connection</p><p className="mt-2 flex items-center gap-2 text-sm font-black">{selectedProfile?.last_test_status === "connected" ? <CircleCheck className="h-4 w-4 text-emerald-600" /> : null}{selectedProfile?.last_test_status ? titleCase(selectedProfile.last_test_status) : "Not tested"}</p></div>
                                </div>
                                <div className="space-y-2"><Label>Base URL</Label><Input value={baseUrl} disabled={environment === "test"} onChange={(e) => setBaseUrl(e.target.value)} /></div>
                                <div className="grid gap-4 md:grid-cols-3">
                                    <div className="space-y-2"><Label>Username</Label><Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" /></div>
                                    <div className="space-y-2"><Label>Item Code</Label><Input value={itemCode} onChange={(e) => setItemCode(e.target.value)} /></div>
                                    <div className="space-y-2"><Label>Password</Label><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={selectedProfile?.configured ? "Leave blank to keep stored password" : "Required"} autoComplete="new-password" /></div>
                                </div>
                                <div className="space-y-2 max-w-56"><Label>Timeout seconds</Label><Input type="number" min={1} max={120} value={timeoutSeconds} onChange={(e) => setTimeoutSeconds(e.target.value)} /></div>
                                <div className="flex flex-wrap gap-2">
                                    <LoadingButton loading={savingProfile} onClick={() => void saveProfile()}><Save className="h-4 w-4" />Save profile</LoadingButton>
                                    <LoadingButton loading={testingProfile} variant="outline" disabled={!selectedProfile?.configured} onClick={() => void testProfile()}><TestTube2 className="h-4 w-4" />Test login</LoadingButton>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader><CardTitle>PAYG pricing & credit controls</CardTitle><CardDescription>Test operations are always M0.00. These rates apply only to successful Live business operations.</CardDescription></CardHeader>
                            <CardContent className="space-y-5">
                                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                                    {PRICE_FIELDS.map(([key, label]) => <div key={key} className="space-y-2"><Label>{label}</Label><Input type="number" min={0} step="0.01" value={pricing[key] ?? "0"} onChange={(e) => setPricing((current) => ({ ...current, [key]: e.target.value }))} /></div>)}
                                </div>
                                <div className="grid gap-4 sm:grid-cols-3">
                                    <div className="space-y-2"><Label>Currency</Label><Input maxLength={3} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} /></div>
                                    <div className="space-y-2"><Label>Credit limit</Label><Input type="number" min={0} step="0.01" value={creditLimit} onChange={(e) => setCreditLimit(e.target.value)} placeholder="Unlimited" /></div>
                                    <div className="space-y-2"><Label>Warning threshold</Label><Input type="number" min={0} step="0.01" value={warningThreshold} onChange={(e) => setWarningThreshold(e.target.value)} placeholder="Optional" /></div>
                                </div>
                                <label className="flex items-center gap-3 rounded-2xl border p-4 text-sm font-semibold"><Checkbox checked={autoSuspend} onCheckedChange={(value) => setAutoSuspend(value === true)} />Automatically suspend Live CDAS access when the credit limit would be exceeded</label>
                                <div className="flex flex-wrap gap-2">
                                    <LoadingButton loading={savingDecision} onClick={() => void decide("approved")}>{selected.status === "approved" ? "Save controls" : "Approve subscription"}</LoadingButton>
                                    {selected.status === "approved" ? <LoadingButton loading={savingDecision} variant="outline" onClick={() => void decide("suspended")}>Suspend</LoadingButton> : null}
                                    {selected.status === "pending" ? <LoadingButton loading={savingDecision} variant="outline" onClick={() => void decide("rejected")}>Reject</LoadingButton> : null}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                ) : null}
            </div>
        </main>
    );
}
