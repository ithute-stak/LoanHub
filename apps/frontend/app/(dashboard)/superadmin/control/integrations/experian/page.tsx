"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ArrowLeft, BadgeCheck, CircleAlert, KeyRound, RefreshCcw, Save, ShieldCheck, TestTube2 } from "lucide-react";

import { platformCreditBureauApi } from "@/api/creditBureau";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { titleCase } from "@/lib/format";
import type { CreditBureauSubscription, ExperianPlatformConfiguration } from "@/types/creditBureau";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const EMPTY_JSON = "{}";

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function parseObject(value: string, label: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value || "{}");
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

export default function PlatformExperianConfigurationPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [configuration, setConfiguration] = useState<ExperianPlatformConfiguration | null>(null);
  const [subscriptions, setSubscriptions] = useState<CreditBureauSubscription[]>([]);
  const [decidingCompanyId, setDecidingCompanyId] = useState<string | null>(null);

  const [environment, setEnvironment] = useState<"sandbox" | "live">("sandbox");
  const [enabled, setEnabled] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [origin, setOrigin] = useState("LNHUB");
  const [originVersion, setOriginVersion] = useState("1.0");
  const [dllVersion, setDllVersion] = useState("1.0");
  const [responseMapping, setResponseMapping] = useState(EMPTY_JSON);
  const [defaultTransactionPrice, setDefaultTransactionPrice] = useState("0");
  const [billingCurrency, setBillingCurrency] = useState("LSL");

  const applyConfiguration = useCallback((row: ExperianPlatformConfiguration) => {
    setConfiguration(row);
    setEnvironment(row.environment === "live" || row.environment === "production" ? "live" : "sandbox");
    setEnabled(Boolean(row.is_enabled));
    setOrigin(String(row.configuration.origin ?? "LNHUB"));
    setOriginVersion(String(row.configuration.origin_version ?? "1.0"));
    setDllVersion(String(row.configuration.dll_version ?? "1.0"));
    setResponseMapping(prettyJson(row.configuration.response_mapping ?? {}));
    setDefaultTransactionPrice(String(row.configuration.default_price_per_transaction ?? 0));
    setBillingCurrency(String(row.configuration.billing_currency ?? "LSL"));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [config, subscriptionRows] = await Promise.all([
        platformCreditBureauApi.getExperianConfiguration(),
        platformCreditBureauApi.listExperianSubscriptions(),
      ]);
      applyConfiguration(config);
      setSubscriptions(subscriptionRows);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Platform Experian configuration could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [applyConfiguration]);

  useEffect(() => { void load(); }, [load]);

  async function saveConfiguration() {
    setSaving(true);
    try {
      const mapping = parseObject(responseMapping, "Response mapping");
      const credentialValues = [username, password].map((value) => value.trim());
      const supplyingCredentials = credentialValues.some(Boolean);
      if (supplyingCredentials && credentialValues.some((value) => !value)) {
        throw new Error("Enter Experian username and password together when adding or rotating credentials.");
      }

      const updated = await platformCreditBureauApi.updateExperianConfiguration({
        environment,
        is_enabled: enabled,
        configuration: {
          region: "lesotho",
          product: "normal_search_v2",
          origin: origin.trim() || "LNHUB",
          origin_version: originVersion.trim() || "1.0",
          dll_version: dllVersion.trim() || "1.0",
          response_mapping: mapping,
          default_price_per_transaction: Math.max(0, Number(defaultTransactionPrice || 0)),
          billing_currency: billingCurrency.trim().toUpperCase() || "LSL",
        },
        credentials: supplyingCredentials
          ? {
              username: username.trim(),
              password,
            }
          : null,
      });
      setUsername("");
      setPassword("");
      applyConfiguration(updated);
      toast.success("Platform Experian configuration saved", {
        description: supplyingCredentials
          ? "The new credentials were encrypted and stored centrally."
          : "Existing encrypted credentials were preserved.",
      });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Platform Experian configuration could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  async function decideSubscription(companyId: string, decision: "approved" | "rejected" | "suspended") {
    setDecidingCompanyId(companyId);
    try {
      await platformCreditBureauApi.decideExperianSubscription(companyId, {
        decision,
        price_per_transaction: decision === "approved" ? Math.max(0, Number(defaultTransactionPrice || 0)) : undefined,
        currency: billingCurrency.trim().toUpperCase() || "LSL",
      });
      toast.success(`Credit Bureau subscription ${decision}`);
      setSubscriptions(await platformCreditBureauApi.listExperianSubscriptions());
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Subscription decision could not be saved."));
    } finally {
      setDecidingCompanyId(null);
    }
  }

  async function testConnection() {
    setTesting(true);
    try {
      const result = await platformCreditBureauApi.testExperianConnection();
      toast.success("Experian Lesotho connection successful", {
        description: `${result.environment.toUpperCase()} · ${result.endpoint}`,
      });
      applyConfiguration(await platformCreditBureauApi.getExperianConfiguration());
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Experian Lesotho connection test failed."));
      await load();
    } finally {
      setTesting(false);
    }
  }

  if (loading) return <PageLoader rows={10} />;

  const readiness = configuration?.readiness;
  const selectedProfile = configuration?.environment_profiles?.[environment];

  return (
    <main className="loanhub-page space-y-6">
      <section className="loanhub-hero overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Platform configuration · Credit bureau</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Experian platform connection</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
              Configure the central Experian credential profiles for Sandbox and Live. Lending companies choose which mode they use; they never see or replace these provider credentials.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" asChild><Link href="/superadmin/control/integrations"><ArrowLeft className="h-4 w-4" />API &amp; integrations</Link></Button>
            <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh</Button>
          </div>
        </div>
      </section>

      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>Platform Owner controlled secret boundary</AlertTitle>
        <AlertDescription>
          Experian Lesotho username/password and the Normal Search configuration are stored at platform scope. Secrets are encrypted and are never returned to company workspaces or the browser after saving.
        </AlertDescription>
      </Alert>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <ReadinessCard label="Credentials" ready={Boolean(readiness?.credentials)} />
        <ReadinessCard label="Connection test" ready={Boolean(readiness?.connection_tested)} />
        <ReadinessCard label="Normal Search v0.5" ready={Boolean(readiness?.normal_search_contract)} />
        <ReadinessCard label="Response map" ready={Boolean(readiness?.response_mapping)} />
        <ReadinessCard label="Company ready" ready={Boolean(readiness?.ready_for_company_use)} />
      </div>

      {!readiness?.ready_for_company_use ? (
        <Alert variant="destructive">
          <CircleAlert className="h-4 w-4" />
          <AlertTitle>Experian is not yet ready for lending companies</AlertTitle>
          <AlertDescription>Complete all readiness items, pass the Experian Lesotho connectivity test, then enable the platform connection. Company Experian switches remain unavailable until this is ready.</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><KeyRound className="h-5 w-5 text-primary" />Experian Lesotho credentials</CardTitle>
<CardDescription>Store and test the Sandbox and Live credential profiles separately. This selector chooses which central credential profile you are editing; it does not force every lending company into that mode.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <Field label="Credential profile">
              <Select value={environment} onValueChange={(value) => setEnvironment(value as typeof environment)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="sandbox">Sandbox credentials · Experian Lesotho UAT</SelectItem>
                  <SelectItem value="live">Live credentials · Experian Lesotho production</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label="Experian username"><Input autoComplete="off" value={username} onChange={(event) => setUsername(event.target.value)} placeholder={selectedProfile?.has_credentials ? "Leave blank to keep stored value" : "Experian username"} /></Field>
            <Field label="Experian password"><Input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={selectedProfile?.has_credentials ? "Leave blank to keep stored value" : "Experian password"} /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <StatusLine label={`${environment === "live" ? "Live" : "Sandbox"} credentials`} value={selectedProfile?.has_credentials ? "Configured" : "Missing"} good={Boolean(selectedProfile?.has_credentials)} />
              <StatusLine label="Latest connection test" value={selectedProfile?.last_test_status ? titleCase(selectedProfile.last_test_status) : "Not tested"} good={selectedProfile?.last_test_status === "connected"} />
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle>Experian Lesotho Normal Search contract</CardTitle>
            <CardDescription>LoanHub now uses the fixed Normal Search v0.5 REST endpoints from the supplied Experian Lesotho specification. Only the origin/version values and optional report mapping remain configurable.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Origin"><Input maxLength={5} value={origin} onChange={(event) => setOrigin(event.target.value)} /></Field>
              <Field label="Origin version"><Input maxLength={5} value={originVersion} onChange={(event) => setOriginVersion(event.target.value)} /></Field>
              <Field label="DLL version"><Input maxLength={30} value={dllVersion} onChange={(event) => setDllVersion(event.target.value)} /></Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Default PAYG price per successful enquiry">
                <Input type="number" min={0} step="0.01" value={defaultTransactionPrice} onChange={(event) => setDefaultTransactionPrice(event.target.value)} />
              </Field>
              <Field label="Billing currency">
                <Input maxLength={3} value={billingCurrency} onChange={(event) => setBillingCurrency(event.target.value.toUpperCase())} />
              </Field>
            </div>
            <Field label="Response mapping (JSON)">
              <Textarea className="min-h-44 font-mono text-xs" value={responseMapping} onChange={(event) => setResponseMapping(event.target.value)} />
              <p className="text-xs text-muted-foreground">Map LoanHub fields such as <code>score</code>, <code>risk_band</code>, <code>monthly_commitments</code>, <code>total_balance</code>, <code>defaults_count</code> and <code>provider_reference</code> to dotted paths in the provider response.</p>
            </Field>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-3xl">
        <CardContent className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex items-start gap-3">
            <Checkbox checked={enabled} onCheckedChange={(value) => setEnabled(value === true)} />
            <span><strong>Enable Experian for LoanHub</strong><span className="mt-1 block max-w-2xl text-xs text-muted-foreground">Companies can only opt in after this central connection is enabled and fully ready. Save and test both profiles independently. Companies can then choose Sandbox for training/demonstrations or Live for real production enquiries.</span></span>
          </label>
          <div className="flex flex-wrap gap-2">
            <LoadingButton loading={saving} onClick={() => void saveConfiguration()}><Save className="h-4 w-4" />Save configuration</LoadingButton>
            <LoadingButton loading={testing} variant="outline" disabled={!selectedProfile?.has_credentials} onClick={() => void testConnection()}><TestTube2 className="h-4 w-4" />Test connection</LoadingButton>
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle>Loan company Credit Bureau subscriptions</CardTitle>
          <CardDescription>Companies can only request access. The Platform Owner approves, rejects or suspends access and owns the PAYG tariff.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {subscriptions.length ? subscriptions.map((subscription) => (
            <div key={subscription.company_id || subscription.id} className="flex flex-col gap-4 rounded-2xl border p-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="font-black">{subscription.company?.name || subscription.company_id || "Loan company"}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {titleCase(subscription.status)} · {subscription.price_per_transaction == null ? "Price set on approval" : `${subscription.currency} ${subscription.price_per_transaction.toFixed(2)} per successful fresh enquiry`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {subscription.status !== "approved" ? (
                  <LoadingButton loading={decidingCompanyId === subscription.company_id} onClick={() => subscription.company_id && void decideSubscription(subscription.company_id, "approved")}>
                    Approve at {billingCurrency} {Number(defaultTransactionPrice || 0).toFixed(2)}
                  </LoadingButton>
                ) : (
                  <LoadingButton variant="outline" loading={decidingCompanyId === subscription.company_id} onClick={() => subscription.company_id && void decideSubscription(subscription.company_id, "suspended")}>
                    Suspend
                  </LoadingButton>
                )}
                {subscription.status === "pending" ? (
                  <LoadingButton variant="outline" loading={decidingCompanyId === subscription.company_id} onClick={() => subscription.company_id && void decideSubscription(subscription.company_id, "rejected")}>
                    Reject
                  </LoadingButton>
                ) : null}
              </div>
            </div>
          )) : <p className="text-sm text-muted-foreground">No loan company has requested Credit Bureau access yet.</p>}
        </CardContent>
      </Card>

      <Alert>
        <BadgeCheck className="h-4 w-4" />
        <AlertTitle>Platform-owned PAYG service</AlertTitle>
        <AlertDescription>Configure and test the central Experian connection, set the PAYG transaction price, then approve lending-company subscription requests. A successful fresh provider enquiry creates one billable transaction; reuse of a fresh cached report does not.</AlertDescription>
      </Alert>
    </main>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function ReadinessCard({ label, ready }: { label: string; ready: boolean }) {
  return <Card className="rounded-2xl"><CardContent className="p-4"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p><p className={`mt-2 text-sm font-black ${ready ? "text-emerald-600" : "text-amber-600"}`}>{ready ? "Ready" : "Pending"}</p></CardContent></Card>;
}

function StatusLine({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return <div className="rounded-2xl border p-4"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p><p className={`mt-2 text-sm font-black ${good ? "text-emerald-600" : ""}`}>{value}</p></div>;
}
