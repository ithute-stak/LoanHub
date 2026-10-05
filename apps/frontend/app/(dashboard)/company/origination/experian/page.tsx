"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { CircleAlert, Play, RefreshCcw, Save, ShieldCheck, WalletCards } from "lucide-react";

import { creditBureauApi } from "@/api/creditBureau";
import { originationApi } from "@/api/origination";
import { listLoanProducts } from "@/api/loanProducts";
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
import type { LoanProduct } from "@/types/loanProduct";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const RUN_ROLES = [...LENDING_ROLES, "risk_manager", "compliance_officer"] as const;

export default function ExperianCreditBureauPage() {
  const { activeRole } = useTenant();
  const canConfigure = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
  const canRun = hasRole(activeRole, RUN_ROLES);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [requestingSubscription, setRequestingSubscription] = useState(false);
  const [running, setRunning] = useState(false);
  const [configuration, setConfiguration] = useState<ExperianCompanyConfiguration | null>(null);
  const [applications, setApplications] = useState<OriginationApplication[]>([]);
  const [loanProducts, setLoanProducts] = useState<LoanProduct[]>([]);
  const [selectedApplicationId, setSelectedApplicationId] = useState("");
  const [enquiries, setEnquiries] = useState<CreditBureauEnquiry[]>([]);
  const [decisionContext, setDecisionContext] = useState<CreditBureauDecisionContext | null>(null);

  const [environment, setEnvironment] = useState<"sandbox" | "live">("sandbox");
  const [maxReportAgeHours, setMaxReportAgeHours] = useState(24);
  const [requirementMode, setRequirementMode] = useState<"optional" | "before_affordability" | "before_approval" | "amount_threshold" | "selected_products">("optional");
  const [requiredAboveAmount, setRequiredAboveAmount] = useState("");
  const [requiredProductIds, setRequiredProductIds] = useState<string[]>([]);
  const [includeCommitments, setIncludeCommitments] = useState(false);
  const [debtMode, setDebtMode] = useState<"max" | "bureau_only" | "declared_plus_bureau">("max");
  const [declineBelowScore, setDeclineBelowScore] = useState("");
  const [referBelowScore, setReferBelowScore] = useState("");
  const [blockDefaults, setBlockDefaults] = useState(false);
  const [requireIdentityMatch, setRequireIdentityMatch] = useState(false);

  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [consentMethod, setConsentMethod] = useState<"written" | "electronic" | "recorded" | "other">("written");
  const [consentReference, setConsentReference] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [address1, setAddress1] = useState("");
  const [address2, setAddress2] = useState("");
  const [enquiryPurpose, setEnquiryPurpose] = useState("12");
  const [forceRefresh, setForceRefresh] = useState(false);

  const applyConfiguration = useCallback((row: ExperianCompanyConfiguration) => {
    setConfiguration(row);
    setEnvironment(row.configuration.environment === "live" ? "live" : "sandbox");
    setMaxReportAgeHours(Number(row.configuration.max_report_age_hours ?? 24));
    const requirement = row.configuration.requirement_mode;
    setRequirementMode(requirement === "before_affordability" || requirement === "before_approval" || requirement === "amount_threshold" || requirement === "selected_products" ? requirement : row.configuration.require_before_affordability ? "before_affordability" : "optional");
    setRequiredAboveAmount(row.configuration.required_above_amount == null ? "" : String(row.configuration.required_above_amount));
    setRequiredProductIds(Array.isArray(row.configuration.required_product_ids) ? row.configuration.required_product_ids : []);
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
      const [config, apps, products] = await Promise.all([
        creditBureauApi.getExperianConfiguration(),
        originationApi.listApplications(),
        listLoanProducts(),
      ]);
      applyConfiguration(config);
      const requestedApplicationId = typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("application")
        : null;
      setApplications(apps);
      setLoanProducts(products.filter((item) => item.is_active));
      setSelectedApplicationId((current) => {
        if (current) return current;
        if (requestedApplicationId && apps.some((item) => item.id === requestedApplicationId)) {
          return requestedApplicationId;
        }
        return apps[0]?.id || "";
      });
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
  const selectedEnvironmentReady = Boolean(
    configuration?.platform.environments?.[environment]?.ready ??
    (configuration?.configuration.environment === environment && configuration?.platform.ready_for_company_use),
  );
  const platformReady = selectedEnvironmentReady;
  const subscription = configuration?.subscription;
  const subscriptionApproved = subscription?.status === "approved";
  const companyReady = selectedEnvironmentReady && subscriptionApproved;

  async function saveCompanySettings() {
    if (!canConfigure) return;
    setSaving(true);
    try {
      const updated = await creditBureauApi.updateExperianConfiguration({
        is_enabled: subscriptionApproved,
        configuration: {
          environment,
          max_report_age_hours: Math.max(1, Number(maxReportAgeHours || 24)),
          requirement_mode: requirementMode,
          required_above_amount: requirementMode === "amount_threshold" && requiredAboveAmount.trim() ? Number(requiredAboveAmount) : null,
          required_product_ids: requirementMode === "selected_products" ? requiredProductIds : [],
          require_before_affordability: requirementMode === "before_affordability",
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

  async function requestSubscription() {
    if (!canConfigure) return;
    setRequestingSubscription(true);
    try {
      await creditBureauApi.requestExperianSubscription();
      toast.success("Credit Bureau subscription requested", {
        description: "The LoanHub Platform Owner must approve your company before any paid bureau enquiry can run.",
      });
      applyConfiguration(await creditBureauApi.getExperianConfiguration());
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Credit Bureau subscription request could not be submitted."));
    } finally {
      setRequestingSubscription(false);
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
        enquiry_purpose: Number(enquiryPurpose),
        result_type: "JSON",
        postal_code: postalCode.trim(),
        address1: address1.trim() || null,
        address2: address2.trim() || null,
        cs_data: true,
        cpa_plus_nlr_data: true,
        run_compuscore: true,
        force_refresh: forceRefresh,
      });
      toast.success("Experian credit check completed", {
        description: row.score === null ? "The bureau response was stored and normalized." : `Score ${row.score}${row.risk_band ? ` · ${row.risk_band}` : ""}`,
      });
      setConsentConfirmed(false);
      setConsentReference("");
      setPostalCode("");
      setAddress1("");
      setAddress2("");
      setForceRefresh(false);
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
              Use LoanHub&apos;s centrally secured Experian connection. Your company requests access; the Platform Owner approves the subscription, controls the provider connection and charges your company per successful fresh bureau transaction.
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
            The LoanHub Platform Owner must configure the Experian Lesotho credentials, pass the connectivity test and enable Experian under Platform configuration → API &amp; integrations. Companies cannot enter or view those secrets.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Central Experian connection ready</AlertTitle>
          <AlertDescription>
            {titleCase(environment)} mode · connection {configuration?.platform.environments?.[environment]?.last_test_status === "connected" ? "tested" : "not tested"}. Paid checks can run only after Platform Owner subscription approval.
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
            <Info label="Connection test" value={configuration?.platform.last_test_status ? titleCase(configuration.platform.last_test_status) : "Not tested"} good={configuration?.platform.last_test_status === "connected"} />
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
            <div className="rounded-2xl border p-4">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="flex items-center gap-2 font-black"><WalletCards className="h-4 w-4 text-primary" />Credit Bureau PAYG subscription</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Status: <strong>{titleCase(subscription?.status || "not subscribed")}</strong>
                    {subscription?.price_per_transaction != null ? ` · ${formatMoney(subscription.price_per_transaction)} per successful fresh enquiry` : ""}
                  </p>
                  {subscription?.rejection_reason ? <p className="mt-2 text-xs text-destructive">{subscription.rejection_reason}</p> : null}
                </div>
                {canConfigure && subscription?.status !== "approved" && subscription?.status !== "pending" ? (
                  <LoadingButton loading={requestingSubscription} onClick={() => void requestSubscription()}>
                    Request subscription
                  </LoadingButton>
                ) : null}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">Approval is controlled only by the LoanHub Platform Owner. Reusing a still-fresh report is not charged; forcing or requiring a fresh provider enquiry creates one PAYG transaction.</p>
            </div>

            <div className="rounded-2xl border p-4">
              <Field label="Experian mode for this company">
                <Select value={environment} onValueChange={(value) => setEnvironment(value as "sandbox" | "live")} disabled={!canConfigure}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sandbox">Sandbox · training and demonstrations</SelectItem>
                    <SelectItem value="live">Live · real credit-bureau enquiries</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <p className="mt-2 text-xs text-muted-foreground">
                Sandbox is intended for staff training, demonstrations and testing. Live sends real enquiries to the production Experian service and may create billable bureau transactions.
                {" "}Selected mode status: <strong>{selectedEnvironmentReady ? "ready" : "not ready"}</strong>.
              </p>
            </div>

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

            <div className="space-y-4 rounded-2xl border p-4">
              <Field label="When is an Experian report required?">
                <Select value={requirementMode} onValueChange={(value) => setRequirementMode(value as typeof requirementMode)} disabled={!canConfigure}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="optional">Optional · officer decides</SelectItem>
                    <SelectItem value="before_affordability">Required before affordability</SelectItem>
                    <SelectItem value="before_approval">Required before approval</SelectItem>
                    <SelectItem value="amount_threshold">Required above a loan amount</SelectItem>
                    <SelectItem value="selected_products">Required for selected products</SelectItem>
                  </SelectContent>
                </Select>
              </Field>

              {requirementMode === "amount_threshold" ? (
                <Field label="Require Experian for amounts at or above">
                  <Input type="number" min={0} step="0.01" value={requiredAboveAmount} onChange={(event) => setRequiredAboveAmount(event.target.value)} disabled={!canConfigure} placeholder="e.g. 5000" />
                </Field>
              ) : null}

              {requirementMode === "selected_products" ? (
                <div className="space-y-2">
                  <Label>Products that require Experian</Label>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {loanProducts.map((product) => (
                      <label key={product.id} className="flex items-start gap-3 rounded-xl border p-3 text-sm">
                        <Checkbox
                          checked={requiredProductIds.includes(product.id)}
                          onCheckedChange={(value) => setRequiredProductIds((current) => value === true ? [...new Set([...current, product.id])] : current.filter((id) => id !== product.id))}
                          disabled={!canConfigure}
                        />
                        <span><strong>{product.name}</strong><span className="mt-1 block text-xs text-muted-foreground">{formatMoney(product.min_amount)} – {formatMoney(product.max_amount)}</span></span>
                      </label>
                    ))}
                    {!loanProducts.length ? <p className="text-sm text-muted-foreground">No active loan products are available.</p> : null}
                  </div>
                </div>
              ) : null}

              <p className="text-xs text-muted-foreground">
                Optional means LoanHub never blocks the loan because of Experian. Amount and product rules are enforced at approval; the affordability rule is enforced before affordability and remains protected at approval.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Toggle label="Use bureau commitments in affordability" checked={includeCommitments} onChange={setIncludeCommitments} disabled={!canConfigure} />
              <Toggle label="Block applicants with defaults" checked={blockDefaults} onChange={setBlockDefaults} disabled={!canConfigure} />
              <Toggle label="Require identity match" checked={requireIdentityMatch} onChange={setRequireIdentityMatch} disabled={!canConfigure} />
            </div>

            {canConfigure ? <LoadingButton loading={saving} onClick={() => void saveCompanySettings()} disabled={!subscriptionApproved}><Save className="h-4 w-4" />Save company policy</LoadingButton> : null}
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

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Field label="Enquiry purpose">
              <Select value={enquiryPurpose} onValueChange={setEnquiryPurpose} disabled={!canRun}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="12">12 · Credit Assessment</SelectItem>
                  <SelectItem value="11">11 · Affordability Assessment</SelectItem>
                  <SelectItem value="16">16 · Account Management</SelectItem>
                  <SelectItem value="15">15 · Debt Collection</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label="Postal code"><Input maxLength={5} value={postalCode} onChange={(event) => setPostalCode(event.target.value)} disabled={!canRun} placeholder="Required by Experian" /></Field>
            <Field label="Address line 1 override"><Input maxLength={25} value={address1} onChange={(event) => setAddress1(event.target.value)} disabled={!canRun} placeholder="Uses borrower address if blank" /></Field>
            <Field label="Address line 2 override"><Input maxLength={25} value={address2} onChange={(event) => setAddress2(event.target.value)} disabled={!canRun} placeholder="Uses town/district if blank" /></Field>
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

          <div className="grid gap-3 lg:grid-cols-2">
            <label className="flex items-start gap-3 rounded-2xl border p-4">
              <Checkbox checked={consentConfirmed} onCheckedChange={(value) => setConsentConfirmed(value === true)} disabled={!canRun || !companyReady} />
              <span><strong>Borrower consent confirmed for this credit application</strong><span className="mt-1 block text-xs text-muted-foreground">LoanHub stores the consent method/reference with the company-scoped bureau enquiry.</span></span>
            </label>
            <label className="flex items-start gap-3 rounded-2xl border p-4">
              <Checkbox checked={forceRefresh} onCheckedChange={(value) => setForceRefresh(value === true)} disabled={!canRun || !companyReady} />
              <span><strong>Force a new paid enquiry</strong><span className="mt-1 block text-xs text-muted-foreground">Leave off to reuse a successful report that is still within the company&apos;s maximum report age.</span></span>
            </label>
          </div>

          <LoadingButton loading={running} disabled={!canRun || !companyReady || !selectedApplicationId || !consentConfirmed || !postalCode.trim()} onClick={() => void runCreditCheck()}><Play className="h-4 w-4" />Run Experian credit check</LoadingButton>
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
