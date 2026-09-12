"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { CalendarClock, CircleAlert, RefreshCcw, RotateCcw, Save, ShieldCheck, StopCircle } from "lucide-react";

import { maturityRecoveryApi, type MaturityPolicyUpdate } from "@/api/maturityRecovery";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { NativeSelect } from "@/components/ui/native-select";
import { PageLoader } from "@/components/ui/page-loader";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatMoney } from "@/lib/format";
import type { MaturityRecoveryOverview, MaturityRenewalLoanOverview } from "@/types/maturityRecovery";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

export default function MaturityRecoveryPage() {
  const [data, setData] = useState<MaturityRecoveryOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [policy, setPolicy] = useState<MaturityPolicyUpdate | null>(null);
  const [stopTarget, setStopTarget] = useState<MaturityRenewalLoanOverview | null>(null);
  const [stopReason, setStopReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await maturityRecoveryApi.overview();
      setData(next);
      setPolicy({
        enabled: next.policy.enabled,
        rollover_basis: next.policy.rollover_basis,
        reuse_original_rate: next.policy.reuse_original_rate,
        renewal_rate_percent: next.policy.renewal_rate_percent,
        reuse_original_term: next.policy.reuse_original_term,
        renewal_term_months: next.policy.renewal_term_months,
        include_processing_fee: next.policy.include_processing_fee,
        grace_days: next.policy.grace_days,
        max_cycles: next.policy.max_cycles,
        notify_borrower: next.policy.notify_borrower,
      });
    } catch (error) {
      toast.error(getErrorMessage(error, "Maturity controls could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const matured = useMemo(() => data?.loans.filter((loan) => loan.is_matured) ?? [], [data]);

  async function savePolicy() {
    if (!policy) return;
    setWorking(true);
    try {
      await maturityRecoveryApi.updatePolicy(policy);
      toast.success("Maturity renewal policy saved");
      await load();
    } catch (error) {
      toast.error(getErrorMessage(error, "The maturity policy could not be saved."));
    } finally {
      setWorking(false);
    }
  }

  async function runNow() {
    setWorking(true);
    try {
      const result = await maturityRecoveryApi.run();
      toast.success(`Maturity check complete: ${result.renewed ?? 0} renewed, ${result.collections_started ?? 0} sent to recovery.`);
      await load();
    } catch (error) {
      toast.error(getErrorMessage(error, "The maturity check could not run."));
    } finally {
      setWorking(false);
    }
  }

  async function confirmStop() {
    if (!stopTarget || stopReason.trim().length < 3) return;
    setWorking(true);
    try {
      const result = await maturityRecoveryApi.stopLoan(stopTarget.id, stopReason.trim());
      toast.success(result.message);
      setStopTarget(null);
      setStopReason("");
      await load();
    } catch (error) {
      toast.error(getErrorMessage(error, "Automatic renewal could not be stopped."));
    } finally {
      setWorking(false);
    }
  }

  async function resume(loan: MaturityRenewalLoanOverview) {
    setWorking(true);
    try {
      const result = await maturityRecoveryApi.resumeLoan(loan.id);
      toast.success(result.message);
      await load();
    } catch (error) {
      toast.error(getErrorMessage(error, "Automatic renewal could not be resumed."));
    } finally {
      setWorking(false);
    }
  }

  if (loading && !data) return <PageLoader rows={7} />;

  return (
    <main className="loanhub-page pb-24 lg:pb-0">
      <section className="loanhub-hero flex flex-col gap-5 p-5 sm:p-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">Maturity & restructuring</p>
          <h1 className="mt-2 text-2xl font-black tracking-tight sm:text-4xl">Maturity renewal control</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
            Keep the original loan as the master facility, capitalise an eligible unpaid balance into a new repayment cycle, and route the account to collections when automatic renewal is stopped.
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Button className="w-full sm:w-auto" variant="outline" onClick={() => void load()} disabled={working}><RefreshCcw className="h-4 w-4" />Refresh</Button>
          <Button className="w-full sm:w-auto" onClick={() => void runNow()} disabled={working}><CalendarClock className="h-4 w-4" />Run maturity check</Button>
        </div>
      </section>

      <Alert className="border-amber-300 bg-amber-50/60 dark:bg-amber-950/20">
        <CircleAlert className="h-4 w-4" />
        <AlertTitle>Contract and lending-rule safeguard</AlertTitle>
        <AlertDescription>
          Automatic renewal is off by default. Enable it only where the signed loan agreement and applicable lending rules permit capitalising the remaining eligible balance. Repeated processing fees are disabled by default.
        </AlertDescription>
      </Alert>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Active facilities" value={data?.summary.active_facilities ?? 0} />
        <Metric label="Matured with balance" value={data?.summary.matured_with_balance ?? 0} />
        <Metric label="Auto-renewing" value={data?.summary.auto_renewing ?? 0} />
        <Metric label="Renewal stopped" value={data?.summary.renewal_stopped ?? 0} />
      </section>

      {policy && <Card className="loanhub-panel">
        <CardHeader><CardTitle>Company renewal policy</CardTitle><CardDescription>Facility-level stop/resume controls override this company default.</CardDescription></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <label className="flex items-center justify-between gap-4 rounded-2xl border p-4 md:col-span-2 xl:col-span-3">
            <span><span className="block font-black">Automatic maturity renewal</span><span className="mt-1 block text-xs text-muted-foreground">Disabled is the safe default.</span></span>
            <Input type="checkbox" className="h-5 w-5" checked={policy.enabled} onChange={(e) => setPolicy({ ...policy, enabled: e.target.checked })} />
          </label>
          <Field label="Rollover basis"><NativeSelect value={policy.rollover_basis} onChange={(e) => setPolicy({ ...policy, rollover_basis: e.target.value })}><option value="outstanding_balance">Outstanding eligible balance</option></NativeSelect></Field>
          <Field label="Grace days"><Input type="number" min={0} max={365} value={policy.grace_days} onChange={(e) => setPolicy({ ...policy, grace_days: Number(e.target.value) })} /></Field>
          <Field label="Maximum cycles"><Input type="number" min={1} max={120} placeholder="Unlimited" value={policy.max_cycles ?? ""} onChange={(e) => setPolicy({ ...policy, max_cycles: e.target.value ? Number(e.target.value) : null })} /></Field>
          <label className="flex items-center gap-3 rounded-2xl border p-4"><Input type="checkbox" className="h-4 w-4" checked={policy.reuse_original_rate} onChange={(e) => setPolicy({ ...policy, reuse_original_rate: e.target.checked })} /><span className="text-sm font-bold">Reuse original interest rate</span></label>
          <Field label="Renewal rate %"><Input type="number" min={0} step="0.001" disabled={policy.reuse_original_rate} value={policy.renewal_rate_percent ?? ""} onChange={(e) => setPolicy({ ...policy, renewal_rate_percent: e.target.value ? Number(e.target.value) : null })} /></Field>
          <label className="flex items-center gap-3 rounded-2xl border p-4"><Input type="checkbox" className="h-4 w-4" checked={policy.reuse_original_term} onChange={(e) => setPolicy({ ...policy, reuse_original_term: e.target.checked })} /><span className="text-sm font-bold">Reuse original repayment term</span></label>
          <Field label="Renewal term (months)"><Input type="number" min={1} max={120} disabled={policy.reuse_original_term} value={policy.renewal_term_months ?? ""} onChange={(e) => setPolicy({ ...policy, renewal_term_months: e.target.value ? Number(e.target.value) : null })} /></Field>
          <label className="flex items-center gap-3 rounded-2xl border p-4"><Input type="checkbox" className="h-4 w-4" checked={policy.include_processing_fee} onChange={(e) => setPolicy({ ...policy, include_processing_fee: e.target.checked })} /><span className="text-sm font-bold">Repeat processing fee on renewal</span></label>
          <label className="flex items-center gap-3 rounded-2xl border p-4"><Input type="checkbox" className="h-4 w-4" checked={policy.notify_borrower} onChange={(e) => setPolicy({ ...policy, notify_borrower: e.target.checked })} /><span className="text-sm font-bold">Notify borrower after every renewal</span></label>
          <div className="md:col-span-2 xl:col-span-3"><LoadingButton loading={working} onClick={() => void savePolicy()}><Save className="h-4 w-4" />Save policy</LoadingButton></div>
        </CardContent>
      </Card>}

      <Card className="loanhub-panel overflow-hidden">
        <CardHeader><CardTitle>Maturity queue</CardTitle><CardDescription>{matured.length} currently matured facility{matured.length === 1 ? "" : "ies"} with an outstanding balance.</CardDescription></CardHeader>
        <CardContent className="grid gap-4 p-4 sm:p-6 lg:grid-cols-2 xl:grid-cols-3">
          {(data?.loans ?? []).map((loan) => <article key={loan.id} className="rounded-3xl border bg-card p-4 shadow-sm sm:p-5">
            <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-mono text-xs font-black text-primary">{loan.loan_reference}</p><h2 className="mt-1 truncate text-lg font-black">{loan.borrower_name}</h2></div><Badge variant={loan.effective_auto_renewal ? "default" : "secondary"}>{loan.effective_auto_renewal ? "Auto renewal" : "Recovery path"}</Badge></div>
            <div className="mt-4 grid grid-cols-2 gap-2"><Value label="Balance" value={formatMoney(loan.balance)} /><Value label="Instalment" value={formatMoney(loan.installment_amount)} /><Value label="Maturity" value={loan.maturity_date ? formatDate(loan.maturity_date) : "—"} /><Value label="Renewals" value={String(loan.renewal_cycle_count)} /></div>
            {loan.latest_cycle && <div className="mt-3 rounded-2xl bg-muted/40 p-3 text-xs text-muted-foreground">Cycle {loan.latest_cycle.cycle_number}: {formatMoney(loan.latest_cycle.opening_balance)} rolled forward · new maturity {formatDate(loan.latest_cycle.maturity_date)}</div>}
            {loan.renewal_stop_reason && <p className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-300">{loan.renewal_stop_reason}</p>}
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              {loan.effective_auto_renewal ? <Button className="w-full" variant="destructive" onClick={() => { setStopTarget(loan); setStopReason(""); }}><StopCircle className="h-4 w-4" />Stop & recover</Button> : <Button className="w-full" variant="outline" onClick={() => void resume(loan)} disabled={working}><RotateCcw className="h-4 w-4" />Resume renewal</Button>}
            </div>
          </article>)}
          {(data?.loans.length ?? 0) === 0 && <div className="col-span-full py-16 text-center text-sm text-muted-foreground"><ShieldCheck className="mx-auto mb-3 h-10 w-10" />No active unpaid loan facilities.</div>}
        </CardContent>
      </Card>

      {stopTarget && <div className="fixed inset-0 z-[100] flex items-end bg-black/50 p-0 sm:items-center sm:justify-center sm:p-6">
        <div className="w-full rounded-t-3xl border bg-background p-5 shadow-2xl sm:max-w-lg sm:rounded-3xl sm:p-6">
          <h2 className="text-xl font-black">Stop automatic renewal</h2>
          <p className="mt-2 text-sm text-muted-foreground">{stopTarget.loan_reference} · {stopTarget.borrower_name}. If it is already matured, LoanHub will open/reopen its collection case immediately.</p>
          <div className="mt-5"><Label htmlFor="stop-reason">Reason</Label><Textarea id="stop-reason" className="mt-2" rows={4} value={stopReason} onChange={(e) => setStopReason(e.target.value)} placeholder="Why is this facility moving to recovery?" /></div>
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button variant="outline" onClick={() => setStopTarget(null)} disabled={working}>Cancel</Button><LoadingButton variant="destructive" loading={working} disabled={stopReason.trim().length < 3} onClick={() => void confirmStop()}><StopCircle className="h-4 w-4" />Stop renewal</LoadingButton></div>
        </div>
      </div>}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) { return <div className="loanhub-stat"><p className="text-xs font-black uppercase tracking-[0.14em] text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-black">{value.toLocaleString()}</p></div>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <div><Label className="mb-2 block">{label}</Label>{children}</div>; }
function Value({ label, value }: { label: string; value: string }) { return <div className="rounded-2xl bg-muted/40 p-3"><p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p><p className="mt-1 text-sm font-black">{value}</p></div>; }
