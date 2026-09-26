"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Gavel,
  RefreshCcw,
  Route,
  ShieldAlert,
  Sparkles,
  TimerReset,
  UserCheck,
} from "lucide-react";

import {
  completeCollectionWorkItem,
  getCollectionAutomationDashboard,
  getCollectionLegalReadiness,
  runCollectionAutomation,
  type CollectionAutomationDashboard,
  type CollectionWorkItem,
} from "@/api/collectionAutomation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string | { message?: string } } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail?.message) return detail.message;
  }
  return error instanceof Error ? error.message : "The collections automation action failed.";
}

function priorityVariant(priority: string) {
  if (priority === "urgent") return "destructive" as const;
  if (priority === "high") return "outline" as const;
  return "secondary" as const;
}

export default function CollectionAutomationPage() {
  const [data, setData] = useState<CollectionAutomationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getCollectionAutomationDashboard());
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function runEngine() {
    setBusy("run");
    setError(null);
    setNotice(null);
    try {
      const result = await runCollectionAutomation();
      setNotice(`Recovery engine checked ${result.cases_checked} case(s), created ${result.work_items_created} work item(s), detected ${result.broken_promises_detected} broken promise(s), and found ${result.legal_ready_cases} legal-ready case(s).`);
      await load();
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  async function complete(item: CollectionWorkItem) {
    setBusy(item.id);
    setError(null);
    try {
      await completeCollectionWorkItem(item.id, "Completed from Collections Automation command centre");
      await load();
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  async function inspectLegal(item: CollectionWorkItem) {
    setBusy(`legal:${item.id}`);
    setError(null);
    setNotice(null);
    try {
      const readiness = await getCollectionLegalReadiness(item.case_id);
      setNotice(
        readiness.ready
          ? `${item.case_reference ?? "Case"} is ready for legal handover.`
          : `${item.case_reference ?? "Case"} is not legal-ready yet. Missing: ${(readiness.missing ?? []).join(", ")}.`,
      );
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  const paths = useMemo(() => Object.entries(data?.recovery_paths ?? {}).sort((a, b) => b[1] - a[1]), [data]);

  return (
    <div className="space-y-6 pb-12">
      <section className="overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground">
              <Sparkles className="h-4 w-4 text-primary" /> Automated Collections & Recovery Engine
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Prioritise the right recovery action</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">
              Convert arrears into an actionable collector queue using DPD treatment bands, broken-promise detection, employer/CDAS recovery routing, legal-readiness controls and collector productivity evidence.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
            <Button onClick={() => void runEngine()} disabled={busy === "run"}><Sparkles className="mr-2 h-4 w-4" /> {busy === "run" ? "Running..." : "Run recovery engine"}</Button>
          </div>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}
      {notice ? <div className="rounded-2xl border border-primary/25 bg-primary/5 p-4 text-sm font-bold">{notice}</div> : null}

      {data ? (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Card><CardHeader className="pb-2"><CardDescription>Open work items</CardDescription><CardTitle>{data.summary.open_work_items}</CardTitle></CardHeader></Card>
          <Card className={data.summary.urgent_work_items ? "border-destructive/30" : ""}><CardHeader className="pb-2"><CardDescription>Urgent</CardDescription><CardTitle className="flex items-center gap-2">{data.summary.urgent_work_items ? <AlertTriangle className="h-5 w-5 text-destructive" /> : <CheckCircle2 className="h-5 w-5 text-emerald-600" />}{data.summary.urgent_work_items}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Past due work</CardDescription><CardTitle>{data.summary.overdue_work_items}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Broken promises</CardDescription><CardTitle>{data.summary.broken_promises}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Legal-ready cases</CardDescription><CardTitle>{data.summary.legal_ready_cases}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Total overdue exposure</CardDescription><CardTitle className="text-lg">{formatMoney(data.summary.total_overdue)}</CardTitle></CardHeader></Card>
        </section>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><TimerReset className="h-5 w-5 text-primary" /> Prioritised collector queue</CardTitle><CardDescription>Highest-risk cases are first. Broken promises and recovery-path exceptions are automatically lifted in priority.</CardDescription></CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-2xl border">
              <Table>
                <TableHeader><TableRow><TableHead>Priority</TableHead><TableHead>Case / folio</TableHead><TableHead>Treatment</TableHead><TableHead>Recovery path</TableHead><TableHead>Exposure</TableHead><TableHead>Due</TableHead><TableHead>Assigned</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                <TableBody>
                  {(data?.queue ?? []).map((item) => {
                    const snapshot = item.context_snapshot as { overdue_amount?: string; days_past_due?: number };
                    return (
                      <TableRow key={item.id}>
                        <TableCell><Badge variant={priorityVariant(item.priority)}>{titleCase(item.priority)}</Badge><p className="mt-1 text-[11px] text-muted-foreground">Score {item.priority_score.toFixed(1)}</p></TableCell>
                        <TableCell><p className="font-black">{item.case_reference ?? "Case"}</p><p className="font-mono text-xs text-primary">{item.folio_number ?? item.loan_reference ?? "—"}</p></TableCell>
                        <TableCell><p className="font-bold">{titleCase(item.action_type)}</p><p className="text-xs text-muted-foreground">{item.treatment_code}</p></TableCell>
                        <TableCell><Badge variant="outline"><Route className="mr-1 h-3 w-3" />{titleCase(item.recovery_path)}</Badge></TableCell>
                        <TableCell><p className="font-bold">{formatMoney(Number(snapshot.overdue_amount ?? 0))}</p><p className="text-xs text-muted-foreground">{snapshot.days_past_due ?? 0} DPD</p></TableCell>
                        <TableCell>{formatDate(item.due_at)}</TableCell>
                        <TableCell className="text-xs">{item.assigned_to ?? "Unassigned"}</TableCell>
                        <TableCell className="text-right"><div className="flex justify-end gap-2"><Button size="sm" variant="outline" onClick={() => void inspectLegal(item)} disabled={busy === `legal:${item.id}`}><Gavel className="mr-1 h-3.5 w-3.5" /> Legal check</Button><Button size="sm" onClick={() => void complete(item)} disabled={busy === item.id}><CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Complete</Button></div></TableCell>
                      </TableRow>
                    );
                  })}
                  {!loading && !data?.queue.length ? <TableRow><TableCell colSpan={8} className="h-28 text-center text-muted-foreground">No open automated recovery work items. Run the recovery engine to refresh the queue.</TableCell></TableRow> : null}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Route className="h-5 w-5 text-primary" /> Recovery paths</CardTitle><CardDescription>How open work is currently routed.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              {paths.map(([path, count]) => <div key={path} className="flex items-center justify-between rounded-xl border p-3"><span className="text-sm font-bold">{titleCase(path)}</span><Badge variant="outline">{count}</Badge></div>)}
              {!paths.length ? <p className="text-sm text-muted-foreground">No active recovery paths yet.</p> : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><ShieldAlert className="h-5 w-5 text-primary" /> Legal readiness</CardTitle><CardDescription>Escalation checks identity/address verification, default notice, recovery contact, material delinquency and outstanding balance before legal handover.</CardDescription></CardHeader>
          </Card>
        </div>
      </section>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><UserCheck className="h-5 w-5 text-primary" /> Collector productivity</CardTitle><CardDescription>Operational activity and recorded recoveries by collector. This is evidence for workload management, not an automatic employment-performance verdict.</CardDescription></CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Collector</TableHead><TableHead>Actions</TableHead><TableHead>Promises captured</TableHead><TableHead>Recorded recoveries</TableHead></TableRow></TableHeader><TableBody>
            {(data?.productivity ?? []).map((row) => <TableRow key={row.user_id ?? row.name}><TableCell className="font-bold">{row.name}</TableCell><TableCell>{row.actions}</TableCell><TableCell>{row.promises}</TableCell><TableCell className="font-bold">{formatMoney(row.recovered)}</TableCell></TableRow>)}
            {!data?.productivity.length ? <TableRow><TableCell colSpan={4} className="h-24 text-center text-muted-foreground">No collector activity has been recorded yet.</TableCell></TableRow> : null}
          </TableBody></Table></div>
        </CardContent>
      </Card>
    </div>
  );
}
