"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  BadgeCheck,
  ClipboardList,
  FileSignature,
  Gauge,
  PlugZap,
  RefreshCcw,
  Settings2,
  ShieldCheck,
  UserRoundSearch,
} from "lucide-react";

import { originationApi, toOriginationPolicyUpdate } from "@/api/origination";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { useTenant } from "@/provider/tenantProvider";
import type { IntegrationConfiguration, OriginationApplication, OriginationPolicy, OriginationPolicyUpdate } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const providerNames: Record<string, string> = {
  experian: "Experian bureau",
  manual_bureau: "Manual bureau review",
  mpesa: "M-Pesa",
  debicheck: "DebiCheck",
  sms: "SMS",
  email: "Email",
};

export default function OriginationDashboardPage() {
  const { activeRole } = useTenant();
  const isCompanyOwner = activeRole === "company_owner";
  const [applications, setApplications] = useState<OriginationApplication[]>([]);
  const [policy, setPolicy] = useState<OriginationPolicy | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationConfiguration[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [policyOpen, setPolicyOpen] = useState(false);
  const [integrationOpen, setIntegrationOpen] = useState(false);
  const [policyForm, setPolicyForm] = useState<OriginationPolicyUpdate | null>(null);
  const [integrationProvider, setIntegrationProvider] = useState("manual_bureau");
  const [integrationEnabled, setIntegrationEnabled] = useState(false);
  const [integrationEnvironment, setIntegrationEnvironment] = useState("manual");
  const [integrationCredentials, setIntegrationCredentials] = useState("");
  const [exceptionApplication, setExceptionApplication] = useState<OriginationApplication | null>(null);
  const [exceptionReason, setExceptionReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [applicationRows, policyRow, integrationRows] = await Promise.all([
        originationApi.listApplications(),
        originationApi.getPolicy(),
        originationApi.listIntegrations(),
      ]);
      setApplications(applicationRows);
      setPolicy(policyRow);
      setPolicyForm(toOriginationPolicyUpdate(policyRow));
      setIntegrations(integrationRows);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Credit origination could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const metrics = useMemo(() => ({
    drafts: applications.filter((item) => item.status === "draft").length,
    review: applications.filter((item) => ["submitted", "under_review"].includes(item.status)).length,
    eligible: applications.filter((item) => ["eligible", "conditionally_eligible"].includes(item.affordability_decision ?? "")).length,
    contracts: applications.filter((item) => item.contract_status === "signed").length,
  }), [applications]);

  async function savePolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!policyForm) return;
    setSaving(true);
    try {
      const updated = await originationApi.updatePolicy(policyForm);
      setPolicy(updated);
      setPolicyForm(toOriginationPolicyUpdate(updated));
      setPolicyOpen(false);
      toast.success("Affordability policy updated", { description: `Version ${updated.version} is now active.` });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The affordability policy could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  async function saveIntegration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      const updated = await originationApi.updateIntegration(integrationProvider, {
        environment: integrationEnvironment,
        is_enabled: integrationEnabled,
        configuration: {},
        credentials: integrationCredentials.trim() || null,
      });
      setIntegrations((current) => [...current.filter((item) => item.provider !== updated.provider), updated]);
      setIntegrationCredentials("");
      setIntegrationOpen(false);
      toast.success(`${providerNames[updated.provider] ?? titleCase(updated.provider)} configuration saved`);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The integration configuration could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  async function approveTopUpException(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!exceptionApplication || exceptionReason.trim().length < 10) return;
    setSaving(true);
    try {
      const updated = await originationApi.approveTopUpException(exceptionApplication.id, exceptionReason.trim());
      setApplications((current) => current.map((item) => item.id === updated.id ? updated : item));
      setExceptionApplication(null);
      setExceptionReason("");
      toast.success("Top-up exception approved by the company owner");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The top-up exception could not be approved."));
    } finally { setSaving(false); }
  }

  if (loading) return <PageLoader rows={8} />;

  return (
    <main className="loanhub-page space-y-6">
      <section className="loanhub-hero overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Enterprise credit origination</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">KYC, affordability and contract control</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
              Capture the complete applicant profile, prevent duplicate active lending, calculate affordability from verified income and obligations, agree the instalment date, and issue a signed loan contract before cash disbursement.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh</Button>
            <Button variant="outline" onClick={() => setPolicyOpen(true)}><Settings2 className="h-4 w-4" />Affordability policy</Button>
            <Button variant="outline" onClick={() => setIntegrationOpen(true)}><PlugZap className="h-4 w-4" />Integrations</Button>
            <Button asChild><Link href="/company/clients"><UserRoundSearch className="h-4 w-4" />Select borrower</Link></Button>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={ClipboardList} label="Draft applications" value={metrics.drafts} hint="Origination forms still being completed" />
        <Metric icon={ShieldCheck} label="Decision queue" value={metrics.review} hint="Submitted or under manager review" />
        <Metric icon={Gauge} label="Positive assessments" value={metrics.eligible} hint="Eligible or conditionally eligible" />
        <Metric icon={FileSignature} label="Signed contracts" value={metrics.contracts} hint="Ready for controlled cash disbursement" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <Card className="overflow-hidden rounded-3xl border-border/70">
          <CardHeader className="border-b bg-muted/20">
            <CardTitle>Origination applications</CardTitle>
            <CardDescription>Open any application to continue its step form or inspect its decision status.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader><TableRow><TableHead>Application</TableHead><TableHead>Applicant</TableHead><TableHead>KYC</TableHead><TableHead>Affordability</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader>
              <TableBody>
                {applications.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="h-40 text-center text-muted-foreground">No credit-origination applications have been created.</TableCell></TableRow>
                ) : applications.map((application) => (
                  <TableRow key={application.id}>
                    <TableCell><div className="flex flex-wrap items-center gap-2"><p className="font-mono text-xs font-black">{application.application_reference}</p>{application.application_type === "top_up" ? <Badge variant="outline">Top-up</Badge> : null}</div><p className="text-xs text-muted-foreground">{formatMoney(application.requested_amount)} · {application.term_count} months</p>{application.application_type === "top_up" ? <p className="text-xs text-muted-foreground">Cash to borrower {formatMoney(application.top_up_cash_to_borrower ?? application.top_up_cash_requested ?? 0)}</p> : null}</TableCell>
                    <TableCell><p className="font-bold">{application.borrower_name}</p><p className="text-xs text-muted-foreground">Created {formatDate(application.created_at)}</p></TableCell>
                    <TableCell><StatusBadge value={application.kyc_status ?? "not started"} /></TableCell>
                    <TableCell><StatusBadge value={application.affordability_decision ?? "pending"} /></TableCell>
                    <TableCell><StatusBadge value={application.status} /></TableCell>
                    <TableCell className="text-right"><div className="flex flex-wrap justify-end gap-2">{isCompanyOwner && application.application_type === "top_up" && application.top_up_exception_requested && !application.top_up_exception_approved ? <Button size="sm" variant="secondary" onClick={() => { setExceptionApplication(application); setExceptionReason(application.top_up_exception_reason ?? ""); }}>Approve exception</Button> : null}<Button size="sm" asChild><Link href={`/company/origination/new?application=${application.id}`}>Open step form</Link></Button></div></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card className="rounded-3xl border-primary/20 bg-gradient-to-br from-primary/10 via-card to-emerald-500/10">
            <CardHeader><CardTitle className="flex items-center gap-2"><BadgeCheck className="h-5 w-5 text-primary" />Current policy</CardTitle><CardDescription>These rules are snapshotted into every affordability assessment.</CardDescription></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <Line label="Policy version" value={String(policy?.version ?? 1)} />
              <Line label="Maximum DTI" value={`${Number(policy?.max_dti_percent ?? 0)}%`} />
              <Line label="Instalment-to-income" value={`${Number(policy?.max_installment_income_percent ?? 0)}%`} />
              <Line label="Disposable income usage" value={`${Number(policy?.disposable_income_usage_percent ?? 0)}%`} />
              <Line label="One active loan" value={policy?.allow_concurrent_active_loans ? "No" : "Yes"} />
              <Line label="Top-up normal threshold" value={`${Number(policy?.top_up_min_paid_percent ?? 75)}% paid`} />
              <Line label="Owner exception" value={policy?.top_up_owner_exception_enabled ? "Enabled" : "Disabled"} />
              <Line label="Signed contract required" value={policy?.require_signed_contract ? "Yes" : "No"} />
            </CardContent>
          </Card>

          <Card className="rounded-3xl">
            <CardHeader><CardTitle>Provider readiness</CardTitle><CardDescription>Optional adapters remain disabled until approved credentials are configured.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              {Object.keys(providerNames).map((provider) => {
                const row = integrations.find((item) => item.provider === provider);
                return <div key={provider} className="flex items-center justify-between rounded-2xl border p-3"><span className="text-sm font-bold">{providerNames[provider]}</span><Badge variant={row?.is_enabled ? "default" : "secondary"}>{row?.is_enabled ? "Enabled" : "Disabled"}</Badge></div>;
              })}
            </CardContent>
          </Card>
        </div>
      </div>

      <CustomDialog open={policyOpen} onOpenChange={setPolicyOpen} title="Affordability and duplicate-loan policy" description="Company management controls the rules. Every assessment preserves the policy version used at calculation time." contentClassName="sm:max-w-5xl">
        {policyForm ? (
          <form onSubmit={savePolicy} className="space-y-6 p-6 sm:p-8">
            <Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Safe default</AlertTitle><AlertDescription>Concurrent active loans are blocked unless management explicitly changes the policy.</AlertDescription></Alert>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              <NumberField label="Minimum age" value={policyForm.min_age} onChange={(value) => setPolicyForm({ ...policyForm, min_age: value })} />
              <NumberField label="Maximum age" value={policyForm.max_age} onChange={(value) => setPolicyForm({ ...policyForm, max_age: value })} />
              <NumberField label="Minimum verified income" value={policyForm.min_verified_net_income} onChange={(value) => setPolicyForm({ ...policyForm, min_verified_net_income: value })} />
              <NumberField label="Maximum DTI (%)" value={policyForm.max_dti_percent} step="0.001" onChange={(value) => setPolicyForm({ ...policyForm, max_dti_percent: value })} />
              <NumberField label="Max instalment/income (%)" value={policyForm.max_installment_income_percent} step="0.001" onChange={(value) => setPolicyForm({ ...policyForm, max_installment_income_percent: value })} />
              <NumberField label="Disposable income usage (%)" value={policyForm.disposable_income_usage_percent} step="0.001" onChange={(value) => setPolicyForm({ ...policyForm, disposable_income_usage_percent: value })} />
              <NumberField label="Living-cost buffer" value={policyForm.living_expense_buffer} onChange={(value) => setPolicyForm({ ...policyForm, living_expense_buffer: value })} />
              <NumberField label="Allowance per dependant" value={policyForm.dependant_allowance} onChange={(value) => setPolicyForm({ ...policyForm, dependant_allowance: value })} />
              <NumberField label="Minimum disposable after instalment" value={policyForm.min_disposable_after_installment} onChange={(value) => setPolicyForm({ ...policyForm, min_disposable_after_installment: value })} />
              <NumberField label="Required payslips" value={policyForm.required_payslips} step="1" onChange={(value) => setPolicyForm({ ...policyForm, required_payslips: value })} />
              <NumberField label="Bank statement months" value={policyForm.required_bank_statement_months} step="1" onChange={(value) => setPolicyForm({ ...policyForm, required_bank_statement_months: value })} />
              <NumberField label="Maximum open applications" value={policyForm.max_open_applications} step="1" onChange={(value) => setPolicyForm({ ...policyForm, max_open_applications: value })} />
              <NumberField label="Top-up minimum paid (%)" value={policyForm.top_up_min_paid_percent} step="0.001" onChange={(value) => setPolicyForm({ ...policyForm, top_up_min_paid_percent: value })} />
              <NumberField label="Top-up minimum paid instalments" value={policyForm.top_up_min_paid_installments} step="1" onChange={(value) => setPolicyForm({ ...policyForm, top_up_min_paid_installments: value })} />
            </div>
            <div className="grid gap-3 rounded-3xl border bg-muted/20 p-5 sm:grid-cols-2">
              <Check label="Require verified KYC" checked={policyForm.require_kyc_verified} onChange={(checked) => setPolicyForm({ ...policyForm, require_kyc_verified: checked })} />
              <Check label="Require signed contract before disbursement" checked={policyForm.require_signed_contract} onChange={(checked) => setPolicyForm({ ...policyForm, require_signed_contract: checked })} />
              <Check label="Permit manager affordability override" checked={policyForm.manager_override_enabled} onChange={(checked) => setPolicyForm({ ...policyForm, manager_override_enabled: checked })} />
              <Check label="Allow blacklisted applicants" checked={policyForm.allow_blacklisted} onChange={(checked) => setPolicyForm({ ...policyForm, allow_blacklisted: checked })} />
              <Check label="Allow concurrent active loans" checked={policyForm.allow_concurrent_active_loans} onChange={(checked) => setPolicyForm({ ...policyForm, allow_concurrent_active_loans: checked })} />
              <Check label="Allow top-ups" checked={policyForm.allow_top_up} onChange={(checked) => setPolicyForm({ ...policyForm, allow_top_up: checked })} />
              <Check label="Allow owner top-up exceptions" checked={policyForm.top_up_owner_exception_enabled} onChange={(checked) => setPolicyForm({ ...policyForm, top_up_owner_exception_enabled: checked })} />
              <Check label="Require positive payment history" checked={policyForm.top_up_require_positive_history} onChange={(checked) => setPolicyForm({ ...policyForm, top_up_require_positive_history: checked })} />
              <Check label="Settle old balance from new facility" checked={policyForm.top_up_settle_existing_balance} onChange={(checked) => setPolicyForm({ ...policyForm, top_up_settle_existing_balance: checked })} />
            </div>
            <DialogFooter><Button type="button" variant="outline" onClick={() => setPolicyOpen(false)}>Cancel</Button><LoadingButton type="submit" loading={saving} loadingText="Saving policy…">Save policy</LoadingButton></DialogFooter>
          </form>
        ) : null}
      </CustomDialog>

      <CustomDialog open={Boolean(exceptionApplication)} onOpenChange={(open) => !open && !saving && setExceptionApplication(null)} title="Approve exceptional top-up" description={exceptionApplication ? `${exceptionApplication.application_reference} · ${exceptionApplication.borrower_name}` : undefined}>
        <form onSubmit={approveTopUpException} className="space-y-5 p-6 sm:p-8">
          <Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Owner accountability</AlertTitle><AlertDescription>This borrower has not met the normal top-up threshold. Your decision, reason, user ID and time are permanently recorded.</AlertDescription></Alert>
          <div className="grid gap-4 sm:grid-cols-2"><Line label="Total replacement facility" value={formatMoney(exceptionApplication?.requested_amount ?? 0)} /><Line label="Additional cash" value={formatMoney(exceptionApplication?.top_up_cash_requested ?? 0)} /></div>
          <div className="space-y-2"><Label>Owner decision reason</Label><Textarea required minLength={10} value={exceptionReason} onChange={(event) => setExceptionReason(event.target.value)} /></div>
          <DialogFooter><Button type="button" variant="outline" onClick={() => setExceptionApplication(null)}>Cancel</Button><LoadingButton type="submit" loading={saving}>Approve exception</LoadingButton></DialogFooter>
        </form>
      </CustomDialog>

      <CustomDialog open={integrationOpen} onOpenChange={setIntegrationOpen} title="Optional enterprise integrations" description="The core LoanHub workflow remains usable in cash/manual mode. Do not enable a provider before commercial approval and UAT.">
        <form onSubmit={saveIntegration} className="space-y-6 p-6 sm:p-8">
          <Tabs value={integrationProvider} onValueChange={setIntegrationProvider}>
            <TabsList className="grid h-auto grid-cols-2 gap-2 bg-muted/50 p-2 sm:grid-cols-3">
              {Object.entries(providerNames).map(([value, label]) => <TabsTrigger key={value} value={value}>{label}</TabsTrigger>)}
            </TabsList>
            {Object.keys(providerNames).map((provider) => <TabsContent key={provider} value={provider} className="mt-5 rounded-3xl border p-5"><p className="font-black">{providerNames[provider]}</p><p className="mt-2 text-sm text-muted-foreground">Credentials are encrypted. Live request logic remains disabled until the approved provider adapter and contract are available.</p></TabsContent>)}
          </Tabs>
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2"><Label>Environment</Label><Select value={integrationEnvironment} onValueChange={setIntegrationEnvironment}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="manual">Manual</SelectItem><SelectItem value="sandbox">Sandbox</SelectItem><SelectItem value="production">Production</SelectItem></SelectContent></Select></div>
            <div className="space-y-2"><Label>New credential or API configuration secret</Label><Input type="password" value={integrationCredentials} onChange={(event) => setIntegrationCredentials(event.target.value)} placeholder="Leave blank to preserve existing secret" /></div>
          </div>
          <Check label="Enable this provider" checked={integrationEnabled} onChange={setIntegrationEnabled} />
          <DialogFooter><Button type="button" variant="outline" onClick={() => setIntegrationOpen(false)}>Cancel</Button><LoadingButton type="submit" loading={saving} loadingText="Saving integration…">Save integration</LoadingButton></DialogFooter>
        </form>
      </CustomDialog>
    </main>
  );
}

function Metric({ icon: Icon, label, value, hint }: { icon: typeof ClipboardList; label: string; value: number; hint: string }) {
  return <Card className="rounded-3xl border-border/70 bg-gradient-to-br from-card to-primary/5"><CardContent className="flex items-start gap-4 p-5"><div className="rounded-2xl bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5" /></div><div><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-black">{value}</p><p className="mt-1 text-xs text-muted-foreground">{hint}</p></div></CardContent></Card>;
}

function StatusBadge({ value }: { value: string }) {
  const good = ["verified", "eligible", "conditionally_eligible", "signed", "approved"].includes(value);
  const bad = ["failed", "not_affordable", "rejected"].includes(value);
  return <Badge variant={bad ? "destructive" : good ? "default" : "secondary"}>{titleCase(value)}</Badge>;
}

function Line({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-4 border-b pb-2 last:border-0"><span className="text-muted-foreground">{label}</span><strong>{value}</strong></div>;
}

function NumberField({ label, value, onChange, step = "0.01" }: { label: string; value: number; onChange: (value: number) => void; step?: string }) {
  return <div className="space-y-2"><Label>{label}</Label><Input type="number" min={0} step={step} value={value} onChange={(event) => onChange(Number(event.target.value || 0))} /></div>;
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return <label className="flex cursor-pointer items-center gap-3 rounded-2xl border bg-card p-4 text-sm font-bold"><Checkbox checked={checked} onCheckedChange={(value) => onChange(value === true)} />{label}</label>;
}
