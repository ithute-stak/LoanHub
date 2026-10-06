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

type CdasTransaction = {
    id: string;
    transaction_reference: string;
    operation_type: string;
    environment: Environment;
    amount: number;
    currency: string;
    status: string;
    accrued_at: string;
};

type CdasInvoice = {
    id: string;
    invoice_number: string;
    period_start: string;
    period_end: string;
    transaction_count: number;
    amount_due: number;
    currency: string;
    status: string;
    due_at: string;
    paid_at: string | null;
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
    billing_due_days?: number;
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
    const [billingDueDays, setBillingDueDays] = useState("14");
    const [savingProfile, setSavingProfile] = useState(false);
    const [testingProfile, setTestingProfile] = useState(false);
    const [savingDecision, setSavingDecision] = useState(false);
    const [transactions, setTransactions] = useState<CdasTransaction[]>([]);
    const [invoices, setInvoices] = useState<CdasInvoice[]>([]);
    const [adjustmentReason, setAdjustmentReason] = useState("");
    const [invoiceStart, setInvoiceStart] = useState("");
    const [invoiceEnd, setInvoiceEnd] = useState("");
    const [settlementMethod, setSettlementMethod] = useState<"cash" | "bank" | "electronic">("bank");
    const [settlementReference, setSettlementReference] = useState("");
    const [refundMethod, setRefundMethod] = useState<"cash" | "bank" | "electronic">("bank");
    const [refundReference, setRefundReference] = useState("");
    const [billingAction, setBillingAction] = useState<string | null>(null);

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
        setBillingDueDays(String(row?.billing_due_days ?? 14));
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

    const loadBilling = useCallback(async (companyId: string) => {
        if (!companyId) {
            setTransactions([]);
            setInvoices([]);
            return;
        }
        const [transactionResponse, invoiceResponse] = await Promise.all([
            api.get<CdasTransaction[]>(`/platform-owner/cdas/transactions?company_id=${companyId}&limit=30`),
            api.get<CdasInvoice[]>(`/platform-owner/cdas/invoices?company_id=${companyId}&limit=24`),
        ]);
        setTransactions(transactionResponse.data);
        setInvoices(invoiceResponse.data);
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
            await loadBilling(nextId);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Platform CDAS service could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, [environment, hydrateCommercial, hydrateProfile, loadBilling, selectedCompanyId]);

    useEffect(() => { void load(); }, [load]);

    function chooseCompany(companyId: string) {
        setSelectedCompanyId(companyId);
        const row = subscriptions.find((item) => item.company_id === companyId) ?? null;
        hydrateCommercial(row);
        hydrateProfile(row, environment);
        void loadBilling(companyId);
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
                billing_due_days: Number(billingDueDays || 14),
            });
            toast.success(`CDAS subscription ${decision}`);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS subscription decision could not be saved."));
        } finally {
            setSavingDecision(false);
        }
    }

    async function createManualInvoice() {
        if (!selectedCompanyId || !invoiceStart || !invoiceEnd) return;
        setBillingAction("invoice");
        try {
            await api.post(`/platform-owner/cdas/invoices/${selectedCompanyId}`, {
                period_start: invoiceStart,
                period_end: invoiceEnd,
            });
            toast.success("CDAS invoice issued");
            await loadBilling(selectedCompanyId);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS invoice could not be issued."));
        } finally {
            setBillingAction(null);
        }
    }

    async function markInvoicePaid(invoiceId: string) {
        if (!selectedCompanyId) return;
        if (settlementMethod !== "cash" && settlementReference.trim().length < 2) {
            toast.error("Enter the bank/gateway settlement reference.");
            return;
        }
        setBillingAction(`paid:${invoiceId}`);
        try {
            await api.post(`/platform-owner/cdas/invoices/${invoiceId}/paid`, {
                payment_method: settlementMethod,
                proof_reference: settlementReference.trim() || null,
            });
            toast.success("CDAS invoice marked paid");
            await loadBilling(selectedCompanyId);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "CDAS invoice payment could not be recorded."));
        } finally {
            setBillingAction(null);
        }
    }

    async function adjustTransaction(transactionId: string, action: "waive" | "refund") {
        if (!selectedCompanyId || adjustmentReason.trim().length < 3) {
            toast.error("Enter a reason of at least 3 characters.");
            return;
        }
        if (action === "refund" && refundMethod !== "cash" && refundReference.trim().length < 2) {
            toast.error("Enter the bank/gateway refund reference.");
            return;
        }
        setBillingAction(`${action}:${transactionId}`);
        try {
            await api.post(`/platform-owner/cdas/transactions/${transactionId}/${action}`, {
                reason: adjustmentReason.trim(),
                ...(action === "refund" ? {
                    payment_method: refundMethod,
                    proof_reference: refundReference.trim() || null,
                } : {}),
            });
            toast.success(action === "waive" ? "CDAS charge waived" : "CDAS charge refunded");
            setAdjustmentReason("");
            await loadBilling(selectedCompanyId);
            await load();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, `CDAS charge could not be ${action === "waive" ? "waived" : "refunded"}.`));
        } finally {
            setBillingAction(null);
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
                                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                                    <div className="space-y-2"><Label>Currency</Label><Input maxLength={3} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} /></div>
                                    <div className="space-y-2"><Label>Credit limit</Label><Input type="number" min={0} step="0.01" value={creditLimit} onChange={(e) => setCreditLimit(e.target.value)} placeholder="Unlimited" /></div>
                                    <div className="space-y-2"><Label>Warning threshold</Label><Input type="number" min={0} step="0.01" value={warningThreshold} onChange={(e) => setWarningThreshold(e.target.value)} placeholder="Optional" /></div>
                                    <div className="space-y-2"><Label>Invoice due days</Label><Input type="number" min={1} max={90} value={billingDueDays} onChange={(e) => setBillingDueDays(e.target.value)} /></div>
                                </div>
                                <label className="flex items-center gap-3 rounded-2xl border p-4 text-sm font-semibold"><Checkbox checked={autoSuspend} onCheckedChange={(value) => setAutoSuspend(value === true)} />Automatically suspend Live CDAS access when the credit limit would be exceeded</label>
                                <div className="flex flex-wrap gap-2">
                                    <LoadingButton loading={savingDecision} onClick={() => void decide("approved")}>{selected.status === "approved" ? "Save controls" : "Approve subscription"}</LoadingButton>
                                    {selected.status === "approved" ? <LoadingButton loading={savingDecision} variant="outline" onClick={() => void decide("suspended")}>Suspend</LoadingButton> : null}
                                    {selected.status === "pending" ? <LoadingButton loading={savingDecision} variant="outline" onClick={() => void decide("rejected")}>Reject</LoadingButton> : null}
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader><CardTitle>Billing & invoices</CardTitle><CardDescription>Issue exceptional manual invoices, record payment, and review the monthly automated billing cycle.</CardDescription></CardHeader>
                            <CardContent className="space-y-4">
                                <div className="grid gap-3 sm:grid-cols-3">
                                    <div className="space-y-2"><Label>Period start</Label><Input type="date" value={invoiceStart} onChange={(e) => setInvoiceStart(e.target.value)} /></div>
                                    <div className="space-y-2"><Label>Period end</Label><Input type="date" value={invoiceEnd} onChange={(e) => setInvoiceEnd(e.target.value)} /></div>
                                    <div className="flex items-end"><LoadingButton className="w-full" loading={billingAction === "invoice"} disabled={!invoiceStart || !invoiceEnd} onClick={() => void createManualInvoice()}>Issue invoice</LoadingButton></div>
                                </div>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <div className="space-y-2"><Label>Settlement method</Label><Select value={settlementMethod} onValueChange={(value) => setSettlementMethod(value as "cash" | "bank" | "electronic")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="cash">Cash</SelectItem><SelectItem value="bank">Bank</SelectItem><SelectItem value="electronic">Electronic / gateway</SelectItem></SelectContent></Select></div>
                                    <div className="space-y-2"><Label>Settlement reference</Label><Input value={settlementReference} onChange={(e) => setSettlementReference(e.target.value)} placeholder={settlementMethod === "cash" ? "Optional for cash" : "Required bank/gateway reference"} /></div>
                                </div>
                                <div className="space-y-2">
                                    {invoices.length ? invoices.map((invoice) => (
                                        <div key={invoice.id} className="flex flex-col gap-3 rounded-2xl border p-4 lg:flex-row lg:items-center lg:justify-between">
                                            <div><p className="font-black">{invoice.invoice_number}</p><p className="text-xs text-muted-foreground">{invoice.period_start} → {invoice.period_end} · {invoice.transaction_count} operations · due {new Date(invoice.due_at).toLocaleDateString()}</p></div>
                                            <div className="flex items-center gap-2"><Badge variant={invoice.status === "paid" ? "default" : "secondary"}>{titleCase(invoice.status)}</Badge><strong>{formatMoney(invoice.amount_due)}</strong>{invoice.status !== "paid" ? <LoadingButton size="sm" loading={billingAction === `paid:${invoice.id}`} onClick={() => void markInvoicePaid(invoice.id)}>Mark paid</LoadingButton> : null}</div>
                                        </div>
                                    )) : <p className="text-sm text-muted-foreground">No CDAS invoices have been issued for this company.</p>}
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader><CardTitle>Charge adjustments</CardTitle><CardDescription>Waive an unpaid charge or refund a settled charge without deleting financial history.</CardDescription></CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2"><Label>Adjustment reason</Label><Input value={adjustmentReason} onChange={(e) => setAdjustmentReason(e.target.value)} placeholder="Required reason for waiver or refund" /></div>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <div className="space-y-2"><Label>Refund method</Label><Select value={refundMethod} onValueChange={(value) => setRefundMethod(value as "cash" | "bank" | "electronic")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="cash">Cash</SelectItem><SelectItem value="bank">Bank</SelectItem><SelectItem value="electronic">Electronic / gateway</SelectItem></SelectContent></Select></div>
                                    <div className="space-y-2"><Label>Refund reference</Label><Input value={refundReference} onChange={(e) => setRefundReference(e.target.value)} placeholder={refundMethod === "cash" ? "Optional for cash refund" : "Required bank/gateway reference"} /></div>
                                </div>
                                <div className="space-y-2">
                                    {transactions.length ? transactions.map((transaction) => (
                                        <div key={transaction.id} className="flex flex-col gap-3 rounded-2xl border p-4 lg:flex-row lg:items-center lg:justify-between">
                                            <div><p className="font-black">{titleCase(transaction.operation_type)} · {transaction.transaction_reference}</p><p className="text-xs text-muted-foreground">{transaction.environment.toUpperCase()} · {new Date(transaction.accrued_at).toLocaleString()} · {titleCase(transaction.status)}</p></div>
                                            <div className="flex items-center gap-2"><strong>{formatMoney(transaction.amount)}</strong>{transaction.status === "accrued" ? <LoadingButton size="sm" variant="outline" loading={billingAction === `waive:${transaction.id}`} onClick={() => void adjustTransaction(transaction.id, "waive")}>Waive</LoadingButton> : null}{transaction.status === "settled" ? <LoadingButton size="sm" variant="outline" loading={billingAction === `refund:${transaction.id}`} onClick={() => void adjustTransaction(transaction.id, "refund")}>Refund</LoadingButton> : null}</div>
                                        </div>
                                    )) : <p className="text-sm text-muted-foreground">No metered CDAS charges for this company.</p>}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                ) : null}
            </div>
        </main>
    );
}
