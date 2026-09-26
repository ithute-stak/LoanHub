"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Building2,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  RefreshCcw,
  Save,
  ShieldAlert,
  UsersRound,
  WalletCards,
} from "lucide-react";

import {
  configurePayrollAccount,
  generatePayrollCycle,
  getEmployerPayrollOverview,
  getPayrollCycles,
  getPayrollEmployees,
  getPayrollExceptions,
  type EmployerPayrollGroup,
  type EmployerPayrollOverview,
  type PayrollCycle,
  type PayrollDeduction,
  type PayrollEmployee,
} from "@/api/employerPayroll";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";

function currentPeriod() {
  const value = new Date();
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}`;
}

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Employer payroll data could not be loaded.";
}

function cycleTone(status: string) {
  if (status === "reconciled") return "secondary" as const;
  if (status === "exception") return "destructive" as const;
  return "outline" as const;
}

export default function EmployerPayrollPage() {
  const [overview, setOverview] = useState<EmployerPayrollOverview | null>(null);
  const [cycles, setCycles] = useState<PayrollCycle[]>([]);
  const [exceptions, setExceptions] = useState<PayrollDeduction[]>([]);
  const [employees, setEmployees] = useState<PayrollEmployee[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [periodKey, setPeriodKey] = useState(currentPeriod());
  const [editing, setEditing] = useState<EmployerPayrollGroup | null>(null);
  const [form, setForm] = useState({
    payroll_reference: "",
    payroll_day: "",
    collection_channel: "employer_payroll",
    reconciliation_tolerance: "0.00",
    payroll_contact_name: "",
    payroll_contact_email: "",
    payroll_contact_phone: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextOverview, nextCycles, nextExceptions, nextEmployees] = await Promise.all([
        getEmployerPayrollOverview(),
        getPayrollCycles(),
        getPayrollExceptions(),
        getPayrollEmployees(),
      ]);
      setOverview(nextOverview);
      setCycles(nextCycles);
      setExceptions(nextExceptions);
      setEmployees(nextEmployees);
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const employmentExceptions = useMemo(
    () => employees.filter((row) => ["terminated", "left_employer", "suspended"].includes(row.employment_state)),
    [employees],
  );

  function editGroup(group: EmployerPayrollGroup) {
    const account = group.account;
    setEditing(group);
    setForm({
      payroll_reference: account?.payroll_reference ?? "",
      payroll_day: account?.payroll_day ? String(account.payroll_day) : "",
      collection_channel: account?.collection_channel ?? "employer_payroll",
      reconciliation_tolerance: String(account?.reconciliation_tolerance ?? 0),
      payroll_contact_name: account?.payroll_contact_name ?? "",
      payroll_contact_email: account?.payroll_contact_email ?? "",
      payroll_contact_phone: account?.payroll_contact_phone ?? "",
    });
  }

  async function saveConfiguration() {
    if (!editing) return;
    setBusy(`config:${editing.employer_group_id}`);
    setError(null);
    try {
      await configurePayrollAccount({
        employer_group_id: editing.employer_group_id,
        payroll_reference: form.payroll_reference || null,
        payroll_day: form.payroll_day ? Number(form.payroll_day) : null,
        collection_channel: form.collection_channel,
        reconciliation_tolerance: Number(form.reconciliation_tolerance || 0),
        payroll_contact_name: form.payroll_contact_name || null,
        payroll_contact_email: form.payroll_contact_email || null,
        payroll_contact_phone: form.payroll_contact_phone || null,
      });
      setEditing(null);
      await load();
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  async function generate(group: EmployerPayrollGroup) {
    if (!group.account) return;
    setBusy(`cycle:${group.account.id}`);
    setError(null);
    try {
      const cycle = await generatePayrollCycle(group.account.id, periodKey);
      await load();
      window.location.assign(`/company/employer-payroll/cycles/${cycle.id}`);
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6 pb-12">
      <section className="overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground">
              <Building2 className="h-4 w-4 text-primary" /> Employer & Payroll Management Centre
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Payroll collections under control</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">
              Manage work-group exposure, payroll schedules, expected deductions, employer returns, shortages, rejections, terminated employees and reconciliation from one ledger. Loan matching is anchored on the permanent folio number.
            </p>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            <RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      {overview ? (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
          <Card><CardHeader className="pb-2"><CardDescription>Work groups</CardDescription><CardTitle>{overview.summary.work_group_count}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Payroll borrowers</CardDescription><CardTitle>{overview.summary.borrower_count}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Active loans</CardDescription><CardTitle>{overview.summary.active_loan_count}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Outstanding exposure</CardDescription><CardTitle className="text-lg">{formatMoney(overview.summary.outstanding_exposure)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Expected / month</CardDescription><CardTitle className="text-lg">{formatMoney(overview.summary.expected_monthly_deductions)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Overdue exposure</CardDescription><CardTitle className="text-lg">{formatMoney(overview.summary.overdue_exposure)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Employment flags</CardDescription><CardTitle>{overview.summary.terminated_employee_count}</CardTitle></CardHeader></Card>
          <Card className={overview.summary.reconciliation_exception_count ? "border-amber-500/40" : "border-emerald-500/30"}><CardHeader className="pb-2"><CardDescription>Reconciliation exceptions</CardDescription><CardTitle className="flex items-center gap-2">{overview.summary.reconciliation_exception_count ? <AlertTriangle className="h-5 w-5 text-amber-500" /> : <CheckCircle2 className="h-5 w-5 text-emerald-600" />}{overview.summary.reconciliation_exception_count}</CardTitle></CardHeader></Card>
        </section>
      ) : null}

      <Card>
        <CardHeader className="gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <CardTitle>Employer / work-group ledger</CardTitle>
            <CardDescription>Exposure and expected payroll collection are calculated from the live loan book. Employer configuration never owns or changes folio sequences.</CardDescription>
          </div>
          <div className="w-full max-w-[180px]">
            <label className="mb-1 block text-xs font-black uppercase tracking-wide text-muted-foreground">Payroll period</label>
            <Input type="month" value={periodKey} onChange={(event) => setPeriodKey(event.target.value)} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-2xl border">
            <Table>
              <TableHeader><TableRow><TableHead>Work group</TableHead><TableHead>Borrowers / loans</TableHead><TableHead>Exposure</TableHead><TableHead>Expected deduction</TableHead><TableHead>CDAS</TableHead><TableHead>Employment flags</TableHead><TableHead>Latest cycle</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
              <TableBody>
                {(overview?.groups ?? []).map((group) => (
                  <TableRow key={group.employer_group_id}>
                    <TableCell><p className="font-black text-primary">{group.group_code}</p><p className="max-w-[240px] text-xs text-muted-foreground">{group.group_name}</p><p className="mt-1 text-[11px] text-muted-foreground">{group.account ? `${titleCase(group.account.collection_channel)} · payroll day ${group.account.payroll_day ?? "not set"}` : "Not configured"}</p></TableCell>
                    <TableCell><p className="font-bold">{group.borrower_count} borrowers</p><p className="text-xs text-muted-foreground">{group.active_loan_count} active/defaulted loans</p></TableCell>
                    <TableCell><p className="font-bold">{formatMoney(group.outstanding_exposure)}</p><p className="text-xs text-destructive">Overdue {formatMoney(group.overdue_exposure)}</p></TableCell>
                    <TableCell className="font-bold">{formatMoney(group.expected_monthly_deductions)}</TableCell>
                    <TableCell><p className="font-bold">{group.cdas_loan_count} loans</p><p className="text-xs text-muted-foreground">{formatMoney(group.cdas_expected_deductions)}</p></TableCell>
                    <TableCell><p className="font-bold">{group.terminated_employee_count} terminated/left</p><p className="text-xs text-muted-foreground">{group.suspended_employee_count} suspended</p></TableCell>
                    <TableCell>{group.latest_cycle ? <><Badge variant={cycleTone(group.latest_cycle.status)}>{titleCase(group.latest_cycle.status)}</Badge><p className="mt-1 text-xs text-muted-foreground">{group.latest_cycle.period_key} · {group.latest_cycle.exception_line_count} exceptions</p></> : <span className="text-xs text-muted-foreground">No cycle yet</span>}</TableCell>
                    <TableCell className="text-right"><div className="flex justify-end gap-2"><Button size="sm" variant="outline" onClick={() => editGroup(group)}>Configure</Button><Button size="sm" onClick={() => void generate(group)} disabled={!group.account || !group.account.payroll_day || busy === `cycle:${group.account?.id}`}><CalendarClock className="mr-2 h-4 w-4" /> Generate</Button></div></TableCell>
                  </TableRow>
                ))}
                {!loading && !overview?.groups.length ? <TableRow><TableCell colSpan={8} className="h-28 text-center text-muted-foreground">No employer/work-group exposure exists yet.</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {editing ? (
        <Card className="border-primary/30">
          <CardHeader><CardTitle>Configure {editing.group_code} payroll</CardTitle><CardDescription>Company-specific controls for {editing.group_name}. A payroll day is required for automatic cycle generation.</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div><label className="mb-1 block text-xs font-bold">Payroll reference</label><Input value={form.payroll_reference} onChange={(event) => setForm((value) => ({ ...value, payroll_reference: event.target.value }))} placeholder="Employer payroll code" /></div>
              <div><label className="mb-1 block text-xs font-bold">Payroll day</label><Input type="number" min={1} max={31} value={form.payroll_day} onChange={(event) => setForm((value) => ({ ...value, payroll_day: event.target.value }))} placeholder="25" /></div>
              <div><label className="mb-1 block text-xs font-bold">Collection channel</label><Select value={form.collection_channel} onValueChange={(value) => setForm((current) => ({ ...current, collection_channel: value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="employer_payroll">Employer payroll</SelectItem><SelectItem value="cdas">CDAS</SelectItem><SelectItem value="mixed">Mixed</SelectItem><SelectItem value="manual">Manual</SelectItem></SelectContent></Select></div>
              <div><label className="mb-1 block text-xs font-bold">Tolerance</label><Input type="number" min={0} step="0.01" value={form.reconciliation_tolerance} onChange={(event) => setForm((value) => ({ ...value, reconciliation_tolerance: event.target.value }))} /></div>
              <div><label className="mb-1 block text-xs font-bold">Payroll contact</label><Input value={form.payroll_contact_name} onChange={(event) => setForm((value) => ({ ...value, payroll_contact_name: event.target.value }))} /></div>
              <div><label className="mb-1 block text-xs font-bold">Contact email</label><Input type="email" value={form.payroll_contact_email} onChange={(event) => setForm((value) => ({ ...value, payroll_contact_email: event.target.value }))} /></div>
              <div><label className="mb-1 block text-xs font-bold">Contact phone</label><Input value={form.payroll_contact_phone} onChange={(event) => setForm((value) => ({ ...value, payroll_contact_phone: event.target.value }))} /></div>
            </div>
            <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button><Button onClick={() => void saveConfiguration()} disabled={busy?.startsWith("config:")}><Save className="mr-2 h-4 w-4" /> Save payroll controls</Button></div>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><WalletCards className="h-5 w-5 text-primary" /> Payroll cycles</CardTitle><CardDescription>Generate expected deductions, import the employer return, reconcile, then retain the cycle as an audit record.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {cycles.slice(0, 12).map((cycle) => (
              <div key={cycle.id} className="flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center sm:justify-between">
                <div><div className="flex items-center gap-2"><p className="font-black">{cycle.group_code} · {cycle.period_key}</p><Badge variant={cycleTone(cycle.status)}>{titleCase(cycle.status)}</Badge></div><p className="mt-1 text-xs text-muted-foreground">Expected {formatMoney(cycle.expected_amount)} · Received {formatMoney(cycle.actual_amount)} · {cycle.exception_line_count} exceptions</p></div>
                <Button asChild size="sm" variant="outline"><Link href={`/company/employer-payroll/cycles/${cycle.id}`}><ExternalLink className="mr-2 h-4 w-4" /> Open reconciliation</Link></Button>
              </div>
            ))}
            {!cycles.length ? <p className="text-sm text-muted-foreground">No payroll cycles generated yet.</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><ShieldAlert className="h-5 w-5 text-amber-500" /> Exceptions requiring attention</CardTitle><CardDescription>Shortages, missing/rejected deductions, excess payments, terminated-employment exposure and unmatched employer rows.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {exceptions.slice(0, 12).map((row) => (
              <div key={row.id} className="rounded-2xl border p-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-mono text-sm font-black text-primary">{row.folio_number || "UNMATCHED"}</p><Badge variant="destructive">{titleCase(row.status)}</Badge></div><p className="mt-1 font-bold">{row.borrower_name}</p><p className="text-xs text-muted-foreground">Expected {formatMoney(row.expected_amount)} · Actual {formatMoney(row.actual_amount)} · Variance {formatMoney(row.variance_amount)}</p>{row.rejection_reason ? <p className="mt-2 text-xs text-destructive">{row.rejection_reason}</p> : null}</div>
            ))}
            {!exceptions.length ? <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm font-bold"><CheckCircle2 className="h-5 w-5 text-emerald-600" /> No current payroll reconciliation exceptions.</div> : null}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><UsersRound className="h-5 w-5 text-primary" /> Employment-risk register</CardTitle><CardDescription>Payroll identities that are suspended, terminated or recorded as having left the employer remain visible while any lending exposure is managed.</CardDescription></CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-2xl border">
            <Table><TableHeader><TableRow><TableHead>Borrower</TableHead><TableHead>Employee no.</TableHead><TableHead>State</TableHead><TableHead>Termination date</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader><TableBody>
              {employmentExceptions.map((row) => <TableRow key={row.id}><TableCell className="font-bold">{row.borrower_name}</TableCell><TableCell className="font-mono">{row.employee_number || "—"}</TableCell><TableCell><Badge variant="destructive">{titleCase(row.employment_state)}</Badge></TableCell><TableCell>{row.termination_date ? formatDate(row.termination_date) : "—"}</TableCell><TableCell className="max-w-[360px] text-xs text-muted-foreground">{row.termination_reason || "—"}</TableCell></TableRow>)}
              {!employmentExceptions.length ? <TableRow><TableCell colSpan={5} className="h-24 text-center text-muted-foreground">No suspended or terminated payroll identities are recorded.</TableCell></TableRow> : null}
            </TableBody></Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
