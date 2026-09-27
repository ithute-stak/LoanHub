"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Calculator, CheckCircle2, RefreshCcw, ShieldCheck } from "lucide-react";

import {
  approveCreditLossProvisionRun,
  createCreditLossProvisionRun,
  getCreditLossProvisionOverview,
  getCreditLossProvisionRun,
  type CreditLossProvisionLine,
  type CreditLossProvisionOverview,
  type CreditLossProvisionRun,
} from "@/api/creditLossProvisioning";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatMoney, titleCase } from "@/lib/format";

function today() { return new Date().toISOString().slice(0, 10); }
function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Provisioning action failed.";
}

export default function CreditLossProvisioningPage() {
  const [overview, setOverview] = useState<CreditLossProvisionOverview | null>(null);
  const [selected, setSelected] = useState<CreditLossProvisionRun | null>(null);
  const [asOfDate, setAsOfDate] = useState(today());
  const [overlay, setOverlay] = useState("0");
  const [overlayReason, setOverlayReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCreditLossProvisionOverview();
      setOverview(data);
      if (data.latest) setSelected(await getCreditLossProvisionRun(data.latest.id));
    } catch (nextError) { setError(errorText(nextError)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const writeOffCandidates = useMemo(() => selected?.lines?.filter((row) => row.write_off_candidate) ?? [], [selected]);

  async function generate() {
    setBusy("generate"); setError(null);
    try {
      const run = await createCreditLossProvisionRun({
        as_of_date: asOfDate,
        management_overlay: Number(overlay || 0),
        overlay_reason: Number(overlay || 0) !== 0 ? overlayReason : null,
      });
      setSelected(run);
      setOverview(await getCreditLossProvisionOverview());
    } catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  async function approve() {
    if (!selected) return;
    setBusy("approve"); setError(null);
    try {
      setSelected(await approveCreditLossProvisionRun(selected.id));
      setOverview(await getCreditLossProvisionOverview());
    } catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  async function openRun(id: string) {
    setBusy(id); setError(null);
    try { setSelected(await getCreditLossProvisionRun(id)); }
    catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  return (
    <div className="space-y-6 pb-12">
      <section className="rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground"><Calculator className="h-4 w-4 text-primary" /> Credit Loss Provisioning</div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Loan-loss allowance & impairment control</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">Convert stored portfolio-risk evidence into a controlled, reviewable provision estimate. Draft runs are evidence-backed, maker-checker approved, locked after approval, and the approved movement posts into the company accounting ledger.</p>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      <Card className="border-amber-500/30 bg-amber-500/5">
        <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-5 w-5 text-amber-600" /> Accounting-policy guardrail</CardTitle><CardDescription>This workspace provides a configurable operational impairment estimate. It does not claim statutory IFRS 9 compliance without the lender&apos;s approved accounting policy, model governance and external accounting review.</CardDescription></CardHeader>
      </Card>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Card><CardHeader className="pb-2"><CardDescription>Gross exposure</CardDescription><CardTitle className="text-lg">{formatMoney(overview?.latest?.gross_exposure ?? 0)}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Required allowance</CardDescription><CardTitle className="text-lg">{formatMoney(overview?.latest?.required_allowance ?? 0)}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Movement</CardDescription><CardTitle className="text-lg">{formatMoney(overview?.latest?.allowance_movement ?? 0)}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Stage 2</CardDescription><CardTitle className="text-lg">{formatMoney(overview?.latest?.stage_2_allowance ?? 0)}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Stage 3</CardDescription><CardTitle className="text-lg">{formatMoney(overview?.latest?.stage_3_allowance ?? 0)}</CardTitle></CardHeader></Card>
      </section>

      <Card>
        <CardHeader><CardTitle>Generate provision run</CardTitle><CardDescription>The selected date must already have a stored Portfolio Risk snapshot. Management overlays require an explicit reason.</CardDescription></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <div><label className="mb-1 block text-xs font-bold">As-of date</label><Input type="date" value={asOfDate} onChange={(event) => setAsOfDate(event.target.value)} /></div>
          <div><label className="mb-1 block text-xs font-bold">Management overlay</label><Input type="number" step="0.01" value={overlay} onChange={(event) => setOverlay(event.target.value)} /></div>
          <div className="md:col-span-2"><label className="mb-1 block text-xs font-bold">Overlay reason</label><Input value={overlayReason} onChange={(event) => setOverlayReason(event.target.value)} placeholder="Required when overlay is not zero" /></div>
          <div className="md:col-span-4 flex justify-end"><Button onClick={() => void generate()} disabled={busy === "generate"}><Calculator className="mr-2 h-4 w-4" /> {busy === "generate" ? "Calculating..." : "Generate draft"}</Button></div>
        </CardContent>
      </Card>

      {selected ? <>
        <Card>
          <CardHeader className="gap-4 md:flex-row md:items-start md:justify-between">
            <div><div className="flex items-center gap-2"><CardTitle>{selected.run_reference}</CardTitle><Badge variant={selected.status === "posted" ? "secondary" : "outline"}>{titleCase(selected.status)}</Badge></div><CardDescription className="mt-1">As at {selected.as_of_date} · {selected.loan_count} loans · allowance {formatMoney(selected.required_allowance)}</CardDescription></div>
            {selected.status === "draft" ? <Button onClick={() => void approve()} disabled={busy === "approve"}><CheckCircle2 className="mr-2 h-4 w-4" /> Approve & post movement</Button> : null}
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><div className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">Prior allowance</p><p className="mt-1 font-black">{formatMoney(selected.prior_allowance)}</p></div><div className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">Stage 1</p><p className="mt-1 font-black">{formatMoney(selected.stage_1_allowance)}</p></div><div className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">Stage 2</p><p className="mt-1 font-black">{formatMoney(selected.stage_2_allowance)}</p></div><div className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">Stage 3</p><p className="mt-1 font-black">{formatMoney(selected.stage_3_allowance)}</p></div></div>
          </CardContent>
        </Card>

        {writeOffCandidates.length ? <Card className="border-destructive/30"><CardHeader><CardTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-destructive" /> Write-off review candidates</CardTitle><CardDescription>{writeOffCandidates.length} loan(s) crossed the configured DPD review threshold. This is a review queue only; no loan is automatically written off.</CardDescription></CardHeader></Card> : null}

        <Card><CardHeader><CardTitle>Loan-level allowance register</CardTitle><CardDescription>Every amount is traceable to the stored portfolio snapshot, folio, DPD bucket and policy rate.</CardDescription></CardHeader><CardContent><div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Folio</TableHead><TableHead>Stage</TableHead><TableHead>DPD</TableHead><TableHead>Exposure</TableHead><TableHead>Rate</TableHead><TableHead>Allowance</TableHead><TableHead>Evidence</TableHead></TableRow></TableHeader><TableBody>{(selected.lines ?? []).map((row: CreditLossProvisionLine) => <TableRow key={row.id}><TableCell className="font-mono font-black text-primary">{row.folio_number}</TableCell><TableCell><Badge variant={row.stage === 3 ? "destructive" : row.stage === 2 ? "outline" : "secondary"}>Stage {row.stage}</Badge></TableCell><TableCell>{row.days_past_due}</TableCell><TableCell>{formatMoney(row.exposure)}</TableCell><TableCell>{(row.provision_rate * 100).toFixed(2)}%</TableCell><TableCell className="font-bold">{formatMoney(row.required_allowance)}</TableCell><TableCell className="max-w-[360px] text-xs text-muted-foreground">{row.rationale.join(" · ")}</TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card>
      </> : null}

      <Card><CardHeader><CardTitle>Provision history</CardTitle></CardHeader><CardContent className="space-y-2">{(overview?.history ?? []).map((run) => <button key={run.id} type="button" onClick={() => void openRun(run.id)} className="flex w-full items-center justify-between rounded-2xl border p-4 text-left hover:bg-muted/40"><span><span className="font-black">{run.as_of_date}</span><span className="ml-2 text-xs text-muted-foreground">{run.run_reference}</span></span><span className="text-right"><span className="block font-bold">{formatMoney(run.required_allowance)}</span><span className="text-xs text-muted-foreground">{titleCase(run.status)}</span></span></button>)}</CardContent></Card>
    </div>
  );
}
