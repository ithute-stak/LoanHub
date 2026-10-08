"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, ArrowLeft, CheckCircle2, History, ListChecks, Loader2, RefreshCw, ShieldAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";
import { getErrorMessage } from "@/utils/apiError";

type TransactionItem = {
    source: "provider_operation" | "metered_transaction";
    id: string;
    occurred_at: string;
    operation_type: string;
    state: string;
    employee_no: string | null;
    deduction_id: number | null;
    reference_no: string | null;
    provider_status_code: number | null;
    requires_reconciliation: boolean;
    error_message: string | null;
    actor_user_id: string | null;
    request_snapshot: Record<string, unknown>;
    response_snapshot: Record<string, unknown>;
    amount?: string;
    currency?: string;
    transaction_reference?: string;
};

type DeductionHistoryItem = {
    event_id: string;
    occurred_at: string;
    event_type: string;
    request_type: number | null;
    success: boolean;
    message: string | null;
    provider_status_code: number | null;
    actor_user_id: string | null;
    employee_no: string;
    deduction_id: number | null;
    reference_no: string;
    lifecycle_status: string;
    mandate_status: string;
    request_snapshot: Record<string, unknown>;
    response_snapshot: Record<string, unknown>;
};

type TransactionResponse = { environment: string; items: TransactionItem[]; count: number };
type DeductionResponse = { items: DeductionHistoryItem[]; count: number };

function titleCase(value: string) {
    return value.replaceAll("_", " ").replaceAll(".", " · ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function when(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function JsonBlock({ title, value }: { title: string; value: Record<string, unknown> }) {
    return (
        <div className="overflow-hidden rounded-2xl border">
            <div className="border-b bg-muted/40 px-4 py-3 text-sm font-black">{title}</div>
            <pre className="max-h-72 overflow-auto p-4 text-xs leading-5">{JSON.stringify(value, null, 2)}</pre>
        </div>
    );
}

export default function CdasHistoryPage() {
    const searchParams = useSearchParams();
    const { activeRole } = useTenant();
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const initialTab = searchParams.get("tab") === "deductions" ? "deductions" : "transactions";
    const [tab, setTab] = useState<"transactions" | "deductions">(initialTab);
    const [transactions, setTransactions] = useState<TransactionItem[]>([]);
    const [deductions, setDeductions] = useState<DeductionHistoryItem[]>([]);
    const [environment, setEnvironment] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selected, setSelected] = useState<{ title: string; request: Record<string, unknown>; response: Record<string, unknown> } | null>(null);

    const load = useCallback(async () => {
        if (!canManage) return;
        setLoading(true);
        setError(null);
        try {
            const [transactionResponse, deductionResponse] = await Promise.all([
                api.get<TransactionResponse>("/cdas/history/transactions?limit=200"),
                api.get<DeductionResponse>("/cdas/history/deductions?limit=200"),
            ]);
            setTransactions(transactionResponse.data.items);
            setEnvironment(transactionResponse.data.environment);
            setDeductions(deductionResponse.data.items);
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS history could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, [canManage]);

    useEffect(() => {
        void load();
    }, [load]);

    const reconciliationCount = useMemo(
        () => transactions.filter((item) => item.requires_reconciliation).length,
        [transactions],
    );

    if (!canManage) {
        return (
            <div className="loanhub-page space-y-5">
                <Button asChild variant="ghost"><Link href="/company/cdas"><ArrowLeft className="h-4 w-4" /> Back to CDAS workspace</Link></Button>
                <Alert variant="destructive">
                    <ShieldAlert className="h-4 w-4" />
                    <AlertTitle>Company management permission required</AlertTitle>
                    <AlertDescription>CDAS transaction and deduction history is restricted to company management.</AlertDescription>
                </Alert>
            </div>
        );
    }

    return (
        <div className="loanhub-page space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <Button asChild variant="ghost"><Link href="/company/cdas"><ArrowLeft className="h-4 w-4" /> Back to CDAS workspace</Link></Button>
                <div className="flex items-center gap-2">
                    {environment ? <Badge variant="outline">{environment.toUpperCase()}</Badge> : null}
                    <Button variant="outline" onClick={() => void load()} disabled={loading}>
                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                        Refresh
                    </Button>
                </div>
            </div>

            <section className="rounded-3xl border bg-card p-6 shadow-sm">
                <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">Original CDAS reporting parity</p>
                <h1 className="mt-2 text-3xl font-black tracking-tight">CDAS transaction & deduction history</h1>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
                    CDAS API v1.5 does not expose portal transaction-log or deduction-history endpoints. LoanHub reconstructs these views from its durable provider-operation ledger, PAYG transaction ledger and append-only official mandate events.
                </p>
            </section>

            <div className="grid gap-4 sm:grid-cols-3">
                <Card><CardHeader className="pb-2"><CardDescription>Transactions loaded</CardDescription><CardTitle>{transactions.length}</CardTitle></CardHeader></Card>
                <Card><CardHeader className="pb-2"><CardDescription>Deduction events loaded</CardDescription><CardTitle>{deductions.length}</CardTitle></CardHeader></Card>
                <Card><CardHeader className="pb-2"><CardDescription>Need reconciliation</CardDescription><CardTitle>{reconciliationCount}</CardTitle></CardHeader></Card>
            </div>

            {error ? (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>CDAS history unavailable</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            ) : null}

            <div className="flex flex-wrap gap-2">
                <Button variant={tab === "transactions" ? "default" : "outline"} onClick={() => setTab("transactions")}>
                    <ListChecks className="h-4 w-4" /> Transaction log
                </Button>
                <Button variant={tab === "deductions" ? "default" : "outline"} onClick={() => setTab("deductions")}>
                    <History className="h-4 w-4" /> Deduction history
                </Button>
            </div>

            {tab === "transactions" ? (
                <Card>
                    <CardHeader>
                        <CardTitle>Transaction log</CardTitle>
                        <CardDescription>Provider mutations and metered CDAS business operations recorded by LoanHub.</CardDescription>
                    </CardHeader>
                    <CardContent className="overflow-x-auto p-0">
                        <table className="w-full min-w-[1050px] text-sm">
                            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                                <tr><th className="px-5 py-4">Time</th><th className="px-4 py-4">Operation</th><th className="px-4 py-4">Employee / deduction</th><th className="px-4 py-4">State</th><th className="px-4 py-4">Provider</th><th className="px-5 py-4 text-right">Details</th></tr>
                            </thead>
                            <tbody>
                                {transactions.map((item) => (
                                    <tr key={item.source + "-" + item.id} className="border-t">
                                        <td className="px-5 py-4 font-semibold">{when(item.occurred_at)}</td>
                                        <td className="px-4 py-4"><p className="font-black">{titleCase(item.operation_type)}</p><p className="text-xs text-muted-foreground">{item.source === "provider_operation" ? "Provider operation" : item.transaction_reference || "Metered transaction"}</p></td>
                                        <td className="px-4 py-4"><p className="font-bold">{item.employee_no || "—"}</p><p className="text-xs text-muted-foreground">{item.deduction_id ? "Deduction #" + item.deduction_id : item.reference_no || "No deduction ID"}</p></td>
                                        <td className="px-4 py-4"><Badge variant={item.requires_reconciliation ? "destructive" : "outline"}>{titleCase(item.state)}</Badge>{item.error_message ? <p className="mt-1 max-w-64 text-xs text-destructive">{item.error_message}</p> : null}</td>
                                        <td className="px-4 py-4">{item.provider_status_code ?? "—"}</td>
                                        <td className="px-5 py-4 text-right"><Button size="sm" variant="outline" onClick={() => setSelected({ title: titleCase(item.operation_type), request: item.request_snapshot, response: item.response_snapshot })}>Inspect</Button></td>
                                    </tr>
                                ))}
                                {!loading && transactions.length === 0 ? <tr><td colSpan={6} className="px-5 py-12 text-center text-muted-foreground">No CDAS transactions have been recorded yet.</td></tr> : null}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardHeader>
                        <CardTitle>Deduction history</CardTitle>
                        <CardDescription>Append-only lifecycle evidence for LoanHub-linked CDAS deductions.</CardDescription>
                    </CardHeader>
                    <CardContent className="overflow-x-auto p-0">
                        <table className="w-full min-w-[1050px] text-sm">
                            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                                <tr><th className="px-5 py-4">Time</th><th className="px-4 py-4">Employee</th><th className="px-4 py-4">Deduction</th><th className="px-4 py-4">Event</th><th className="px-4 py-4">Status</th><th className="px-5 py-4 text-right">Evidence</th></tr>
                            </thead>
                            <tbody>
                                {deductions.map((item) => (
                                    <tr key={item.event_id} className="border-t">
                                        <td className="px-5 py-4 font-semibold">{when(item.occurred_at)}</td>
                                        <td className="px-4 py-4 font-bold">{item.employee_no}</td>
                                        <td className="px-4 py-4"><p className="font-bold">{item.deduction_id ? "#" + item.deduction_id : "Pending ID"}</p><p className="text-xs text-muted-foreground">{item.reference_no}</p></td>
                                        <td className="px-4 py-4"><p className="font-black">{titleCase(item.event_type)}</p><p className="text-xs text-muted-foreground">{item.message || "No message"}</p></td>
                                        <td className="px-4 py-4"><Badge variant={item.success ? "outline" : "destructive"}>{titleCase(item.lifecycle_status)}</Badge></td>
                                        <td className="px-5 py-4 text-right"><Button size="sm" variant="outline" onClick={() => setSelected({ title: titleCase(item.event_type), request: item.request_snapshot, response: item.response_snapshot })}>Inspect</Button></td>
                                    </tr>
                                ))}
                                {!loading && deductions.length === 0 ? <tr><td colSpan={6} className="px-5 py-12 text-center text-muted-foreground">No CDAS deduction lifecycle events have been recorded yet.</td></tr> : null}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            )}

            <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertTitle>Evidence source</AlertTitle>
                <AlertDescription>
                    These views are generated from LoanHub&apos;s own durable records. They do not consume the CDAS 400-request daily allowance and do not claim to be undocumented provider endpoints.
                </AlertDescription>
            </Alert>

            <Dialog open={selected !== null} onOpenChange={(open) => { if (!open) setSelected(null); }}>
                <DialogContent className="sm:max-w-5xl">
                    <DialogHeader>
                        <DialogTitle>{selected?.title || "CDAS evidence"}</DialogTitle>
                        <DialogDescription>Request and response evidence retained by LoanHub.</DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 lg:grid-cols-2">
                        <JsonBlock title="Request" value={selected?.request || {}} />
                        <JsonBlock title="Response" value={selected?.response || {}} />
                    </div>
                    <DialogFooter showCloseButton />
                </DialogContent>
            </Dialog>
        </div>
    );
}
