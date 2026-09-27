"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, Download, Loader2, RefreshCcw, Scale, Upload } from "lucide-react";

import {
  closeReconciliationBatch,
  downloadReconciliationCsv,
  getReconciliationBatch,
  manuallyMatchLine,
  reconcileBatch,
  resolveReconciliationLine,
  uploadReconciliationCsv,
  type ReconciliationBatch,
  type ReconciliationLine,
} from "@/api/reconciliation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Reconciliation action failed.";
}

function variant(status: string) {
  if (["matched", "reconciled", "closed", "ignored", "duplicate"].includes(status)) return "secondary" as const;
  if (["shortage", "excess", "missing_source", "unmatched", "adjustment_required", "exception"].includes(status)) return "destructive" as const;
  return "outline" as const;
}

export default function ReconciliationBatchPage() {
  const params = useParams<{ batchId: string }>();
  const [batch, setBatch] = useState<ReconciliationBatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selected, setSelected] = useState<ReconciliationLine | null>(null);
  const [paymentId, setPaymentId] = useState("");
  const [evidenceNote, setEvidenceNote] = useState("");
  const [closeNote, setCloseNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setBatch(await getReconciliationBatch(params.batchId)); }
    catch (nextError) { setError(errorText(nextError)); }
    finally { setLoading(false); }
  }, [params.batchId]);

  useEffect(() => { void load(); }, [load]);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !batch) return;
    setBusy("import"); setError(null); setNotice(null);
    try {
      setBatch(await uploadReconciliationCsv(batch.id, file));
      setNotice("Source imported. Exact evidence matches were applied; ambiguous rows remain exceptions.");
    } catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  async function runReconciliation() {
    if (!batch) return;
    setBusy("reconcile"); setError(null); setNotice(null);
    try {
      const result = await reconcileBatch(batch.id);
      setBatch(result);
      setNotice(result.exception_line_count ? `Reconciliation completed with ${result.exception_line_count} unresolved exception(s).` : "Reconciliation balanced with no unresolved exceptions.");
    } catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  async function saveManualMatch() {
    if (!batch || !selected || !paymentId || !evidenceNote) return;
    setBusy("match"); setError(null);
    try {
      await manuallyMatchLine(batch.id, selected.id, paymentId, evidenceNote);
      setSelected(null); setPaymentId(""); setEvidenceNote("");
      await load();
      setNotice("Manual match recorded with evidence and actor audit trail.");
    } catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  async function ignoreLine(line: ReconciliationLine) {
    if (!batch) return;
    const note = window.prompt("Evidence note explaining why this row should be ignored:");
    if (!note) return;
    setBusy(`resolve:${line.id}`); setError(null);
    try { await resolveReconciliationLine(batch.id, line.id, "ignored", note); await load(); }
    catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  async function close() {
    if (!batch || !closeNote.trim()) return;
    setBusy("close"); setError(null);
    try {
      setBatch(await closeReconciliationBatch(batch.id, closeNote));
      setNotice("Batch closed. Its reconciliation evidence is now immutable.");
    } catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  if (loading && !batch) return <div className="flex min-h-[45vh] items-center justify-center"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="outline"><Link href="/company/reconciliation"><ArrowLeft className="mr-2 h-4 w-4" /> Reconciliation centre</Link></Button>
        <Button variant="ghost" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
      </div>
      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}
      {notice ? <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm font-bold"><CheckCircle2 className="mr-2 inline h-4 w-4 text-emerald-600" />{notice}</div> : null}

      {batch ? <>
        <section className="rounded-3xl border bg-card p-5 shadow-sm md:p-8">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div><div className="flex gap-2"><Badge variant={variant(batch.status)}>{titleCase(batch.status)}</Badge><span className="font-mono text-xs font-black text-primary">{batch.batch_reference}</span></div><h1 className="mt-3 text-3xl font-black">{titleCase(batch.source_type)} reconciliation</h1><p className="mt-2 text-sm text-muted-foreground">{formatDate(batch.period_start)} – {formatDate(batch.period_end)} · exact reference/folio evidence only; LoanHub does not fuzzy-match borrower names.</p></div>
            <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void downloadReconciliationCsv(batch)}><Download className="mr-2 h-4 w-4" /> Export evidence</Button><label className="inline-flex cursor-pointer items-center rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground"><Upload className="mr-2 h-4 w-4" /> {busy === "import" ? "Importing..." : "Import CSV"}<input type="file" accept=".csv,text/csv" className="hidden" disabled={busy !== null || batch.status === "closed" || batch.imported_line_count > 0} onChange={(event) => void importFile(event)} /></label><Button onClick={() => void runReconciliation()} disabled={busy !== null || batch.status === "closed" || !batch.imported_at}><Scale className="mr-2 h-4 w-4" /> Reconcile</Button></div>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Card><CardHeader className="pb-2"><CardDescription>Imported</CardDescription><CardTitle className="text-lg">{formatMoney(batch.imported_amount)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Matched</CardDescription><CardTitle className="text-lg">{formatMoney(batch.matched_amount)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Shortage</CardDescription><CardTitle className="text-lg">{formatMoney(batch.shortage_amount)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Excess</CardDescription><CardTitle className="text-lg">{formatMoney(batch.excess_amount)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Unmatched</CardDescription><CardTitle className="text-lg">{formatMoney(batch.unmatched_amount)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Exceptions</CardDescription><CardTitle>{batch.exception_line_count}</CardTitle></CardHeader></Card>
        </section>

        <Card><CardHeader><CardTitle>Evidence lines</CardTitle><CardDescription>Rows with no safe unique match remain visible. Manual matching requires the exact LoanHub payment ID and a written evidence note.</CardDescription></CardHeader><CardContent><div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Reference</TableHead><TableHead>Amount</TableHead><TableHead>Loan / folio</TableHead><TableHead>Match</TableHead><TableHead>Variance</TableHead><TableHead>Exception</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>
          {(batch.lines ?? []).map((line) => <TableRow key={line.id}><TableCell>{formatDate(line.transaction_date)}</TableCell><TableCell><p className="max-w-[250px] font-medium">{line.reference || "—"}</p><p className="max-w-[280px] truncate text-xs text-muted-foreground">{line.description}</p></TableCell><TableCell>{formatMoney(line.amount)}</TableCell><TableCell><p className="font-mono text-xs font-black text-primary">{line.folio_number || "—"}</p><p className="text-[11px] text-muted-foreground">{line.matched_payment_id || "No payment"}</p></TableCell><TableCell><Badge variant={variant(line.status)}>{titleCase(line.status)}</Badge><p className="mt-1 text-[11px] text-muted-foreground">{line.match_method || "No safe match"}</p></TableCell><TableCell className={line.variance_amount < 0 ? "font-bold text-destructive" : line.variance_amount > 0 ? "font-bold text-amber-600" : ""}>{formatMoney(line.variance_amount)}</TableCell><TableCell className="max-w-[260px] text-xs text-muted-foreground">{line.exception_reason || line.resolution_note || "—"}</TableCell><TableCell className="text-right"><div className="flex justify-end gap-1">{line.source_kind === "external" && !["matched", "ignored", "duplicate"].includes(line.status) ? <Button size="sm" variant="outline" onClick={() => { setSelected(line); setPaymentId(line.matched_payment_id ?? ""); setEvidenceNote(""); }}>Match</Button> : null}{["unmatched", "duplicate"].includes(line.status) ? <Button size="sm" variant="ghost" onClick={() => void ignoreLine(line)} disabled={busy === `resolve:${line.id}`}>Ignore</Button> : null}</div></TableCell></TableRow>)}
          {!batch.lines?.length ? <TableRow><TableCell colSpan={8} className="h-24 text-center text-muted-foreground">Import a CSV source to begin.</TableCell></TableRow> : null}
        </TableBody></Table></div></CardContent></Card>

        {selected ? <Card className="border-primary/30"><CardHeader><CardTitle>Evidence-based manual match</CardTitle><CardDescription>Use only when you can identify the exact LoanHub payment. This records the actor and note; it does not silently alter the payment.</CardDescription></CardHeader><CardContent className="space-y-3"><div className="grid gap-3 md:grid-cols-2"><div><label className="mb-1 block text-xs font-bold">Payment ID</label><Input value={paymentId} onChange={(event) => setPaymentId(event.target.value)} placeholder="Exact LoanHub payment UUID" /></div><div><label className="mb-1 block text-xs font-bold">Evidence note</label><Input value={evidenceNote} onChange={(event) => setEvidenceNote(event.target.value)} placeholder="Statement/reference evidence supporting this match" /></div></div><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setSelected(null)}>Cancel</Button><Button onClick={() => void saveManualMatch()} disabled={busy === "match" || !paymentId || !evidenceNote}>Record match</Button></div></CardContent></Card> : null}

        {batch.status !== "closed" ? <Card><CardHeader><CardTitle>Controlled close-off</CardTitle><CardDescription>Close-off is blocked while unresolved unmatched, shortage, excess, missing-source or adjustment-required exceptions remain.</CardDescription></CardHeader><CardContent className="flex flex-col gap-3 md:flex-row"><Input value={closeNote} onChange={(event) => setCloseNote(event.target.value)} placeholder="Reconciliation close-off note" /><Button onClick={() => void close()} disabled={busy === "close" || !closeNote.trim() || batch.exception_line_count > 0}>Close batch</Button></CardContent></Card> : null}
      </> : null}
    </div>
  );
}
