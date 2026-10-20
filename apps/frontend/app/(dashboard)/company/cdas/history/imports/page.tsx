"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";
import { getErrorMessage } from "@/utils/apiError";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Batch = { id: string; source_filename: string; source_sha256: string; status: string; row_count: number; invalid_count: number; duplicate_count: number; created_at: string };
type RecordRow = { id: string; line_number: number; employee_no: string; employee_name: string | null; policy_reference: string; monthly_amount: string; principal_amount: string; total_installments: number; starting_month: string | null; ending_month: string | null; reconciliation_status: string };
type RowPage = { items: RecordRow[]; total: number; page: number; page_size: number; batch_id: string; status: string };

export default function CdasHistoricalReviewPage() {
    const { activeRole } = useTenant();
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const [batches, setBatches] = useState<Batch[]>([]);
    const [selected, setSelected] = useState<string | null>(null);
    const [rows, setRows] = useState<RowPage | null>(null);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<{valid_count:number; invalid_count:number; duplicate_count:number; source_sha256?:string; reconciliation?:{counts:Record<string,number>}; persisted:boolean} | null>(null);
    const [staging, setStaging] = useState(false);
    const [notice, setNotice] = useState<string | null>(null);
    const [reviewReason, setReviewReason] = useState("");
    const [reviewing, setReviewing] = useState<string | null>(null);
    async function reviewRow(rowId: string, decision: "approved" | "rejected") {
        if (!selected || reviewing || reviewReason.trim().length < 10) return;
        setReviewing(rowId);
        setError(null);
        try {
            await api.post(`/cdas/history/import/batches/${encodeURIComponent(selected)}/rows/${encodeURIComponent(rowId)}/review`, { decision, reason: reviewReason.trim() });
            const response = await api.get<RowPage>(`/cdas/history/import/batches/${encodeURIComponent(selected)}/rows?page=${page}&limit=50`);
            setRows(response.data);
            setReviewReason("");
            setNotice("Historical evidence reviewed. No financial posting was performed.");
        } catch (e) { setError(getErrorMessage(e, "Historical row review failed.")); }
        finally { setReviewing(null); }
    }

    async function submitHistoryFile(mode: "preview" | "stage") {
        if (!uploadFile || staging) return;
        setStaging(true);
        setError(null);
        setNotice(null);
        try {
            const form = new FormData();
            form.append("file", uploadFile);
            const response = await api.post(`/cdas/history/import/${mode}`, form);
            if (mode === "preview") setPreview(response.data);
            else {
                setNotice("Historical CSV safely staged for independent review; no financial postings were made.");
                setPreview(null);
                setUploadFile(null);
                await loadBatches();
            }
        } catch (e) { setError(getErrorMessage(e, "CDAS historical file processing failed.")); }
        finally { setStaging(false); }
    }

    const loadBatches = useCallback(async () => {
        if (!canManage) return;
        setLoading(true);
        setError(null);
        try {
            const response = await api.get<{ items: Batch[] }>("/cdas/history/import/batches");
            setBatches(response.data.items);
        } catch (e) { setError(getErrorMessage(e, "Unable to load historical CDAS batches.")); }
        finally { setLoading(false); }
    }, [canManage]);

    useEffect(() => { void loadBatches(); }, [loadBatches]);
    useEffect(() => {
        if (!canManage || !selected) { setRows(null); return; }
        let alive = true;
        setLoading(true);
        api.get<RowPage>(`/cdas/history/import/batches/${encodeURIComponent(selected)}/rows?page=${page}&limit=50`)
            .then((response) => { if (alive) { setRows(response.data); setError(null); } })
            .catch((e: unknown) => { if (alive) setError(getErrorMessage(e, "Unable to retrieve historical CDAS rows.")); })
            .finally(() => { if (alive) setLoading(false); });
        return () => { alive = false; };
    }, [canManage, selected, page]);

    return <div className="loanhub-page space-y-6">
        <Button asChild variant="ghost"><Link href="/company/cdas/history"><ArrowLeft className="h-4 w-4" /> CDAS transaction history</Link></Button>
        <div><h1 className="text-3xl font-bold">Historical CDAS imports</h1><p className="text-sm text-muted-foreground">Pre-integration portal exports are kept separate from live deductions and financial postings.</p></div>
        {!canManage ? <Card><CardContent className="p-5">Company management permission required.</CardContent></Card> : <>
            {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
            {notice ? <p role="status" className="text-sm font-medium">{notice}</p> : null}
            <Card><CardHeader><CardTitle>Upload historical CDAS CSV</CardTitle><CardDescription>Preview the exported file first. Staging stores a separate review copy; it never creates a deduction, posts a payment or adjusts an outstanding balance.</CardDescription></CardHeader><CardContent className="space-y-3">
                <input type="file" accept=".csv,text/csv" aria-label="Historical CDAS CSV" onChange={(event) => { setUploadFile(event.target.files?.[0] ?? null); setPreview(null); }} className="block w-full text-sm" />
                <div className="flex flex-wrap gap-2">
                    <Button variant="outline" disabled={!uploadFile || staging} onClick={() => void submitHistoryFile("preview")}>Validate and preview</Button>
                    <Button disabled={!uploadFile || staging || !preview || preview.valid_count === 0 || preview.invalid_count > 0 || preview.persisted} onClick={() => void submitHistoryFile("stage")}>Confirm staging</Button>
                </div>
                {preview ? <div className="rounded-lg border p-3 text-sm"><p>Valid: {preview.valid_count} · Invalid: {preview.invalid_count} · Duplicate: {preview.duplicate_count}</p><p className="mt-1">This preview has not imported financial transactions.</p>{preview.reconciliation ? <p className="mt-1">Reconciliation: {Object.entries(preview.reconciliation.counts).map(([key, count]) => `${key}: ${count}`).join(" · ")}</p> : null}</div> : null}
            </CardContent></Card>
            <Card><CardHeader><CardTitle>Imported files</CardTitle><CardDescription>Staged records awaiting independent reconciliation; no payments are posted.</CardDescription></CardHeader><CardContent className="space-y-3">
                <Button variant="outline" disabled={loading} onClick={() => void loadBatches()}><RefreshCw className="h-4 w-4" /> Refresh</Button>
                {batches.length === 0 && !loading ? <p className="text-sm text-muted-foreground">No historical CDAS files have been staged yet.</p> : null}
                <div className="grid gap-2">{batches.map((batch) => <button type="button" key={batch.id} onClick={() => { setSelected(batch.id); setPage(1); }} className="rounded-lg border p-3 text-left hover:bg-muted/40" aria-pressed={selected === batch.id}>
                    <span className="font-semibold">{batch.source_filename}</span><span className="ml-2 text-xs text-muted-foreground">{batch.status} · {batch.row_count} rows · {batch.duplicate_count} duplicates</span><span className="block text-xs text-muted-foreground">Source SHA-256: {batch.source_sha256}</span>
                </button>)}</div>
            </CardContent></Card>
            {rows ? <Card><CardHeader><CardTitle>Staged historical records</CardTitle><CardDescription>Read-only review, batch status: {rows.status}</CardDescription></CardHeader><CardContent>
                <label className="block text-sm font-semibold">Review reason (minimum 10 characters)<input className="mt-1 block w-full rounded-md border bg-background p-2 font-normal" value={reviewReason} maxLength={1000} onChange={(e) => setReviewReason(e.target.value)} placeholder="Document why these historic records should be accepted or rejected" /></label>
                <div className="overflow-x-auto"><table className="w-full min-w-[1000px] text-sm"><thead><tr className="border-b text-left"><th className="p-2">Employee</th><th className="p-2">Policy reference</th><th className="p-2">Monthly amount</th><th className="p-2">Principal</th><th className="p-2">Installments</th><th className="p-2">Start / end</th><th className="p-2">Review status</th><th className="p-2">Decision</th></tr></thead><tbody>{rows.items.map((row) => <tr key={row.id} className="border-b"><td className="p-2">{row.employee_name || "—"}<span className="block text-muted-foreground">{row.employee_no}</span></td><td className="p-2">{row.policy_reference}</td><td className="p-2">{row.monthly_amount}</td><td className="p-2">{row.principal_amount}</td><td className="p-2">{row.total_installments}</td><td className="p-2">{row.starting_month || "—"} / {row.ending_month || "—"}</td><td className="p-2">{row.reconciliation_status}</td><td className="p-2">{row.reconciliation_status === "pending" ? <div className="flex gap-2"><Button size="sm" disabled={reviewing !== null || reviewReason.trim().length < 10} onClick={() => void reviewRow(row.id, "approved")}>Approve</Button><Button size="sm" variant="outline" disabled={reviewing !== null || reviewReason.trim().length < 10} onClick={() => void reviewRow(row.id, "rejected")}>Reject</Button></div> : "Reviewed"}</td></tr>)}</tbody></table></div>
                <div className="mt-4 flex items-center justify-between gap-3"><span className="text-sm text-muted-foreground">Page {page} · {rows.total} rows</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1 || loading} onClick={() => setPage(p => p - 1)}>Previous</Button><Button variant="outline" disabled={page * rows.page_size >= rows.total || loading} onClick={() => setPage(p => p + 1)}>Next</Button></div></div>
            </CardContent></Card> : null}
        </>}
    </div>;
}
