"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  RefreshCcw,
  Save,
  Upload,
  UserCog,
} from "lucide-react";

import {
  downloadPayrollCycleCsv,
  downloadPayrollCyclePdf,
  getPayrollCycle,
  reconcilePayrollCycle,
  updatePayrollEmployee,
  uploadPayrollCsv,
  type PayrollCycle,
  type PayrollDeduction,
} from "@/api/employerPayroll";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "The payroll cycle action failed.";
}

function statusVariant(status: string) {
  if (status === "matched" || status === "reconciled") return "secondary" as const;
  if (["shortage", "rejected", "missing", "terminated", "unmatched", "exception"].includes(status)) return "destructive" as const;
  return "outline" as const;
}

export default function EmployerPayrollCyclePage() {
  const params = useParams<{ cycleId: string }>();
  const [cycle, setCycle] = useState<PayrollCycle | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selected, setSelected] = useState<PayrollDeduction | null>(null);
  const [employeeForm, setEmployeeForm] = useState({ employee_number: "", employment_state: "active", termination_date: "", termination_reason: "" });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCycle(await getPayrollCycle(params.cycleId));
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, [params.cycleId]);

  useEffect(() => { void load(); }, [load]);

  const totals = useMemo(() => ({
    lines: cycle?.deductions?.length ?? 0,
    matched: cycle?.deductions?.filter((row) => row.status === "matched").length ?? 0,
    exceptions: cycle?.deductions?.filter((row) => ["shortage", "excess", "rejected", "missing", "terminated", "unmatched"].includes(row.status)).length ?? 0,
  }), [cycle]);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !cycle) return;
    setBusy("import");
    setError(null);
    setNotice(null);
    try {
      const result = await uploadPayrollCsv(cycle.id, file);
      setCycle(result.cycle);
      setNotice(`Payroll import matched ${result.import.matched_rows} row(s), with ${result.import.unmatched_rows} unmatched and ${result.import.duplicate_match_rows} duplicate-match row(s).`);
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  async function reconcile() {
    if (!cycle) return;
    setBusy("reconcile");
    setError(null);
    setNotice(null);
    try {
      const result = await reconcilePayrollCycle(cycle.id);
      setCycle(result);
      setNotice(result.exception_line_count ? `Reconciliation completed with ${result.exception_line_count} exception(s) requiring attention.` : "Reconciliation completed with no exceptions.");
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  function editEmployee(row: PayrollDeduction) {
    setSelected(row);
    setEmployeeForm({
      employee_number: row.employee_number ?? "",
      employment_state: row.status === "terminated" ? "terminated" : "active",
      termination_date: "",
      termination_reason: row.rejection_reason ?? "",
    });
  }

  async function saveEmployee() {
    if (!cycle || !selected?.borrower_id) return;
    setBusy("employee");
    setError(null);
    try {
      await updatePayrollEmployee(cycle.account_id, selected.borrower_id, {
        employee_number: employeeForm.employee_number || null,
        employment_state: employeeForm.employment_state,
        termination_date: employeeForm.termination_date || null,
        termination_reason: employeeForm.termination_reason || null,
      });
      setSelected(null);
      await load();
      setNotice("Payroll identity updated. Future generated cycles will use the employee number and employment state.");
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  if (loading && !cycle) {
    return <div className="flex min-h-[45vh] items-center justify-center"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>;
  }

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="outline"><Link href="/company/employer-payroll"><ArrowLeft className="mr-2 h-4 w-4" /> Employer payroll centre</Link></Button>
        <Button variant="ghost" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
      </div>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}
      {notice ? <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm font-bold"><CheckCircle2 className="mr-2 inline h-4 w-4 text-emerald-600" />{notice}</div> : null}

      {cycle ? (
        <>
          <section className="overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2"><Badge variant={statusVariant(cycle.status)}>{titleCase(cycle.status)}</Badge><span className="font-mono text-xs font-black text-primary">{cycle.group_code}</span></div>
                <h1 className="mt-3 text-3xl font-black tracking-tight">Payroll reconciliation · {cycle.period_key}</h1>
                <p className="mt-2 text-sm text-muted-foreground">Scheduled pay date {formatDate(cycle.scheduled_pay_date)} · {cycle.group_name}. Permanent folio numbers are the primary matching key.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => void downloadPayrollCycleCsv(cycle)}><FileSpreadsheet className="mr-2 h-4 w-4" /> Export CSV</Button>
                <Button variant="outline" onClick={() => void downloadPayrollCyclePdf(cycle)}><FileText className="mr-2 h-4 w-4" /> PDF report</Button>
                <label className="inline-flex cursor-pointer items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90">
                  <Upload className="mr-2 h-4 w-4" /> {busy === "import" ? "Importing..." : "Import employer CSV"}
                  <input type="file" accept=".csv,text/csv" className="hidden" disabled={busy !== null || cycle.status === "reconciled"} onChange={(event) => void importFile(event)} />
                </label>
                <Button onClick={() => void reconcile()} disabled={busy !== null || cycle.status === "reconciled"}>{busy === "reconcile" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />} Reconcile</Button>
              </div>
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <Card><CardHeader className="pb-2"><CardDescription>Expected</CardDescription><CardTitle className="text-lg">{formatMoney(cycle.expected_amount)}</CardTitle></CardHeader></Card>
            <Card><CardHeader className="pb-2"><CardDescription>Received</CardDescription><CardTitle className="text-lg">{formatMoney(cycle.actual_amount)}</CardTitle></CardHeader></Card>
            <Card><CardHeader className="pb-2"><CardDescription>Shortage</CardDescription><CardTitle className="text-lg">{formatMoney(cycle.shortage_amount)}</CardTitle></CardHeader></Card>
            <Card><CardHeader className="pb-2"><CardDescription>Excess</CardDescription><CardTitle className="text-lg">{formatMoney(cycle.excess_amount)}</CardTitle></CardHeader></Card>
            <Card><CardHeader className="pb-2"><CardDescription>Rejected exposure</CardDescription><CardTitle className="text-lg">{formatMoney(cycle.rejected_amount)}</CardTitle></CardHeader></Card>
            <Card><CardHeader className="pb-2"><CardDescription>Lines</CardDescription><CardTitle>{totals.lines} <span className="text-sm font-normal text-muted-foreground">· {totals.matched} matched · {totals.exceptions} exceptions</span></CardTitle></CardHeader></Card>
          </section>

          <Card>
            <CardHeader><CardTitle>Deduction register</CardTitle><CardDescription>Import format: folio_number (preferred) or employee_number, actual_amount, optional status/reason/reference. Ambiguous rows are never guessed; they remain unmatched exceptions.</CardDescription></CardHeader>
            <CardContent>
              <div className="overflow-x-auto rounded-2xl border">
                <Table>
                  <TableHeader><TableRow><TableHead>Folio</TableHead><TableHead>Borrower</TableHead><TableHead>Employee no.</TableHead><TableHead>Expected</TableHead><TableHead>Actual</TableHead><TableHead>Variance</TableHead><TableHead>Result</TableHead><TableHead>Reason / reference</TableHead><TableHead className="text-right">Payroll identity</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {(cycle.deductions ?? []).map((row) => (
                      <TableRow key={row.id}>
                        <TableCell><p className="font-mono font-black text-primary">{row.folio_number || "UNMATCHED"}</p><p className="text-[11px] text-muted-foreground">{row.loan_reference || "No LoanHub loan match"}</p></TableCell>
                        <TableCell className="font-bold">{row.borrower_name}</TableCell>
                        <TableCell className="font-mono">{row.employee_number || <span className="text-muted-foreground">Not recorded</span>}</TableCell>
                        <TableCell>{formatMoney(row.expected_amount)}</TableCell><TableCell>{formatMoney(row.actual_amount)}</TableCell><TableCell className={row.variance_amount < 0 ? "font-bold text-destructive" : row.variance_amount > 0 ? "font-bold text-amber-600" : ""}>{formatMoney(row.variance_amount)}</TableCell>
                        <TableCell><Badge variant={statusVariant(row.status)}>{titleCase(row.status)}</Badge></TableCell>
                        <TableCell className="max-w-[280px] text-xs text-muted-foreground">{row.rejection_reason || row.employer_reference || "—"}</TableCell>
                        <TableCell className="text-right">{row.borrower_id ? <Button size="sm" variant="ghost" onClick={() => editEmployee(row)}><UserCog className="mr-2 h-4 w-4" /> Edit</Button> : "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {selected ? (
            <Card className="border-primary/30">
              <CardHeader><CardTitle>Payroll identity · {selected.borrower_name}</CardTitle><CardDescription>Keep the employee number and employment state current. Terminated or departed employees remain visible as collection-risk exceptions while loans are outstanding.</CardDescription></CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <div><label className="mb-1 block text-xs font-bold">Employee number</label><Input value={employeeForm.employee_number} onChange={(event) => setEmployeeForm((value) => ({ ...value, employee_number: event.target.value }))} /></div>
                  <div><label className="mb-1 block text-xs font-bold">Employment state</label><Select value={employeeForm.employment_state} onValueChange={(value) => setEmployeeForm((current) => ({ ...current, employment_state: value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="active">Active</SelectItem><SelectItem value="suspended">Suspended</SelectItem><SelectItem value="terminated">Terminated</SelectItem><SelectItem value="left_employer">Left employer</SelectItem></SelectContent></Select></div>
                  <div><label className="mb-1 block text-xs font-bold">Termination / exit date</label><Input type="date" value={employeeForm.termination_date} onChange={(event) => setEmployeeForm((value) => ({ ...value, termination_date: event.target.value }))} /></div>
                  <div><label className="mb-1 block text-xs font-bold">Reason</label><Input value={employeeForm.termination_reason} onChange={(event) => setEmployeeForm((value) => ({ ...value, termination_reason: event.target.value }))} /></div>
                </div>
                <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setSelected(null)}>Cancel</Button><Button onClick={() => void saveEmployee()} disabled={busy === "employee"}><Save className="mr-2 h-4 w-4" /> Save identity</Button></div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader><CardTitle>Audit rule</CardTitle><CardDescription>Once a cycle reaches reconciled status it is locked against CSV replacement. Corrections must be handled as a new correction period/record rather than silently rewriting historical payroll evidence.</CardDescription></CardHeader>
            <CardContent className="text-sm text-muted-foreground"><Download className="mr-2 inline h-4 w-4" />Keep the CSV/PDF reconciliation exports with employer remittance evidence where required by your operating process.</CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
