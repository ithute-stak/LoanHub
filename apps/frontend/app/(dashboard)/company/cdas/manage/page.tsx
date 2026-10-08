"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, Loader2, RefreshCw, ShieldCheck, SlidersHorizontal, Sparkles, WalletCards } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";
import { getErrorMessage } from "@/utils/apiError";

type CdasOperationalLoan = {
  loan_id: string;
  loan_reference: string;
  borrower_name: string;
  loan_status: string;
  balance: string;
  installment_amount: string;
  repayment_period: number;
  employee_number: string | null;
  mandate_status: string | null;
  deduction_id: number | null;
  lifecycle_status: string;
  requires_reconciliation: boolean;
  next_action: "register" | "track" | "reconcile" | "manage" | "complete";
  autopilot_enabled: boolean;
  autopilot_pending: Record<string, unknown> | null;
  autopilot_last_result: Record<string, unknown> | null;
  autopilot_topup_opportunity: Record<string, unknown> | null;
};

type OperationsResponse = { items: CdasOperationalLoan[]; count: number };
type RosterSnapshot = {
  environment: string;
  captured_at: string;
  source_reference: string;
  snapshot_date: string;
  provider_year: number;
  provider_month: number;
  file_name: string | null;
  employee_count: number;
  total_monthly_deductions: string;
  truncated: boolean;
};
type RosterResponse = { available: boolean; snapshot: RosterSnapshot | null };
type RegistrationDraft = {
  loan_id: string;
  loan_reference: string;
  ready: boolean;
  reasons: string[];
  registration: {
    employee_no: string;
    deduction_amount: string;
    total_installment: number;
    effective_month: string;
  } | null;
};

const STATUS_LABELS: Record<string, string> = {
  not_registered: "Ready to register",
  registration_pending: "Registration pending",
  registered: "Registered",
  reviewed: "Reviewed",
  approved: "Approved",
  active: "Active",
  changed: "Changed",
  change_pending: "Change pending",
  settlement_pending: "Settlement pending",
  settled: "Settled",
  registration_failed: "Registration failed",
};

function money(value: string | number | null | undefined) {
  const amount = Number(value || 0);
  return "M " + amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function statusVariant(item: CdasOperationalLoan): "default" | "secondary" | "destructive" | "outline" {
  if (item.requires_reconciliation) return "destructive";
  if (item.lifecycle_status === "settled") return "secondary";
  if (["approved", "active", "changed"].includes(item.lifecycle_status)) return "default";
  return "outline";
}

export default function CdasManagePage() {
  const { activeRole } = useTenant();
  const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
  const [items, setItems] = useState<CdasOperationalLoan[]>([]);
  const [loading, setLoading] = useState(false);
  const [workingLoanId, setWorkingLoanId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [registrationDraft, setRegistrationDraft] = useState<RegistrationDraft | null>(null);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [roster, setRoster] = useState<RosterSnapshot | null>(null);
  const [rosterLoading, setRosterLoading] = useState(false);

  async function load() {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const [response, rosterResponse] = await Promise.all([
        api.get<OperationsResponse>("/cdas/loans/operations"),
        api.get<RosterResponse>("/cdas/roster-intelligence"),
      ]);
      setItems(response.data.items);
      setRoster(rosterResponse.data.snapshot);
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, "CDAS operations could not be loaded."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return items;
    return items.filter((item) =>
      [item.loan_reference, item.borrower_name, item.employee_number || "", item.lifecycle_status]
        .some((value) => value.toLowerCase().includes(term)),
    );
  }, [items, search]);

  const totals = useMemo(() => ({
    total: items.length,
    add: items.filter((item) => item.next_action === "register").length,
    active: items.filter((item) => ["approved", "active", "changed"].includes(item.lifecycle_status)).length,
    reconcile: items.filter((item) => item.requires_reconciliation).length,
    topups: items.filter((item) => Boolean(item.autopilot_topup_opportunity)).length,
    settled: items.filter((item) => item.lifecycle_status === "settled").length,
  }), [items]);


  async function refreshRoster() {
    if (rosterLoading) return;
    setRosterLoading(true);
    setError(null);
    try {
      await api.post("/cdas/roster-intelligence/refresh");
      const response = await api.get<RosterResponse>("/cdas/roster-intelligence");
      setRoster(response.data.snapshot);
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, "CDAS roster intelligence refresh failed."));
    } finally {
      setRosterLoading(false);
    }
  }

  async function prepareRegistration(loanId: string) {
    setWorkingLoanId(loanId);
    setError(null);
    setConsentConfirmed(false);
    try {
      const response = await api.get<RegistrationDraft>("/cdas/loans/" + loanId + "/registration-draft");
      setRegistrationDraft(response.data);
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, "CDAS registration could not be prepared."));
    } finally {
      setWorkingLoanId(null);
    }
  }

  async function registerLoan() {
    if (!registrationDraft?.ready || !consentConfirmed) return;
    setWorkingLoanId(registrationDraft.loan_id);
    setError(null);
    try {
      await api.post("/cdas/loans/" + registrationDraft.loan_id + "/register", {
        confirmed: true,
        borrower_consent: true,
      });
      setRegistrationDraft(null);
      setConsentConfirmed(false);
      await load();
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, "CDAS registration failed."));
    } finally {
      setWorkingLoanId(null);
    }
  }

  async function lifecycle(loanId: string, requestType: 3 | 4) {
    setWorkingLoanId(loanId);
    setError(null);
    try {
      await api.post("/cdas/loans/" + loanId + "/lifecycle", {
        request_type: requestType,
        confirmed: true,
      });
      await load();
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, "CDAS lifecycle action failed."));
    } finally {
      setWorkingLoanId(null);
    }
  }

  async function reconcile(loanId: string) {
    setWorkingLoanId(loanId);
    setError(null);
    try {
      await api.post("/cdas/loans/" + loanId + "/reconcile");
      await load();
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, "CDAS reconciliation failed."));
    } finally {
      setWorkingLoanId(null);
    }
  }

  if (!canManage) {
    return (
      <div className="loanhub-page">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Company management permission required</AlertTitle>
          <AlertDescription>Adding or changing CDAS deductions is restricted to company management.</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="loanhub-page space-y-6">
      <section className="rounded-3xl border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge>CDAS Operations</Badge>
              <Badge variant="outline">LoanHub-managed workflow</Badge>
            </div>
            <h1 className="text-3xl font-black tracking-tight">Payroll deduction management</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Approved loan to CDAS registration, provider tracking, reconciliation and Autopilot from one screen.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh
            </Button>
            <Button asChild variant="ghost">
              <Link href="/company/cdas/operations">
                <SlidersHorizontal className="h-4 w-4" />
                Advanced controls
              </Link>
            </Button>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Card><CardHeader className="pb-2"><CardDescription>CDAS loans</CardDescription><CardTitle>{totals.total}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Ready to add</CardDescription><CardTitle>{totals.add}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Active / approved</CardDescription><CardTitle>{totals.active}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Need reconcile</CardDescription><CardTitle>{totals.reconcile}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Top-up opportunities</CardDescription><CardTitle>{totals.topups}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Settled</CardDescription><CardTitle>{totals.settled}</CardTitle></CardHeader></Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>CDAS roster intelligence</CardTitle>
              <CardDescription>Daily employee and deduction snapshot from the provider Output File.</CardDescription>
            </div>
            <Button variant="outline" onClick={() => void refreshRoster()} disabled={rosterLoading}>
              {rosterLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh roster
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {roster ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl bg-muted/35 p-3"><p className="text-xs font-bold uppercase text-muted-foreground">Employees</p><p className="mt-1 text-2xl font-black">{roster.employee_count}</p></div>
              <div className="rounded-xl bg-muted/35 p-3"><p className="text-xs font-bold uppercase text-muted-foreground">Monthly deductions</p><p className="mt-1 text-2xl font-black">{money(roster.total_monthly_deductions)}</p></div>
              <div className="rounded-xl bg-muted/35 p-3"><p className="text-xs font-bold uppercase text-muted-foreground">Provider month</p><p className="mt-1 font-black">{String(roster.provider_month).padStart(2, "0")}/{roster.provider_year}</p></div>
              <div className="rounded-xl bg-muted/35 p-3"><p className="text-xs font-bold uppercase text-muted-foreground">Environment</p><p className="mt-1 font-black uppercase">{roster.environment}</p></div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
              No roster snapshot has been captured yet. LoanHub will attempt the daily sync after 03:45 Africa/Maseru, or you can refresh it manually.
            </div>
          )}
        </CardContent>
      </Card>

      {error ? (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>CDAS action unsuccessful</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>Deduction queue</CardTitle>
              <CardDescription>LoanHub calculates the next safe action from the current CDAS state.</CardDescription>
            </div>
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search borrower, loan, employee number or status" className="lg:max-w-sm" />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {visible.length === 0 ? (
            <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">No CDAS-enabled loans match this view.</div>
          ) : visible.map((item) => {
            const busy = workingLoanId === item.loan_id;
            return (
              <div key={item.loan_id} className="rounded-2xl border p-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-black">{item.borrower_name}</p>
                      <Badge variant={statusVariant(item)}>{STATUS_LABELS[item.lifecycle_status] || item.lifecycle_status}</Badge>
                      {item.autopilot_enabled ? <Badge variant="outline"><Sparkles className="mr-1 h-3 w-3" /> Autopilot</Badge> : null}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {item.loan_reference}
                      {item.employee_number ? " · Employee " + item.employee_number : ""}
                      {item.deduction_id ? " · Deduction #" + item.deduction_id : ""}
                    </p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-xl bg-muted/35 p-3"><p className="text-xs font-bold uppercase text-muted-foreground">Balance</p><p className="mt-1 font-black tabular-nums">{money(item.balance)}</p></div>
                      <div className="rounded-xl bg-muted/35 p-3"><p className="text-xs font-bold uppercase text-muted-foreground">Monthly deduction</p><p className="mt-1 font-black tabular-nums">{money(item.installment_amount)}</p></div>
                      <div className="rounded-xl bg-muted/35 p-3"><p className="text-xs font-bold uppercase text-muted-foreground">Term</p><p className="mt-1 font-black">{item.repayment_period} months</p></div>
                    </div>
                    {item.autopilot_topup_opportunity ? (
                      <Alert className="mt-4"><Sparkles className="h-4 w-4" /><AlertTitle>New CDAS affordability detected</AlertTitle><AlertDescription>Autopilot has recorded a possible deduction top-up.</AlertDescription></Alert>
                    ) : null}
                    {item.autopilot_pending ? (
                      <Alert className="mt-4"><Clock3 className="h-4 w-4" /><AlertTitle>Cash-payment re-optimisation pending</AlertTitle><AlertDescription>LoanHub will reconcile the deduction with the new balance.</AlertDescription></Alert>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2 xl:max-w-sm xl:justify-end">
                    {item.next_action === "register" ? <Button onClick={() => void prepareRegistration(item.loan_id)} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <WalletCards className="h-4 w-4" />}Add to CDAS</Button> : null}
                    {item.requires_reconciliation ? <Button variant="destructive" onClick={() => void reconcile(item.loan_id)} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Reconcile</Button> : null}
                    {!item.requires_reconciliation && item.lifecycle_status === "registered" ? <Button variant="outline" onClick={() => void lifecycle(item.loan_id, 3)} disabled={busy}>Review</Button> : null}
                    {!item.requires_reconciliation && item.lifecycle_status === "reviewed" ? <Button onClick={() => void lifecycle(item.loan_id, 4)} disabled={busy}><ShieldCheck className="h-4 w-4" />Approve</Button> : null}
                    {["approved", "active", "changed"].includes(item.lifecycle_status) ? <Button asChild variant="outline"><Link href={"/company/cdas/operations?loan=" + item.loan_id}>Manage<ArrowRight className="h-4 w-4" /></Link></Button> : null}
                    {item.lifecycle_status === "settled" ? <Badge variant="secondary" className="px-3 py-2"><CheckCircle2 className="mr-1 h-4 w-4" />Complete</Badge> : null}
                  </div>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {registrationDraft ? (
        <Card className={registrationDraft.ready ? "border-primary/30" : "border-destructive/30"}>
          <CardHeader>
            <CardTitle>{registrationDraft.ready ? "Review and add deduction" : "Loan is not ready for CDAS"}</CardTitle>
            <CardDescription>{registrationDraft.ready ? "LoanHub prepared the registration from the approved loan." : registrationDraft.reasons.join(" ")}</CardDescription>
          </CardHeader>
          {registrationDraft.ready && registrationDraft.registration ? (
            <CardContent className="space-y-5">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-xl bg-muted/35 p-3"><Label>Employee</Label><p className="mt-1 font-black">{registrationDraft.registration.employee_no}</p></div>
                <div className="rounded-xl bg-muted/35 p-3"><Label>Deduction</Label><p className="mt-1 font-black">{money(registrationDraft.registration.deduction_amount)}</p></div>
                <div className="rounded-xl bg-muted/35 p-3"><Label>Instalments</Label><p className="mt-1 font-black">{registrationDraft.registration.total_installment}</p></div>
                <div className="rounded-xl bg-muted/35 p-3"><Label>Effective month</Label><p className="mt-1 font-black">{registrationDraft.registration.effective_month}</p></div>
              </div>
              <label className="flex items-start gap-3 rounded-2xl border p-4 text-sm">
                <input type="checkbox" checked={consentConfirmed} onChange={(event) => setConsentConfirmed(event.target.checked)} className="mt-1" />
                <span><strong>I confirm the borrower authorised this payroll deduction.</strong><br /><span className="text-muted-foreground">LoanHub records the consent before sending the prepared registration to CDAS.</span></span>
              </label>
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => void registerLoan()} disabled={!consentConfirmed || Boolean(workingLoanId)}>{workingLoanId ? <Loader2 className="h-4 w-4 animate-spin" /> : <WalletCards className="h-4 w-4" />}Confirm and Add to CDAS</Button>
                <Button variant="outline" onClick={() => setRegistrationDraft(null)}>Cancel</Button>
              </div>
            </CardContent>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
