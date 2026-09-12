"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { CircleAlert, Play, RefreshCcw, Save, ShieldCheck } from "lucide-react";

import { creditBureauApi } from "@/api/creditBureau";
import { originationApi } from "@/api/origination";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, LENDING_ROLES, hasRole } from "@/types/auth";
import type { CreditBureauDecisionContext, CreditBureauEnquiry, ExperianCompanyConfiguration } from "@/types/creditBureau";
import type { OriginationApplication } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const RUN_ROLES = [...LENDING_ROLES, "risk_manager", "compliance_officer"] as const;

export default function ExperianCreditBureauPage() {
  const { activeRole } = useTenant();
  const canConfigure = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
  const canRun = hasRole(activeRole, RUN_ROLES);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [configuration, setConfiguration] = useState<ExperianCompanyConfiguration | null>(null);
  const [applications, setApplications] = useState<OriginationApplication[]>([]);
  const [selectedApplicationId, setSelectedApplicationId] = useState("");
  const [enquiries, setEnquiries] = useState<CreditBureauEnquiry[]>([]);
  const [decisionContext, setDecisionContext] = useState<CreditBureauDecisionContext | null>(null);

  const [enabled, setEnabled] = useState(false);
  const [maxReportAgeHours, setMaxReportAgeHours] = useState(24);
  const [requireBeforeAffordability, setRequireBeforeAffordability] = useState(false);
  const [includeCommitments, setIncludeCommitments] = useState(false);
  const [debtMode, setDebtMode] = useState<"max" | "bureau_only" | "declared_plus_bureau">("max");
  const [declineBelowScore, setDeclineBelowScore] = useState("");
  const [referBelowScore, setReferBelowScore] = useState("");
  const [blockDefaults, setBlockDefaults] = useState(false);
  const [requireIdentityMatch, setRequireIdentityMatch] = useState(false);

  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [consentMethod, setConsentMethod] = useState<"written" | "electronic" | "recorded" | "other">("written");
  const [consentReference, setConsentReference] = useState("");

  const applyConfiguration = useCallback((row: ExperianCompanyConfiguration) => {
    setConfiguration(row);
    setEnabled(Boolean(row.is_enabled));
    setMaxReportAgeHours(Number(row.configuration.max_report_age_hours ?? 24));
    setRequireBeforeAffordability(Boolean(row.configuration.require_before_affordability));
    setIncludeCommitments(Boolean(row.configuration.include_bureau_commitments_in_affordability));
    const mode = row.configuration.bureau_debt_mode;
    setDebtMode(mode === "bureau_only" || mode === "declared_plus_bureau" ? mode : "max");
    setDeclineBelowScore(row.configuration.decline_below_score == null ? "" : String(row.configuration.decline_below_score));
    setReferBelowScore(row.configuration.refer_below_score == null ? "" : String(row.configuration.refer_below_score));
    setBlockDefaults(Boolean(row.configuration.block_defaults));
    setRequireIdentityMatch(Boolean(row.configuration.require_identity_match));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [config, apps] = await Promise.all([
        creditBureauApi.getExperianConfiguration(),
        originationApi.listApplications(),
      ]);
      applyConfiguration(config);
      setApplications(apps);
      setSelectedApplicationId((current) => current || apps[0]?.id || "");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Experian workspace could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [applyConfiguration]);

  const loadApplicationBureau = useCallback(async (applicationId: string) => {
    if (!applicationId) {
      setEnquiries([]);
      setDecisionContext(null);
      return;
    }
    try {
      const [rows, context] = await Promise.all([
        creditBureauApi.listApplicationEnquiries(applicationId),
        creditBureauApi.decisionContext(applicationId),
      ]);
      setEnquiries(rows);
      setDecisionContext(context);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Credit-bureau history could not be loaded."));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void loadApplicationBureau(selectedApplicationId); }, [loadApplicationBureau, selectedApplicationId]);

  const selectedApplication = useMemo(
    () => applications.find((item) => item.id === selectedApplicationId) ?? null,
    [applications, selectedApplicationId],
  );
  const latest = enquiries[0] ?? null;
  const platformReady = Boolean(configuration?.platform.ready_for_company_use);
  const companyReady = platformReady && enabled;

  async function saveCompanySettings() {
    if (!canConfigure) return;
    setSaving(true);
    try {
      const updated = await creditBureauApi.updateExperianConfiguration({
        is_enabled: enabled,
        configuration: {
          max_report_age_hours: Math.max(1, Number(maxReportAgeHours || 24)),
          require_before_affordability: requireBeforeAffordability,
          include_bureau_commitments_in_affordability: includeCommitments,
          bureau_debt_mode: debtMode,
          decline_below_score: declineBelowScore.trim() ? Number(declineBelowScore) : null,
          refer_below_score: referBelowScore.trim() ? Number(referBelowScore) : null,
          block_defaults: blockDefaults,
          require_identity_match: requireIdentityMatch,
        },
      });
      applyConfiguration(updated);
      toast.success("Experian company policy saved", {
        description: "Provider credentials remain controlled by the LoanHub Platform Owner.",
      });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Experian company policy could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  async function runCreditCheck() {
    if (!selectedApplicationId || !consentConfirmed || !companyReady) return;
    setRunning(true);
    try {
      const row = await creditBureauApi.runExperian(selectedApplicationId, {
        consent_confirmed: true,
        consent_method: consentMethod,
        consent_reference: consentReference.trim() || null,
        permissible_purpose: "credit_application",
      });
      toast.success("Experian credit check completed", {
        description: row.score === null ? "The bureau response was stored and normalized." : `Score ${row.score}${row.risk_band ? ` · ${row.risk_band}` : ""}`,
      });
      setConsentConfirmed(false);
      setConsentReference("");
      await loadApplicationBureau(selectedApplicationId);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Experian credit check could not be completed."));
      await loadApplicationBureau(selectedApplicationId);
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <PageLoader rows={10} />;

  return (
    <main className="loanhub-page space-y-6">
      <section className="loanhub-hero overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Credit bureau integration</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Experian</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
              Use LoanHub&apos;s centrally secured Experian connection. Your company controls participation and its credit-risk policy; the Platform Owner controls all Experian credentials and API mapping.
            </p>
          </div>
          <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh</Button>
        </div>
      </section>

      {!platformReady ? (
        <Alert variant="destructive">
          <CircleAlert className="h-4 w-4" />
          <AlertTitle>Platform Experian connection is not ready</AlertTitle>
          <AlertDescription>
            The LoanHub Platform Owner must configure credentials, product mapping, pass the OAuth test and enable Experian under Platform configuration → API &amp; integrations. Companies cannot enter or view those secrets.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Central Experian connection ready</AlertTitle>
          <AlertDescription>
            {titleCase(configuration?.platform.environment ?? "configured")} environment · OAuth {configuration?.platform.last_test_status === "connected" ? "connected" : "not tested"}. Your company can enable Experian and run consented checks.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle>Platform connection</CardTitle>
            <CardDescription>Read-only status. Credentials and product mapping belong to the Platform Owner.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <Info label="Platform status" value={configuration?.platform.is_enabled ? "Enabled" : "Disabled"} good={Boolean(configuration?.platform.is_enabled)} />
            <Info label="Environment" value={configuration?.platform.environment ? titleCase(configuration.platform.environment) : "Not configured"} good={Boolean(configuration?.platform.environment)} />
            <Info label="Credentials" value={configuration?.platform.has_credentials ? "Stored centrally" : "Not configured"} good={Boolean(configuration?.platform.has_credentials)} />
            <Info label="OAuth" value={configuration?.platform.last_test_status ? titleCase(configuration.platform.last_test_status) : "Not tested"} good={configuration?.platform.last_test_status === "connected"} />
            <Info label="Product" value={configuration?.platform.product || "Not configured"} good={Boolean(configuration?.platform.product)} />
            <Info label="Ready for use" value={platformReady ? "Ready" : "Not ready"} good={platformReady} />
          </CardContent>
        </Card>

        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle>Company Experian policy</CardTitle>
            <CardDescription>These settings apply only to your lending company and never contain Experian secrets.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <label className="flex items-start gap-3 rounded-2xl border p-4">
              <Checkbox checked={enabled} onCheckedChange={(value) => setEnabled(value === true)} disabled={!canConfigure || !platformReady} />
              <span><strong>Enable Experian for this company</strong><span className="mt-1 block text-xs text-muted-foreground">Requires the Platform Owner connection to be ready.</span></span>
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Maximum report age (hours)"><Input type="number" min={1} max={720} value={maxReportAgeHours} onChange={(event) => setMaxReportAgeHours(Number(event.target.value))} disabled={!canConfigure} /></Field>
              <Field label="Bureau debt treatment">
                <Select value={debtMode} onValueChange={(value) => setDebtMode(value as typeof debtMode)} disabled={!canConfigure}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="max">Use higher of declared/bureau</SelectItem><SelectItem value="bureau_only">Use bureau commitments</SelectItem><SelectItem value="declared_plus_bureau">Add declared + bureau</SelectItem></SelectContent>
                </Select>
              </Field>
              <Field label="Decline below score"><Input type="number" min={0} max={1000} value={declineBelowScore} onChange={(event) => setDeclineBelowScore(event.target.value)} disabled={!canConfigure} placeholder="Optional" /></Field>
              <Field label="Refer below score"><Input type="number" min={0} max={1000} value={referBelowScore} onChange={(event) => setReferBelowScore(event.target.value)} disabled={!canConfigure} placeholder="Optional" /></Field>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Toggle label="Require before affordability" checked={requireBeforeAffordability} onChange={setRequireBeforeAffordability} disabled={!canConfigure} />
              <Toggle label="Use bureau commitments in affordability" checked={includeCommitments} onChange={setIncludeCommitments} disabled={!canConfigure} />
              <Toggle label="Block applicants with defaults" checked={blockDefaults} onChange={setBlockDefaults} disabled={!canConfigure} />
              <Toggle label="Require identity match" checked={requireIdentityMatch} onChange={setRequireIdentityMatch} disabled={!canConfigure} />
            </div>

            {canConfigure ? <LoadingButton loading={saving} onClick={() => void saveCompanySettings()}><Save className="h-4 w-4" />Save company policy</LoadingButton> : null}
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle>Run Experian credit check</CardTitle>
          <CardDescription>Select an origination application and record borrower consent before a new bureau enquiry.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <Field label="Loan application">
              <Select value={selectedApplicationId} onValueChange={setSelectedApplicationId} disabled={!applications.length}>
                <SelectTrigger><SelectValue placeholder="Select application" /></SelectTrigger>
                <SelectContent>{applications.map((application) => <SelectItem key={application.id} value={application.id}>{application.application_reference} · {application.borrower_name}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <div className="rounded-2xl border bg-muted/20 p-4 text-sm">
              <p className="font-black">{selectedApplication?.borrower_name || "No application selected"}</p>
              <p className="mt-1 text-muted-foreground">{selectedApplication ? `${selectedApplication.application_reference} · ${formatMoney(selectedApplication.requested_amount)}` : "Choose an application to continue."}</p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Consent method">
              <Select value={consentMethod} onValueChange={(value) => setConsentMethod(value as typeof consentMethod)} disabled={!canRun}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="written">Written</SelectItem><SelectItem value="electronic">Electronic</SelectItem><SelectItem value="recorded">Recorded</SelectItem><SelectItem value="other">Other</SelectItem></SelectContent>
              </Select>
            </Field>
            <Field label="Consent reference"><Input value={consentReference} onChange={(event) => setConsentReference(event.target.value)} disabled={!canRun} placeholder="Form, OTP, file or audit reference" /></Field>
          </div>

          <label className="flex items-start gap-3 rounded-2xl border p-4">
            <Checkbox checked={consentConfirmed} onCheckedChange={(value) => setConsentConfirmed(value === true)} disabled={!canRun || !companyReady} />
            <span><strong>Borrower consent confirmed for this credit application</strong><span className="mt-1 block text-xs text-muted-foreground">LoanHub stores the consent method/reference with the company-scoped bureau enquiry.</span></span>
          </label>

          <LoadingButton loading={running} disabled={!canRun || !companyReady || !selectedApplicationId || !consentConfirmed} onClick={() => void runCreditCheck()}><Play className="h-4 w-4" />Run Experian credit check</LoadingButton>
        </CardContent>
      </Card>

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <InfoCard label="Latest score" value={latest?.score == null ? "—" : String(latest.score)} />
        <InfoCard label="Risk band" value={latest?.risk_band ? titleCase(latest.risk_band) : "—"} />
        <InfoCard label="Bureau commitments" value={decisionContext?.bureau_monthly_commitments == null ? "—" : formatMoney(decisionContext.bureau_monthly_commitments)} />
        <InfoCard label="Declared vs bureau variance" value={decisionContext?.variance == null ? "—" : formatMoney(decisionContext.variance)} />
      </div>

      <Card className="rounded-3xl overflow-hidden">
        <CardHeader><CardTitle>Experian enquiry history</CardTitle><CardDescription>Only enquiries bought/run by this company for the selected application are shown.</CardDescription></CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Status</TableHead><TableHead>Score</TableHead><TableHead>Risk</TableHead><TableHead>Accounts</TableHead><TableHead>Monthly debt</TableHead><TableHead>Adverse</TableHead></TableRow></TableHeader>
            <TableBody>
              {enquiries.length ? enquiries.map((row) => <TableRow key={row.id}><TableCell>{formatDate(row.requested_at)}</TableCell><TableCell><Badge variant={row.status === "succeeded" ? "default" : row.status === "failed" ? "destructive" : "secondary"}>{titleCase(row.status)}</Badge></TableCell><TableCell>{row.score ?? "—"}</TableCell><TableCell>{row.risk_band ? titleCase(row.risk_band) : "—"}</TableCell><TableCell>{row.open_accounts_count}</TableCell><TableCell>{formatMoney(row.monthly_commitments)}</TableCell><TableCell>{row.defaults_count + row.judgments_count + row.collections_count}</TableCell></TableRow>) : <TableRow><TableCell colSpan={7} className="h-28 text-center text-muted-foreground">No Experian enquiry exists for this application.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </main>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function Toggle({ label, checked, onChange, disabled }: { label: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
  return <label className="flex items-center gap-3 rounded-2xl border p-3 text-sm font-semibold"><Checkbox checked={checked} onCheckedChange={(value) => onChange(value === true)} disabled={disabled} /><span>{label}</span></label>;
}

function Info({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return <div className="rounded-2xl border p-4"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p><p className={`mt-2 text-sm font-black ${good ? "text-emerald-600" : ""}`}>{value}</p></div>;
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return <Card className="rounded-3xl"><CardContent className="p-5"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-2 text-xl font-black">{value}</p></CardContent></Card>;
}
