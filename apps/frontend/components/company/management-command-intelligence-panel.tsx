"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, Gauge, RefreshCcw, Sparkles } from "lucide-react";

import { analyticsApi, type ManagementCommandIntelligence } from "@/api/analytics";
import { listCompanyStaff } from "@/api/companyStaff";
import { createManagementAction, escalateOverdueManagementActions, listManagementActions, recordManagementDecision, resolveManagementAction, verifyManagementAction, type ManagementAction } from "@/api/companyOperatingSystem";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMoney, titleCase } from "@/lib/format";

function isoDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

function metricValue(metric?: { value: number; format: "money" | "integer" | "percent" | "decimal" }) {
  if (!metric) return "—";
  if (metric.format === "money") return formatMoney(metric.value);
  if (metric.format === "percent") return `${metric.value.toFixed(2)}%`;
  if (metric.format === "integer") return Math.round(metric.value).toLocaleString();
  return metric.value.toFixed(2);
}

function severityVariant(severity: string) {
  if (severity === "critical") return "destructive" as const;
  if (severity === "high") return "outline" as const;
  return "secondary" as const;
}

export function ManagementCommandIntelligencePanel() {
  const today = useMemo(() => new Date(), []);
  const start = useMemo(() => {
    const value = new Date(today);
    value.setDate(value.getDate() - 29);
    return value;
  }, [today]);

  const [data, setData] = useState<ManagementCommandIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actions, setActions] = useState<ManagementAction[]>([]);
  const [staff, setStaff] = useState<Array<{ user_id: string; label: string }>>([]);
  const [ownerBySignal, setOwnerBySignal] = useState<Record<string, string>>({});
  const [dueBySignal, setDueBySignal] = useState<Record<string, string>>({});
  const [noteByAction, setNoteByAction] = useState<Record<string, string>>({});
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [result, actionRows, staffRows] = await Promise.all([
        analyticsApi.command({
          date_from: isoDate(start),
          date_to: isoDate(today),
          granularity: "day",
        }),
        listManagementActions(),
        listCompanyStaff(),
      ]);
      setData(result);
      setActions(actionRows);
      setStaff(staffRows.filter((row) => row.is_active).map((row) => ({
        user_id: row.user_id,
        label: row.user.person ? [row.user.person.first_name, row.user.person.last_name].filter(Boolean).join(" ") : row.user.phone,
      })));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Management command intelligence could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [start, today]);

  useEffect(() => { void load(); }, [load]);

  async function assignPriority(item: ManagementCommandIntelligence["priority_actions"][number]) {
    const owner = ownerBySignal[item.id];
    const dueDate = dueBySignal[item.id];
    if (!owner || !dueDate) return;
    setBusyAction(item.id);
    setError(null);
    try {
      await createManagementAction({
        source_signal_id: item.id,
        source: item.source,
        domain: item.domain,
        severity: item.severity,
        title: item.title,
        why_now: item.why_now,
        recommended_action: item.recommended_action,
        action_url: item.action_url,
        evidence: item.evidence,
        assigned_user_id: owner,
        due_at: new Date(`${dueDate}T17:00:00`).toISOString(),
      });
      await load();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Could not assign management priority.");
    } finally {
      setBusyAction(null);
    }
  }

  async function addDecision(action: ManagementAction) {
    const note = noteByAction[action.id]?.trim();
    if (!note) return;
    setBusyAction(action.id);
    try {
      await recordManagementDecision(action.id, { decision: "management_review", note });
      setNoteByAction((current) => ({ ...current, [action.id]: "" }));
      await load();
    } finally {
      setBusyAction(null);
    }
  }

  async function resolveAction(action: ManagementAction) {
    const note = noteByAction[action.id]?.trim();
    if (!note) return;
    setBusyAction(action.id);
    try {
      await resolveManagementAction(action.id, { resolution: note });
      setNoteByAction((current) => ({ ...current, [action.id]: "" }));
      await load();
    } finally {
      setBusyAction(null);
    }
  }

  async function verifyAction(action: ManagementAction, outcome: "verified" | "reopened") {
    const note = noteByAction[action.id]?.trim();
    if (!note) return;
    setBusyAction(action.id);
    try {
      await verifyManagementAction(action.id, { outcome, note });
      setNoteByAction((current) => ({ ...current, [action.id]: "" }));
      await load();
    } finally {
      setBusyAction(null);
    }
  }

  async function escalateOverdue() {
    setBusyAction("escalate");
    try {
      await escalateOverdueManagementActions();
      await load();
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <section className="space-y-4">
      <Card className={data?.command_status === "critical" ? "border-destructive/50" : data?.command_status === "high" ? "border-amber-500/40" : ""}>
        <CardHeader>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs font-black text-muted-foreground"><Gauge className="h-4 w-4 text-primary" /> Management Command Intelligence</div>
              <CardTitle className="mt-3 text-2xl">What needs management attention first</CardTitle>
              <CardDescription className="mt-2 max-w-4xl">Evidence-backed priorities across lending, collections, finance, treasury, branches, audit and operations. Recommendations require human review and do not execute high-impact actions automatically.</CardDescription>
            </div>
            <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh priorities</Button>
          </div>
        </CardHeader>
        {error ? <CardContent><div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div></CardContent> : null}
        {data ? <CardContent className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Command status</p><div className="mt-2"><Badge variant={severityVariant(data.command_status)}>{titleCase(data.command_status)}</Badge></div></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Enterprise risk</p><p className="mt-2 text-2xl font-black">{data.enterprise_risk_score}/100</p><p className="text-xs text-muted-foreground">{titleCase(data.enterprise_risk_level)}</p></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Critical</p><p className="mt-2 text-2xl font-black">{data.priority_counts.critical}</p></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">High</p><p className="mt-2 text-2xl font-black">{data.priority_counts.high}</p></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Medium</p><p className="mt-2 text-2xl font-black">{data.priority_counts.medium}</p></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Open priorities</p><p className="mt-2 text-2xl font-black">{data.priority_counts.total}</p></div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {["outstanding_balance", "collections", "net_cashflow", "collection_rate"].map((key) => {
              const metric = data.executive_metrics[key];
              return <div key={key} className="rounded-2xl border bg-card p-4"><p className="text-xs font-black uppercase text-muted-foreground">{metric?.label ?? titleCase(key)}</p><p className="mt-2 text-xl font-black">{metricValue(metric)}</p>{metric?.change_percent != null ? <p className="mt-1 text-xs text-muted-foreground">{metric.change_percent >= 0 ? "+" : ""}{metric.change_percent.toFixed(1)}% vs prior period</p> : null}</div>;
            })}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3"><h3 className="text-lg font-black">Ranked management action queue</h3><span className="text-xs text-muted-foreground">Highest severity first</span></div>
            {data.priority_actions.length ? data.priority_actions.map((item) => (
              <div key={item.id} className="rounded-2xl border p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border bg-background text-sm font-black">{item.rank}</div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2"><p className="font-black">{item.title}</p><Badge variant={severityVariant(item.severity)}>{titleCase(item.severity)}</Badge><Badge variant="secondary">{titleCase(item.domain)}</Badge></div>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.why_now}</p>
                      <div className="mt-3 rounded-xl bg-muted/40 p-3"><p className="text-xs font-black uppercase tracking-wide text-muted-foreground">Recommended management action</p><p className="mt-1 text-sm">{item.recommended_action}</p></div>
                    </div>
                  </div>
                  <div className="w-full shrink-0 space-y-2 lg:w-72">
                    <Button asChild variant="outline" className="w-full"><Link href={item.action_url}>Open evidence <ArrowRight className="ml-2 h-4 w-4" /></Link></Button>
                    {actions.some((action) => action.source_signal_id === item.id && !["verified","cancelled"].includes(action.status)) ? <Badge variant="secondary">Action case already active</Badge> : <>
                      <Select value={ownerBySignal[item.id] ?? ""} onValueChange={(value) => setOwnerBySignal((current) => ({ ...current, [item.id]: value }))}><SelectTrigger><SelectValue placeholder="Assign owner" /></SelectTrigger><SelectContent>{staff.map((member) => <SelectItem key={member.user_id} value={member.user_id}>{member.label}</SelectItem>)}</SelectContent></Select>
                      <Input type="date" value={dueBySignal[item.id] ?? ""} onChange={(event) => setDueBySignal((current) => ({ ...current, [item.id]: event.target.value }))} />
                      <Button className="w-full" disabled={busyAction === item.id || !ownerBySignal[item.id] || !dueBySignal[item.id]} onClick={() => void assignPriority(item)}>Assign & track</Button>
                    </>}
                  </div>
                </div>
              </div>
            )) : <div className="rounded-2xl border bg-emerald-500/5 p-4 text-sm font-bold"><CheckCircle2 className="mr-2 inline h-4 w-4" />No management priority thresholds are currently breached.</div>}
          </div>

          {data.opportunities.length ? <div className="space-y-3">
            <h3 className="flex items-center gap-2 text-lg font-black"><Sparkles className="h-5 w-5 text-primary" />Evidence-backed opportunities</h3>
            <div className="grid gap-3 md:grid-cols-2">{data.opportunities.map((item) => <div key={item.code} className="rounded-2xl border p-4"><p className="font-black">{item.title}</p><p className="mt-2 text-sm leading-6 text-muted-foreground">{item.management_option}</p><Button asChild variant="link" className="mt-2 h-auto p-0"><Link href={item.action_url}>Review supporting area <ArrowRight className="ml-1 h-4 w-4" /></Link></Button></div>)}</div>
          </div> : null}

          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-black">Decision & accountability workflow</h3><Button variant="outline" disabled={busyAction === "escalate"} onClick={() => void escalateOverdue()}>Escalate overdue actions</Button></div>
            {actions.length ? actions.map((action) => <div key={action.id} className="rounded-2xl border p-4">
              <div className="flex flex-wrap items-center gap-2"><p className="font-black">{action.reference} · {action.title}</p><Badge variant={severityVariant(action.severity)}>{titleCase(action.severity)}</Badge><Badge variant={action.overdue ? "destructive" : "secondary"}>{action.overdue ? `${action.days_overdue}d overdue` : titleCase(action.status)}</Badge>{action.escalation_level ? <Badge variant="outline">Escalation L{action.escalation_level}</Badge> : null}</div>
              <p className="mt-2 text-sm text-muted-foreground">Owner: {staff.find((member) => member.user_id === action.assigned_user_id)?.label ?? action.assigned_user_id ?? "Unassigned"} · Due: {action.due_at ? new Date(action.due_at).toLocaleDateString() : "—"}</p>
              {action.decision_note ? <div className="mt-3 rounded-xl bg-muted/40 p-3 text-sm"><span className="font-bold">Decision:</span> {action.decision_note}</div> : null}
              {action.resolution ? <div className="mt-3 rounded-xl bg-muted/40 p-3 text-sm"><span className="font-bold">Resolution:</span> {action.resolution}</div> : null}
              {action.status !== "verified" ? <div className="mt-3 space-y-2"><Textarea placeholder={action.status === "resolved" ? "Independent verification note" : "Decision / resolution evidence note"} value={noteByAction[action.id] ?? ""} onChange={(event) => setNoteByAction((current) => ({ ...current, [action.id]: event.target.value }))} /><div className="flex flex-wrap gap-2">{!["resolved","verified"].includes(action.status) ? <Button variant="outline" disabled={busyAction === action.id} onClick={() => void addDecision(action)}>Record decision</Button> : null}{!["resolved","verified"].includes(action.status) ? <Button disabled={busyAction === action.id} onClick={() => void resolveAction(action)}>Resolve</Button> : null}{action.status === "resolved" ? <><Button disabled={busyAction === action.id} onClick={() => void verifyAction(action, "verified")}>Verify independently</Button><Button variant="outline" disabled={busyAction === action.id} onClick={() => void verifyAction(action, "reopened")}>Reopen</Button></> : null}</div></div> : <div className="mt-3 rounded-xl border bg-emerald-500/5 p-3 text-sm font-bold">Independently verified</div>}
            </div>) : <div className="rounded-2xl border p-4 text-sm text-muted-foreground">No management action cases have been created yet.</div>}
          </div>

          <div className="rounded-2xl border bg-muted/30 p-4 text-sm text-muted-foreground"><AlertTriangle className="mr-2 inline h-4 w-4" />{data.policy_note}</div>
        </CardContent> : null}
      </Card>
    </section>
  );
}
