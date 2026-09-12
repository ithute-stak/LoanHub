"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Boxes,
  BriefcaseBusiness,
  Building2,
  Calculator,
  ChartNoAxesCombined,
  CheckCircle2,
  ClipboardCheck,
  FileBarChart,
  Gauge,
  KeyRound,
  Loader2,
  Plus,
  RefreshCcw,
  Scale,
  Send,
  ShieldCheck,
  Webhook,
} from "lucide-react";

import {
  askCompanyDataAssistant,
  createCompanyApiKey,
  createCompanyWebhook,
  createOperatingRecord,
  generateCompanyBoardPack,
  getCollectionsStrategy,
  getCompanyCapabilities,
  getCompanyCommandDashboard,
  getReconciliationSummary,
  listCompanyApiKeys,
  listCompanyWebhooks,
  listOperatingRecords,
  revokeCompanyApiKey,
  simulateCompanyPricing,
  type APIKeyRecord,
  type CompanyCapability,
  type CompanyCommandDashboard,
  type OperatingRecord,
  type WebhookRecord,
} from "@/api/companyOperatingSystem";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";

const WORK_MODULES = [
  ["crm", "CRM & relationships"],
  ["credit_committee", "Credit committee"],
  ["collateral", "Collateral & guarantors"],
  ["legal_recovery", "Legal recovery"],
  ["complaints", "Complaints & service cases"],
  ["communications", "Communications"],
  ["marketing", "Marketing & retention"],
  ["agents", "Agents & field officers"],
  ["employer_partnerships", "Employer partnerships"],
  ["procurement", "Procurement & vendors"],
  ["assets", "Company assets"],
  ["internal_audit", "Internal audit"],
  ["budgeting", "Budgets & forecasts"],
  ["targets", "Management targets / KPIs"],
  ["business_continuity", "Business continuity"],
  ["integrations", "Integration hub"],
  ["document_automation", "Document automation"],
  ["board_packs", "Board-pack actions"],
] as const;

const TABS = [
  ["overview", "Executive", Gauge],
  ["operations", "Operating workflows", BriefcaseBusiness],
  ["credit", "Credit & finance", Calculator],
  ["integrations", "Integrations", Webhook],
  ["board", "Board & assistant", Bot],
] as const;

type TabKey = (typeof TABS)[number][0];

type PricingForm = {
  principal: string;
  rate: string;
  term: string;
  fee: string;
  method: string;
};

function errorMessage(error: unknown): string {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "The operation could not be completed.";
}

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <article className="rounded-2xl border bg-card p-4 shadow-sm">
      <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-black tracking-tight">{value}</p>
      {detail ? <p className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</p> : null}
    </article>
  );
}

export function CompanyOperatingSystemCentre() {
  const [tab, setTab] = useState<TabKey>("overview");
  const [dashboard, setDashboard] = useState<CompanyCommandDashboard | null>(null);
  const [capabilities, setCapabilities] = useState<CompanyCapability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [module, setModule] = useState<string>("crm");
  const [records, setRecords] = useState<OperatingRecord[]>([]);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [recordTitle, setRecordTitle] = useState("");
  const [recordType, setRecordType] = useState("action");
  const [recordDescription, setRecordDescription] = useState("");
  const [recordPriority, setRecordPriority] = useState("normal");
  const [recordCounterparty, setRecordCounterparty] = useState("");
  const [recordAmount, setRecordAmount] = useState("");

  const [pricing, setPricing] = useState<PricingForm>({
    principal: "10000",
    rate: "10",
    term: "6",
    fee: "0",
    method: "micro_loan",
  });
  const [pricingResult, setPricingResult] = useState<Record<string, unknown> | null>(null);
  const [collections, setCollections] = useState<Record<string, unknown> | null>(null);
  const [reconciliation, setReconciliation] = useState<Record<string, unknown> | null>(null);

  const [apiKeys, setApiKeys] = useState<APIKeyRecord[]>([]);
  const [webhooks, setWebhooks] = useState<WebhookRecord[]>([]);
  const [apiKeyName, setApiKeyName] = useState("Operations integration");
  const [webhookName, setWebhookName] = useState("LoanHub events");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [oneTimeSecret, setOneTimeSecret] = useState<string | null>(null);

  const [question, setQuestion] = useState("What needs management attention today?");
  const [assistantAnswer, setAssistantAnswer] = useState<string | null>(null);
  const [assistantNotice, setAssistantNotice] = useState<string | null>(null);
  const [boardPack, setBoardPack] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  const loadCore = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextDashboard, nextCapabilities] = await Promise.all([
        getCompanyCommandDashboard(),
        getCompanyCapabilities(),
      ]);
      setDashboard(nextDashboard);
      setCapabilities(nextCapabilities);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCore();
  }, [loadCore]);

  async function loadRecords(selectedModule: string) {
    setRecordsLoading(true);
    setError(null);
    try {
      setRecords(await listOperatingRecords(selectedModule));
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setRecordsLoading(false);
    }
  }

  async function chooseTab(nextTab: TabKey) {
    setTab(nextTab);
    if (nextTab === "operations") await loadRecords(module);
  }

  async function chooseModule(nextModule: string) {
    setModule(nextModule);
    await loadRecords(nextModule);
  }

  async function submitRecord() {
    if (!recordTitle.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createOperatingRecord({
        module,
        record_type: recordType.trim() || "action",
        title: recordTitle.trim(),
        description: recordDescription.trim() || undefined,
        priority: recordPriority,
        counterparty_name: recordCounterparty.trim() || undefined,
        amount: recordAmount ? Number(recordAmount) : undefined,
        data: { source: "company_operating_system" },
      });
      setRecordTitle("");
      setRecordDescription("");
      setRecordCounterparty("");
      setRecordAmount("");
      await Promise.all([loadRecords(module), loadCore()]);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function runPricing() {
    setBusy(true);
    setError(null);
    try {
      setPricingResult(
        await simulateCompanyPricing({
          principal: Number(pricing.principal),
          rate_percent: Number(pricing.rate),
          term_months: Number(pricing.term),
          processing_fee: Number(pricing.fee),
          interest_method: pricing.method,
        }),
      );
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function loadCreditControls() {
    setBusy(true);
    setError(null);
    try {
      const [collectionData, reconciliationData] = await Promise.all([
        getCollectionsStrategy(),
        getReconciliationSummary(),
      ]);
      setCollections(collectionData);
      setReconciliation(reconciliationData);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function loadIntegrationSecurity() {
    setBusy(true);
    setError(null);
    try {
      const [keys, hooks] = await Promise.all([listCompanyApiKeys(), listCompanyWebhooks()]);
      setApiKeys(keys);
      setWebhooks(hooks);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function issueApiKey() {
    setBusy(true);
    setError(null);
    try {
      const issued = await createCompanyApiKey({
        name: apiKeyName.trim() || "Company integration",
        scopes: ["read:portfolio", "read:payments", "read:customers"],
      });
      setOneTimeSecret(`API key shown once: ${issued.api_key}`);
      const keys = await listCompanyApiKeys();
      setApiKeys(keys);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function revokeApiKey(id: string) {
    setBusy(true);
    setError(null);
    try {
      await revokeCompanyApiKey(id);
      setApiKeys(await listCompanyApiKeys());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function issueWebhook() {
    if (!webhookUrl.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const issued = await createCompanyWebhook({
        name: webhookName.trim() || "Company webhook",
        endpoint_url: webhookUrl.trim(),
        event_types: ["loan.updated", "payment.succeeded", "borrower.requested"],
      });
      setOneTimeSecret(`Webhook signing secret shown once: ${issued.signing_secret}`);
      setWebhookUrl("");
      setWebhooks(await listCompanyWebhooks());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function createBoardPack() {
    setBusy(true);
    setError(null);
    try {
      setBoardPack(await generateCompanyBoardPack());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function askAssistant() {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const response = await askCompanyDataAssistant(question.trim());
      setAssistantAnswer(response.answer);
      setAssistantNotice(response.notice);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  if (loading && !dashboard) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Loader2 className="h-7 w-7 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      <section className="relative overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground">
              <Building2 className="h-4 w-4 text-primary" /> Company Operating System
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Executive Command Centre</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
              Lending, customers, risk, treasury, collections, governance, planning, integrations and management intelligence in one company-scoped workspace.
            </p>
          </div>
          <button type="button" onClick={() => void loadCore()} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black">
            <RefreshCcw className="h-4 w-4" /> Refresh command data
          </button>
        </div>
      </section>

      {error ? (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">
          {error}
        </div>
      ) : null}

      <nav className="flex gap-2 overflow-x-auto rounded-2xl border bg-card p-2" aria-label="Company operating system sections">
        {TABS.map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            onClick={() => void chooseTab(key)}
            className={`inline-flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-black transition ${tab === key ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </nav>

      {tab === "overview" && dashboard ? (
        <div className="space-y-6">
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Metric label="Portfolio balance" value={formatMoney(dashboard.portfolio.portfolio_balance)} detail={`${dashboard.portfolio.active_loans} active / approved loans`} />
            <Metric label="Expected 30-day collections" value={formatMoney(dashboard.portfolio.expected_collections_30_days)} detail={`${dashboard.portfolio.overdue_loans} overdue loan(s)`} />
            <Metric label="PAR 30" value={`${dashboard.portfolio.par_30.toFixed(2)}%`} detail={`PAR 7 ${dashboard.portfolio.par_7.toFixed(2)}% · PAR 90 ${dashboard.portfolio.par_90.toFixed(2)}%`} />
            <Metric label="Recorded net liquidity" value={formatMoney(dashboard.treasury.net_recorded_liquidity)} detail={`${dashboard.treasury.entry_count} treasury entries`} />
            <Metric label="Contractual margin" value={formatMoney(dashboard.profitability.contractual_margin)} detail="Management view; Accounting remains authoritative" />
          </section>

          <section className="grid gap-4 xl:grid-cols-3">
            <article className="rounded-3xl border bg-card p-5 xl:col-span-2">
              <div className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-amber-500" /><h2 className="text-lg font-black">Management attention</h2></div>
              <div className="mt-4 space-y-3">
                {dashboard.warnings.length ? dashboard.warnings.map((warning, index) => (
                  <div key={`${warning.title}-${index}`} className="rounded-2xl border p-4">
                    <p className="font-black">{warning.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{warning.detail}</p>
                  </div>
                )) : (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-bold text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
                    <CheckCircle2 className="mr-2 inline h-4 w-4" /> No command-centre warning threshold is currently triggered.
                  </div>
                )}
              </div>
            </article>
            <article className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">Governance pulse</h2>
              <div className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between gap-3"><span className="text-muted-foreground">Compliance cases</span><b>{dashboard.governance.open_compliance_cases}</b></div>
                <div className="flex justify-between gap-3"><span className="text-muted-foreground">Reconciliation exceptions</span><b>{dashboard.governance.open_reconciliation_exceptions}</b></div>
                <div className="flex justify-between gap-3"><span className="text-muted-foreground">Active approval workflows</span><b>{dashboard.governance.active_approval_workflows}</b></div>
                <div className="flex justify-between gap-3"><span className="text-muted-foreground">Unresolved system errors</span><b>{dashboard.governance.unresolved_system_errors}</b></div>
                <div className="flex justify-between gap-3"><span className="text-muted-foreground">Overdue operating actions</span><b>{dashboard.operations.overdue_actions}</b></div>
              </div>
            </article>
          </section>

          <section className="rounded-3xl border bg-card p-5 md:p-6">
            <div className="flex items-center gap-2"><Boxes className="h-5 w-5 text-primary" /><h2 className="text-xl font-black">All 34 company capabilities</h2></div>
            <p className="mt-1 text-sm text-muted-foreground">Existing specialist engines remain authoritative; the command centre coordinates and exposes them.</p>
            <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {capabilities.map((capability) => (
                <div key={capability.number} className="rounded-2xl border p-3">
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-black text-primary">{capability.number}</span>
                    <div><p className="text-sm font-black">{capability.name}</p><p className="mt-0.5 text-xs text-muted-foreground">{capability.implementation}</p></div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      ) : null}

      {tab === "operations" ? (
        <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
          <aside className="rounded-3xl border bg-card p-4">
            <h2 className="font-black">Operating module</h2>
            <div className="mt-3 max-h-[65vh] space-y-1 overflow-y-auto pr-1">
              {WORK_MODULES.map(([key, label]) => (
                <button key={key} type="button" onClick={() => void chooseModule(key)} className={`w-full rounded-xl px-3 py-2 text-left text-sm font-bold ${module === key ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>{label}</button>
              ))}
            </div>
          </aside>
          <div className="space-y-5">
            <section className="rounded-3xl border bg-card p-5">
              <div className="flex items-center gap-2"><Plus className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">New {titleCase(module)} record</h2></div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <input value={recordTitle} onChange={(event) => setRecordTitle(event.target.value)} placeholder="Title / action" className="h-11 rounded-xl border bg-background px-3 text-sm" />
                <input value={recordType} onChange={(event) => setRecordType(event.target.value)} placeholder="Record type" className="h-11 rounded-xl border bg-background px-3 text-sm" />
                <input value={recordCounterparty} onChange={(event) => setRecordCounterparty(event.target.value)} placeholder="Customer, supplier, employer or counterparty" className="h-11 rounded-xl border bg-background px-3 text-sm" />
                <div className="grid grid-cols-2 gap-2">
                  <select value={recordPriority} onChange={(event) => setRecordPriority(event.target.value)} className="h-11 rounded-xl border bg-background px-3 text-sm">
                    <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="critical">Critical</option>
                  </select>
                  <input type="number" value={recordAmount} onChange={(event) => setRecordAmount(event.target.value)} placeholder="Amount" className="h-11 rounded-xl border bg-background px-3 text-sm" />
                </div>
                <textarea value={recordDescription} onChange={(event) => setRecordDescription(event.target.value)} placeholder="Notes, conditions, next action or evidence" className="min-h-24 rounded-xl border bg-background p-3 text-sm md:col-span-2" />
              </div>
              <button type="button" disabled={busy || !recordTitle.trim()} onClick={() => void submitRecord()} className="mt-4 inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Create record
              </button>
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card">
              <div className="flex items-center justify-between border-b p-5">
                <div><h2 className="text-lg font-black">{titleCase(module)} work queue</h2><p className="mt-1 text-sm text-muted-foreground">Tenant and branch scoped operating actions with audit timestamps.</p></div>
                <button type="button" onClick={() => void loadRecords(module)} className="rounded-xl border p-2"><RefreshCcw className={`h-4 w-4 ${recordsLoading ? "animate-spin" : ""}`} /></button>
              </div>
              <div className="divide-y">
                {recordsLoading && !records.length ? <p className="p-8 text-center text-sm text-muted-foreground">Loading work queue...</p> : null}
                {!recordsLoading && !records.length ? <p className="p-8 text-center text-sm text-muted-foreground">No records in this module yet.</p> : null}
                {records.map((record) => (
                  <div key={record.id} className="p-5">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2"><p className="font-black">{record.title}</p><span className="rounded-full bg-muted px-2 py-1 text-[11px] font-black">{titleCase(record.status)}</span><span className="rounded-full border px-2 py-1 text-[11px] font-bold">{record.reference}</span></div>
                        <p className="mt-1 text-sm text-muted-foreground">{record.description || titleCase(record.record_type)}</p>
                        {record.counterparty_name ? <p className="mt-2 text-xs font-bold">Counterparty: {record.counterparty_name}</p> : null}
                      </div>
                      <div className="sm:text-right">{record.amount != null ? <p className="font-black">{formatMoney(record.amount)}</p> : null}<p className="mt-1 text-xs text-muted-foreground">Updated {formatDateTime(record.updated_at)}</p></div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      ) : null}

      {tab === "credit" ? (
        <div className="space-y-6">
          <section className="grid gap-5 xl:grid-cols-2">
            <article className="rounded-3xl border bg-card p-5">
              <div className="flex items-center gap-2"><Calculator className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Product & pricing laboratory</h2></div>
              <p className="mt-1 text-sm text-muted-foreground">Uses the authoritative LoanHub interest calculation engine. It does not publish or approve a product.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <input type="number" value={pricing.principal} onChange={(event) => setPricing((current) => ({ ...current, principal: event.target.value }))} className="h-11 rounded-xl border bg-background px-3" placeholder="Principal" />
                <input type="number" value={pricing.rate} onChange={(event) => setPricing((current) => ({ ...current, rate: event.target.value }))} className="h-11 rounded-xl border bg-background px-3" placeholder="Rate %" />
                <input type="number" value={pricing.term} onChange={(event) => setPricing((current) => ({ ...current, term: event.target.value }))} className="h-11 rounded-xl border bg-background px-3" placeholder="Months" />
                <input type="number" value={pricing.fee} onChange={(event) => setPricing((current) => ({ ...current, fee: event.target.value }))} className="h-11 rounded-xl border bg-background px-3" placeholder="Processing fee" />
                <select value={pricing.method} onChange={(event) => setPricing((current) => ({ ...current, method: event.target.value }))} className="h-11 rounded-xl border bg-background px-3 sm:col-span-2">
                  <option value="micro_loan">LoanHub Micro Loan</option><option value="simple_interest">Simple interest</option><option value="flat_rate">Flat rate</option><option value="compound_interest">Compound interest</option><option value="reducing_balance">Reducing balance</option><option value="daily_accrual_reducing">Daily accrual reducing</option>
                </select>
              </div>
              <button type="button" onClick={() => void runPricing()} disabled={busy} className="mt-4 inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground"><Calculator className="h-4 w-4" /> Simulate pricing</button>
              {pricingResult ? <div className="mt-4 rounded-2xl bg-muted p-4 text-sm"><p className="font-black">Estimated installment: {formatMoney(Number(pricingResult.monthly_installment ?? 0))}</p><p className="mt-1">Total repayable: {formatMoney(Number(pricingResult.total_repayable ?? 0))}</p><p className="mt-1">Contractual margin: {formatMoney(Number(pricingResult.contractual_margin ?? 0))}</p></div> : null}
            </article>

            <article className="rounded-3xl border bg-card p-5">
              <div className="flex items-center gap-2"><Scale className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Collections, reconciliation & risk controls</h2></div>
              <p className="mt-1 text-sm text-muted-foreground">Reads the existing CollectionCase and ReconciliationException engines.</p>
              <button type="button" onClick={() => void loadCreditControls()} disabled={busy} className="mt-4 inline-flex h-11 items-center gap-2 rounded-xl border px-4 text-sm font-black"><RefreshCcw className="h-4 w-4" /> Load strategy data</button>
              {collections ? <div className="mt-4 rounded-2xl border p-4"><p className="font-black">Collections strategy</p><pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">{JSON.stringify(collections, null, 2)}</pre></div> : null}
              {reconciliation ? <div className="mt-3 rounded-2xl border p-4"><p className="font-black">Reconciliation</p><pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">{JSON.stringify(reconciliation, null, 2)}</pre></div> : null}
            </article>
          </section>

          <section className="rounded-3xl border bg-card p-5">
            <div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Credit committee & internal risk</h2></div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Credit committee cases are managed in Operating workflows while the existing LoanHub CreditDecisionPolicy, CreditDecision and WorkflowInstance engines remain authoritative. Borrower risk views are company-scoped decision support and remain separate from external credit-bureau scores.</p>
          </section>
        </div>
      ) : null}

      {tab === "integrations" ? (
        <div className="space-y-6">
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div><div className="flex items-center gap-2"><KeyRound className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">API keys & webhooks</h2></div><p className="mt-1 text-sm text-muted-foreground">Owner/admin controlled credentials. Raw keys and signing secrets are shown once and never stored in plaintext.</p></div>
              <button type="button" onClick={() => void loadIntegrationSecurity()} className="h-11 rounded-xl border px-4 text-sm font-black">Load credentials</button>
            </div>
            {oneTimeSecret ? <div className="mt-4 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"><p className="font-black">Copy this now</p><p className="mt-2 break-all font-mono text-xs">{oneTimeSecret}</p></div> : null}
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <article className="rounded-3xl border bg-card p-5">
              <h3 className="font-black">Issue company API key</h3>
              <input value={apiKeyName} onChange={(event) => setApiKeyName(event.target.value)} className="mt-3 h-11 w-full rounded-xl border bg-background px-3" />
              <button type="button" onClick={() => void issueApiKey()} disabled={busy} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Create API key</button>
              <div className="mt-4 space-y-2">{apiKeys.map((key) => <div key={key.id} className="rounded-xl border p-3 text-sm"><div className="flex items-center justify-between gap-3"><div><p className="font-black">{key.name}</p><p className="font-mono text-xs text-muted-foreground">{key.key_prefix}…</p></div>{!key.revoked_at ? <button type="button" onClick={() => void revokeApiKey(key.id)} className="text-xs font-black text-destructive">Revoke</button> : <span className="text-xs font-bold text-muted-foreground">Revoked</span>}</div></div>)}</div>
            </article>
            <article className="rounded-3xl border bg-card p-5">
              <h3 className="font-black">Register webhook</h3>
              <input value={webhookName} onChange={(event) => setWebhookName(event.target.value)} className="mt-3 h-11 w-full rounded-xl border bg-background px-3" />
              <input value={webhookUrl} onChange={(event) => setWebhookUrl(event.target.value)} placeholder="https://your-system.example/webhooks/loanhub" className="mt-2 h-11 w-full rounded-xl border bg-background px-3" />
              <button type="button" onClick={() => void issueWebhook()} disabled={busy || !webhookUrl.trim()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Create webhook</button>
              <div className="mt-4 space-y-2">{webhooks.map((hook) => <div key={hook.id} className="rounded-xl border p-3 text-sm"><p className="font-black">{hook.name}</p><p className="mt-1 truncate text-xs text-muted-foreground">{hook.endpoint_url}</p><p className="mt-1 text-xs">Failures: {hook.failure_count} · {hook.is_active ? "Active" : "Inactive"}</p></div>)}</div>
            </article>
          </section>

          <section className="rounded-3xl border bg-card p-5">
            <div className="flex items-center gap-2"><Boxes className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Integration Hub</h2></div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Use the Integrations operating module to register bank, mobile-money, payroll, credit-bureau, identity, accounting, SMS/email and debt-collection configurations. Provider credentials still require protected server configuration or dedicated encrypted fields.</p>
          </section>
        </div>
      ) : null}

      {tab === "board" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex items-center gap-2"><FileBarChart className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Board / management pack</h2></div>
            <p className="mt-2 text-sm text-muted-foreground">Captures a governed management snapshot in the existing LoanHub GeneratedReport registry for auditability and later scheduled file generation.</p>
            <button type="button" disabled={busy} onClick={() => void createBoardPack()} className="mt-4 inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground"><ChartNoAxesCombined className="h-4 w-4" /> Generate management pack</button>
            {boardPack ? <div className="mt-4 rounded-2xl border p-4"><p className="font-black">Generated successfully</p><p className="mt-1 text-sm text-muted-foreground">Reference: {String(boardPack.reference ?? "")}</p></div> : null}
          </section>

          <section className="rounded-3xl border bg-card p-5">
            <div className="flex items-center gap-2"><Bot className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Company Data Assistant</h2></div>
            <p className="mt-2 text-sm text-muted-foreground">Role-governed deterministic analytics over the same command-centre snapshot. It does not approve loans, make legal decisions or post accounting entries.</p>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} className="mt-4 min-h-28 w-full rounded-xl border bg-background p-3 text-sm" />
            <button type="button" onClick={() => void askAssistant()} disabled={busy || !question.trim()} className="mt-3 inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground"><Send className="h-4 w-4" /> Ask about company data</button>
            {assistantAnswer ? <div className="mt-4 rounded-2xl border p-4"><p className="font-black">Answer</p><p className="mt-2 text-sm leading-6">{assistantAnswer}</p>{assistantNotice ? <p className="mt-3 text-xs leading-5 text-muted-foreground">{assistantNotice}</p> : null}</div> : null}
          </section>

          <section className="rounded-3xl border bg-card p-5 xl:col-span-2">
            <div className="flex items-center gap-2"><ClipboardCheck className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Document automation</h2></div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Configure approval letters, rejection letters, agreements, schedules, settlement quotations, paid-up letters, demand letters, employee letters and board-report triggers in the Document automation operating module. Generated content continues to use the LoanHub Document Studio and versioned document infrastructure instead of duplicating signed documents in this command-centre table.</p>
          </section>
        </div>
      ) : null}
    </div>
  );
}
