"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, FileCheck2, Plus, RefreshCcw, Scale, WalletCards } from "lucide-react";

import {
  createReconciliationBatch,
  getReconciliationDashboard,
  type ReconciliationDashboard,
} from "@/api/reconciliation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";

function monthStart() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Reconciliation action failed.";
}

export default function ReconciliationPage() {
  const [data, setData] = useState<ReconciliationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    source_type: "bank_statement",
    source_reference: "",
    account_reference: "",
    period_start: monthStart(),
    period_end: today(),
    currency: "LSL",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getReconciliationDashboard());
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function createBatch() {
    setBusy(true);
    setError(null);
    try {
      const batch = await createReconciliationBatch(form);
      window.location.assign(`/company/reconciliation/batches/${batch.id}`);
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(false);
    }
  }

  const summary = data?.summary;

  return (
    <div className="space-y-6 pb-12">
      <section className="rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground">
              <Scale className="h-4 w-4 text-primary" /> Proper Reconciliation Engine
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Reconcile money before closing the books</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">
              Match bank, payment-provider, employer-payroll and CDAS remittance evidence against LoanHub payments. Exact evidence is matched automatically; ambiguous, short, excess, duplicate and missing-source items stay visible until a staff member resolves them.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
            <Button onClick={() => setShowCreate((value) => !value)}><Plus className="mr-2 h-4 w-4" /> New batch</Button>
          </div>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      {summary ? (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Card><CardHeader className="pb-2"><CardDescription>Open batches</CardDescription><CardTitle>{summary.open_batches}</CardTitle></CardHeader></Card>
          <Card className={summary.exception_batches ? "border-amber-500/40" : "border-emerald-500/30"}><CardHeader className="pb-2"><CardDescription>Exception batches</CardDescription><CardTitle>{summary.exception_batches}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Unresolved exceptions</CardDescription><CardTitle>{summary.unresolved_exceptions}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Shortages</CardDescription><CardTitle className="text-lg">{formatMoney(summary.shortage_amount)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Excess</CardDescription><CardTitle className="text-lg">{formatMoney(summary.excess_amount)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Unmatched</CardDescription><CardTitle className="text-lg">{formatMoney(summary.unmatched_amount)}</CardTitle></CardHeader></Card>
        </section>
      ) : null}

      {showCreate ? (
        <Card className="border-primary/30">
          <CardHeader><CardTitle>Open reconciliation batch</CardTitle><CardDescription>Create the evidence period first, then upload the source CSV. Closed batches are immutable.</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <div><label className="mb-1 block text-xs font-bold">Source</label><Select value={form.source_type} onValueChange={(value) => setForm((current) => ({ ...current, source_type: value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="bank_statement">Bank statement</SelectItem><SelectItem value="payment_provider">Payment provider</SelectItem><SelectItem value="employer_payroll">Employer payroll</SelectItem><SelectItem value="cdas_remittance">CDAS remittance</SelectItem><SelectItem value="manual_import">Manual import</SelectItem></SelectContent></Select></div>
              <div><label className="mb-1 block text-xs font-bold">Source reference</label><Input value={form.source_reference} onChange={(event) => setForm((current) => ({ ...current, source_reference: event.target.value }))} placeholder="Statement / remittance reference" /></div>
              <div><label className="mb-1 block text-xs font-bold">Account reference</label><Input value={form.account_reference} onChange={(event) => setForm((current) => ({ ...current, account_reference: event.target.value }))} placeholder="Bank/provider account" /></div>
              <div><label className="mb-1 block text-xs font-bold">Period start</label><Input type="date" value={form.period_start} onChange={(event) => setForm((current) => ({ ...current, period_start: event.target.value }))} /></div>
              <div><label className="mb-1 block text-xs font-bold">Period end</label><Input type="date" value={form.period_end} onChange={(event) => setForm((current) => ({ ...current, period_end: event.target.value }))} /></div>
              <div><label className="mb-1 block text-xs font-bold">Currency</label><Input value={form.currency} maxLength={3} onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value.toUpperCase() }))} /></div>
            </div>
            <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button><Button onClick={() => void createBatch()} disabled={busy}><FileCheck2 className="mr-2 h-4 w-4" /> Create batch</Button></div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><WalletCards className="h-5 w-5 text-primary" /> Reconciliation batches</CardTitle><CardDescription>Each batch retains its imported evidence, matching methodology, exceptions, staff decisions and close-off record.</CardDescription></CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-2xl border">
            <Table>
              <TableHeader><TableRow><TableHead>Reference</TableHead><TableHead>Source</TableHead><TableHead>Period</TableHead><TableHead>Imported</TableHead><TableHead>Matched</TableHead><TableHead>Exceptions</TableHead><TableHead>Breaks</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader>
              <TableBody>
                {(data?.batches ?? []).map((batch) => (
                  <TableRow key={batch.id}>
                    <TableCell className="font-mono text-xs font-black text-primary">{batch.batch_reference}</TableCell>
                    <TableCell><p className="font-bold">{titleCase(batch.source_type)}</p><p className="text-xs text-muted-foreground">{batch.source_reference || "No source reference"}</p></TableCell>
                    <TableCell className="text-xs">{formatDate(batch.period_start)} – {formatDate(batch.period_end)}</TableCell>
                    <TableCell><p className="font-bold">{formatMoney(batch.imported_amount)}</p><p className="text-xs text-muted-foreground">{batch.imported_line_count} lines</p></TableCell>
                    <TableCell><p className="font-bold">{formatMoney(batch.matched_amount)}</p><p className="text-xs text-muted-foreground">{batch.matched_line_count} lines</p></TableCell>
                    <TableCell>{batch.exception_line_count ? <span className="inline-flex items-center gap-1 font-bold text-amber-600"><AlertTriangle className="h-4 w-4" />{batch.exception_line_count}</span> : <span className="inline-flex items-center gap-1 font-bold text-emerald-600"><CheckCircle2 className="h-4 w-4" />0</span>}</TableCell>
                    <TableCell className="text-xs"><p>Short {formatMoney(batch.shortage_amount)}</p><p>Excess {formatMoney(batch.excess_amount)}</p><p>Unmatched {formatMoney(batch.unmatched_amount)}</p></TableCell>
                    <TableCell><Badge variant={batch.status === "closed" || batch.status === "reconciled" ? "secondary" : batch.status === "exception" ? "destructive" : "outline"}>{titleCase(batch.status)}</Badge></TableCell>
                    <TableCell className="text-right"><Button asChild size="sm" variant="outline"><Link href={`/company/reconciliation/batches/${batch.id}`}>Open</Link></Button></TableCell>
                  </TableRow>
                ))}
                {!loading && !data?.batches.length ? <TableRow><TableCell colSpan={9} className="h-28 text-center text-muted-foreground">No reconciliation batches yet.</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
