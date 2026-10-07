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
  listCompanyBoardPacks,
  getCollectionsStrategy,
  getCompanyCapabilities,
  getCompanyCommandDashboard,
  getReconciliationSummary,
  getPrudentialIntelligence,
  savePrudentialProfile,
  createRelatedPartyRegister,
  createPrudentialFiling,
  generatePrudentialEvidencePack,
  runPrudentialStressTest,
  generatePrudentialStressEvidencePack,
  listCompanyApiKeys,
  listCompanyWebhooks,
  listOperatingRecords,
  revokeCompanyApiKey,
  simulateCompanyPricing,
  type APIKeyRecord,
  type CompanyCapability,
  type BoardGovernancePack,
  type CompanyCommandDashboard,
  type OperatingRecord,
  type PrudentialIntelligence,
  type PrudentialStressPack,
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
  ["prudential", "Prudential", ShieldCheck],
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
  const [boardPack, setBoardPack] = useState<BoardGovernancePack | null>(null);
  const [prudential, setPrudential] = useState<PrudentialIntelligence | null>(null);
  const [prudentialStress, setPrudentialStress] = useState<PrudentialStressPack | null>(null);
  const [stressCollectionRate, setStressCollectionRate] = useState("70");
  const [stressObligationRate, setStressObligationRate] = useState("110");
  const [stressUnexpectedOutflow, setStressUnexpectedOutflow] = useState("0");
  const [stressStage3Migration, setStressStage3Migration] = useState("15");
  const [stressWriteoff, setStressWriteoff] = useState("5");
  const [stressEclRate, setStressEclRate] = useState("80");
  const [prudentialFramework, setPrudentialFramework] = useState("Configured prudential monitoring framework");
  const [prudentialSource, setPrudentialSource] = useState("");
  const [prudentialCapital, setPrudentialCapital] = useState("");
  const [prudentialCurrentRatio, setPrudentialCurrentRatio] = useState("");
  const [prudentialGearing, setPrudentialGearing] = useState("");
  const [prudentialSingleExposure, setPrudentialSingleExposure] = useState("");
  const [prudentialRelatedExposure, setPrudentialRelatedExposure] = useState("");
  const [prudentialEclCoverage, setPrudentialEclCoverage] = useState("");
  const [prudentialLiquidity, setPrudentialLiquidity] = useState("");
  const [relatedBorrowerId, setRelatedBorrowerId] = useState("");
  const [relatedType, setRelatedType] = useState("");
  const [relatedDescription, setRelatedDescription] = useState("");
  const [filingName, setFilingName] = useState("");
  const [filingPeriodEnd, setFilingPeriodEnd] = useState("");
  const [filingDueAt, setFilingDueAt] = useState("");
  const [boardPackHistory, setBoardPackHistory] = useState<BoardGovernancePack[]>([]);
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
    if (nextTab === "board") {
      try {
        setBoardPackHistory(await listCompanyBoardPacks());
      } catch (nextError) {
        setError(errorMessage(nextError));
      }
    }
    if (nextTab === "prudential") {
      try {
        setPrudential(await getPrudentialIntelligence());
      } catch (nextError) {
        setError(errorMessage(nextError));
      }
    }
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

  async function runPrudentialStress(custom = false) {
    setBusy(true);
    setError(null);
    try {
      const payload = custom ? {
        scenarios: [{
          name: "Custom management stress",
          collection_rate_percent: Number(stressCollectionRate || 0),
          obligation_rate_percent: Number(stressObligationRate || 0),
          unexpected_outflow: Number(stressUnexpectedOutflow || 0),
          additional_stage3_migration_percent: Number(stressStage3Migration || 0),
          additional_writeoff_percent: Number(stressWriteoff || 0),
          stressed_ecl_rate_percent: Number(stressEclRate || 0),
        }],
      } : undefined;
      setPrudentialStress(await runPrudentialStressTest(payload));
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function exportPrudentialStressPack() {
    setBusy(true);
    setError(null);
    try {
      const result = await generatePrudentialStressEvidencePack();
      setPrudentialStress(result.metrics);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function savePrudentialConfiguration() {
    setBusy(true);
    setError(null);
    try {
      const numeric = (value: string) => value.trim() === "" ? null : Number(value);
      await savePrudentialProfile({
        jurisdiction: "Lesotho",
        framework_name: prudentialFramework.trim(),
        source_reference: prudentialSource.trim() || null,
        minimum_capital_ratio_percent: numeric(prudentialCapital),
        minimum_current_ratio: numeric(prudentialCurrentRatio),
        maximum_gearing_percent: numeric(prudentialGearing),
        maximum_single_borrower_exposure_percent_of_equity: numeric(prudentialSingleExposure),
        maximum_related_party_exposure_percent_of_equity: numeric(prudentialRelatedExposure),
        minimum_ecl_coverage_percent: numeric(prudentialEclCoverage),
        minimum_liquidity_buffer: numeric(prudentialLiquidity),
      });
      setPrudential(await getPrudentialIntelligence());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function addRelatedParty() {
    if (!relatedBorrowerId.trim() || !relatedType.trim() || !relatedDescription.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createRelatedPartyRegister({
        borrower_id: relatedBorrowerId.trim(),
        relationship_type: relatedType.trim(),
        relationship_description: relatedDescription.trim(),
      });
      setRelatedBorrowerId("");
      setRelatedType("");
      setRelatedDescription("");
      setPrudential(await getPrudentialIntelligence());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function addPrudentialFiling() {
    if (!filingName.trim() || !filingPeriodEnd || !filingDueAt) return;
    setBusy(true);
    setError(null);
    try {
      await createPrudentialFiling({
        filing_name: filingName.trim(),
        filing_period_end: new Date(`${filingPeriodEnd}T23:59:59`).toISOString(),
        due_at: new Date(`${filingDueAt}T17:00:00`).toISOString(),
        required_evidence: [],
        evidence_references: [],
      });
      setFilingName("");
      setPrudential(await getPrudentialIntelligence());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function exportPrudentialPack() {
    setBusy(true);
    setError(null);
    try {
      const pack = await generatePrudentialEvidencePack();
      setPrudential(pack.metrics);
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
      const generated = await generateCompanyBoardPack();
      setBoardPack(generated);
      setBoardPackHistory(await listCompanyBoardPacks());
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

      {tab === "prudential" ? (
        <div className="space-y-6">
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Regulatory & prudential intelligence</h2></div>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">LoanHub assesses prudential metrics only against explicitly configured thresholds. Missing rules remain not assessed rather than being treated as compliant.</p>
              </div>
              <button type="button" disabled={busy} onClick={() => void exportPrudentialPack()} className="inline-flex h-11 items-center gap-2 rounded-xl border bg-background px-4 text-sm font-black"><FileBarChart className="h-4 w-4" /> Generate evidence pack</button>
            </div>

            {prudential ? <>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="Regulatory status" value={titleCase(prudential.regulatory_status)} />
                <Metric label="Breaches" value={String(prudential.breach_count)} />
                <Metric label="Not assessed" value={String(prudential.not_assessed_count)} />
                <Metric label="Capital / exposure" value={prudential.metrics.capital_to_portfolio_exposure_percent == null ? "—" : `${prudential.metrics.capital_to_portfolio_exposure_percent.toFixed(2)}%`} />
                <Metric label="Largest borrower / equity" value={prudential.metrics.largest_borrower_exposure_percent_of_equity == null ? "—" : `${prudential.metrics.largest_borrower_exposure_percent_of_equity.toFixed(2)}%`} />
                <Metric label="ECL coverage" value={prudential.metrics.ecl_coverage_percent == null ? "—" : `${prudential.metrics.ecl_coverage_percent.toFixed(2)}%`} />
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">{prudential.assessments.map((item) => <div key={item.metric} className="rounded-xl border p-3"><div className="flex items-center justify-between gap-2"><span className="text-sm font-bold">{titleCase(item.metric)}</span><span className={`rounded-full px-2 py-0.5 text-xs font-black ${item.status === "breach" ? "bg-destructive/10 text-destructive" : item.status === "pass" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>{titleCase(item.status)}</span></div><p className="mt-2 text-xs text-muted-foreground">Value: {item.value ?? "—"} · Threshold: {item.threshold ?? "—"} {item.unit}</p></div>)}</div>
              <p className="mt-4 rounded-xl border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">{prudential.policy_note}</p>
            </> : null}
          </section>

          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <h2 className="text-lg font-black">Scenario capital & regulatory stress testing</h2>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">Simulate collection deterioration, higher obligations, Stage 3 migration, write-offs, additional ECL and liquidity shocks without changing live accounting, loans or prudential records.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy} onClick={() => void runPrudentialStress(false)} className="h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Run built-in stress scenarios</button>
                <button type="button" disabled={busy} onClick={() => void exportPrudentialStressPack()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Generate stress evidence pack</button>
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
              <input value={stressCollectionRate} onChange={(e) => setStressCollectionRate(e.target.value)} placeholder="Collection rate %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={stressObligationRate} onChange={(e) => setStressObligationRate(e.target.value)} placeholder="Obligation rate %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={stressUnexpectedOutflow} onChange={(e) => setStressUnexpectedOutflow(e.target.value)} placeholder="Unexpected outflow LSL" className="h-11 rounded-xl border bg-background px-3" />
              <input value={stressStage3Migration} onChange={(e) => setStressStage3Migration(e.target.value)} placeholder="Extra Stage 3 migration %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={stressWriteoff} onChange={(e) => setStressWriteoff(e.target.value)} placeholder="Additional write-off %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={stressEclRate} onChange={(e) => setStressEclRate(e.target.value)} placeholder="Stressed ECL rate %" className="h-11 rounded-xl border bg-background px-3" />
            </div>
            <button type="button" disabled={busy} onClick={() => void runPrudentialStress(true)} className="mt-3 h-11 rounded-xl border bg-background px-4 text-sm font-black">Run custom scenario</button>

            {prudentialStress ? <div className="mt-5 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Metric label="Baseline breaches" value={String(prudentialStress.baseline.breach_count)} />
                <Metric label="Baseline not assessed" value={String(prudentialStress.baseline.not_assessed_count)} />
                <Metric label="Scenarios" value={String(prudentialStress.scenarios.length)} />
                <Metric label="Worst scenario" value={prudentialStress.worst_scenario ?? "—"} />
              </div>
              <div className="grid gap-4 xl:grid-cols-3">{prudentialStress.scenarios.map((scenario) => <article key={scenario.name} className="rounded-2xl border p-4">
                <div className="flex items-start justify-between gap-3"><div><h3 className="font-black">{scenario.name}</h3><p className="mt-1 text-xs text-muted-foreground">{scenario.assumptions.collection_rate_percent}% collections · {scenario.assumptions.additional_stage3_migration_percent}% Stage 3 migration · {scenario.assumptions.additional_writeoff_percent}% write-off</p></div><span className={`rounded-full px-2 py-0.5 text-xs font-black ${scenario.status === "breach" ? "bg-destructive/10 text-destructive" : scenario.status === "within_configured_limits" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>{titleCase(scenario.status)}</span></div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div><p className="text-xs text-muted-foreground">Equity erosion</p><p className="font-black">{formatMoney(scenario.impact.equity_erosion)}</p></div>
                  <div><p className="text-xs text-muted-foreground">Stressed equity</p><p className="font-black">{formatMoney(scenario.impact.stressed_equity)}</p></div>
                  <div><p className="text-xs text-muted-foreground">Incremental ECL</p><p className="font-black">{formatMoney(scenario.impact.incremental_allowance)}</p></div>
                  <div><p className="text-xs text-muted-foreground">Minimum cash</p><p className="font-black">{formatMoney(scenario.impact.minimum_projected_cash)}</p></div>
                  <div><p className="text-xs text-muted-foreground">Capital / exposure</p><p className="font-black">{scenario.ratios.capital_to_portfolio_exposure_percent == null ? "—" : `${scenario.ratios.capital_to_portfolio_exposure_percent.toFixed(2)}%`}</p></div>
                  <div><p className="text-xs text-muted-foreground">Breaches</p><p className="font-black">{scenario.breach_count}</p></div>
                </div>
                <div className="mt-4 space-y-2">{scenario.assessments.map((item) => <div key={item.metric} className="flex items-center justify-between gap-2 rounded-xl border px-3 py-2 text-xs"><span>{titleCase(item.metric)}</span><span className="font-black">{titleCase(item.status)}</span></div>)}</div>
              </article>)}</div>
              <p className="rounded-xl border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">{prudentialStress.policy_note}</p>
            </div> : null}
          </section>

          <section className="rounded-3xl border bg-card p-5">
            <h2 className="text-lg font-black">Prudential framework configuration</h2>
            <p className="mt-2 text-sm text-muted-foreground">Enter only institution-approved or regulator-sourced thresholds. LoanHub does not assume Lesotho legal limits.</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <input value={prudentialFramework} onChange={(e) => setPrudentialFramework(e.target.value)} placeholder="Framework name" className="h-11 rounded-xl border bg-background px-3" />
              <input value={prudentialSource} onChange={(e) => setPrudentialSource(e.target.value)} placeholder="Source / circular / policy reference" className="h-11 rounded-xl border bg-background px-3" />
              <input value={prudentialCapital} onChange={(e) => setPrudentialCapital(e.target.value)} placeholder="Min capital / exposure %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={prudentialCurrentRatio} onChange={(e) => setPrudentialCurrentRatio(e.target.value)} placeholder="Min current ratio" className="h-11 rounded-xl border bg-background px-3" />
              <input value={prudentialGearing} onChange={(e) => setPrudentialGearing(e.target.value)} placeholder="Max gearing %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={prudentialSingleExposure} onChange={(e) => setPrudentialSingleExposure(e.target.value)} placeholder="Max single exposure / equity %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={prudentialRelatedExposure} onChange={(e) => setPrudentialRelatedExposure(e.target.value)} placeholder="Max related-party / equity %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={prudentialEclCoverage} onChange={(e) => setPrudentialEclCoverage(e.target.value)} placeholder="Min ECL coverage %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={prudentialLiquidity} onChange={(e) => setPrudentialLiquidity(e.target.value)} placeholder="Min liquidity buffer LSL" className="h-11 rounded-xl border bg-background px-3" />
            </div>
            <button type="button" disabled={busy || !prudentialFramework.trim()} onClick={() => void savePrudentialConfiguration()} className="mt-4 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Save prudential profile</button>
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">Related-party register</h2>
              <p className="mt-2 text-sm text-muted-foreground">Relationships are explicit and evidence-based; LoanHub never infers related parties automatically.</p>
              <input value={relatedBorrowerId} onChange={(e) => setRelatedBorrowerId(e.target.value)} placeholder="Borrower UUID" className="mt-4 h-11 w-full rounded-xl border bg-background px-3" />
              <input value={relatedType} onChange={(e) => setRelatedType(e.target.value)} placeholder="Relationship type" className="mt-3 h-11 w-full rounded-xl border bg-background px-3" />
              <textarea value={relatedDescription} onChange={(e) => setRelatedDescription(e.target.value)} placeholder="Relationship description and evidence basis" className="mt-3 min-h-24 w-full rounded-xl border bg-background p-3 text-sm" />
              <button type="button" disabled={busy || !relatedBorrowerId.trim() || !relatedType.trim() || !relatedDescription.trim()} onClick={() => void addRelatedParty()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Add related party</button>
              {prudential?.related_parties?.length ? <div className="mt-4 space-y-2">{prudential.related_parties.map((row) => <div key={row.id} className="rounded-xl border p-3 text-sm"><p className="font-black">{row.relationship_type ?? "Related party"}</p><p className="mt-1 text-xs text-muted-foreground">{row.borrower_id}</p><p className="mt-1">{row.relationship_description}</p></div>)}</div> : null}
            </section>

            <section className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">Regulatory filing readiness</h2>
              <input value={filingName} onChange={(e) => setFilingName(e.target.value)} placeholder="Filing / return name" className="mt-4 h-11 w-full rounded-xl border bg-background px-3" />
              <div className="mt-3 grid grid-cols-2 gap-3"><input type="date" value={filingPeriodEnd} onChange={(e) => setFilingPeriodEnd(e.target.value)} className="h-11 rounded-xl border bg-background px-3" /><input type="date" value={filingDueAt} onChange={(e) => setFilingDueAt(e.target.value)} className="h-11 rounded-xl border bg-background px-3" /></div>
              <button type="button" disabled={busy || !filingName.trim() || !filingPeriodEnd || !filingDueAt} onClick={() => void addPrudentialFiling()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Create filing readiness record</button>
              {prudential?.filing_readiness?.length ? <div className="mt-4 space-y-2">{prudential.filing_readiness.map((row) => <div key={row.id} className="rounded-xl border p-3 text-sm"><div className="flex items-center justify-between gap-2"><p className="font-black">{row.filing_name}</p><span className={row.overdue ? "text-destructive font-black" : "text-muted-foreground"}>{row.overdue ? "Overdue" : titleCase(row.status)}</span></div><p className="mt-1 text-xs text-muted-foreground">Due {row.due_at ? formatDateTime(row.due_at) : "—"} · Missing evidence {row.missing_evidence.length}</p></div>)}</div> : null}
            </section>
          </div>
        </div>
      ) : null}

      {tab === "board" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <section className="rounded-3xl border bg-card p-5 xl:col-span-2">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex items-center gap-2"><FileBarChart className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Board & executive governance pack</h2></div>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">Creates a governed evidence snapshot from finance, treasury, portfolio risk, audit controls, management priorities and accountability cases. The pack is stored in LoanHub’s GeneratedReport registry for auditability and historical comparison.</p>
              </div>
              <button type="button" disabled={busy} onClick={() => void createBoardPack()} className="inline-flex h-11 shrink-0 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground"><ChartNoAxesCombined className="h-4 w-4" /> Generate governance pack</button>
            </div>

            {boardPack ? <div className="mt-5 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="Enterprise risk" value={`${boardPack.metrics.command.enterprise_risk_score}/100`} detail={titleCase(boardPack.metrics.command.enterprise_risk_level)} />
                <Metric label="Critical priorities" value={String(boardPack.metrics.command.priority_counts.critical)} />
                <Metric label="Open actions" value={String(boardPack.metrics.accountability.open_count)} />
                <Metric label="Overdue actions" value={String(boardPack.metrics.accountability.overdue_count)} />
                <Metric label="Audit exceptions" value={String(boardPack.metrics.audit.control_fail_count)} />
                <Metric label="30-day closing cash" value={formatMoney(boardPack.metrics.treasury.projected_closing_cash)} />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <article className="rounded-2xl border p-4">
                  <div className="flex items-center justify-between gap-3"><h3 className="font-black">Board attention</h3><span className="text-xs text-muted-foreground">{boardPack.reference}</span></div>
                  <div className="mt-3 space-y-3">
                    {boardPack.metrics.board_attention.length ? boardPack.metrics.board_attention.map((item, index) => <div key={`${item.title}-${index}`} className="rounded-xl border p-3"><div className="flex items-center gap-2"><span className="font-black">{item.title}</span><span className={`rounded-full px-2 py-0.5 text-xs font-black ${item.severity === "critical" ? "bg-destructive/10 text-destructive" : "bg-amber-500/10 text-amber-700 dark:text-amber-300"}`}>{titleCase(item.severity)}</span></div><p className="mt-2 text-sm leading-6">{item.oversight_question}</p></div>) : <div className="rounded-xl border bg-emerald-500/5 p-3 text-sm font-bold">No board-attention thresholds are currently breached.</div>}
                  </div>
                </article>

                <article className="rounded-2xl border p-4">
                  <h3 className="font-black">Accountability position</h3>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <Metric label="Critical open" value={String(boardPack.metrics.accountability.critical_open_count)} />
                    <Metric label="Pending verification" value={String(boardPack.metrics.accountability.resolved_pending_verification_count)} />
                    <Metric label="Verified" value={String(boardPack.metrics.accountability.verified_count)} />
                    <Metric label="Overdue" value={String(boardPack.metrics.accountability.overdue_count)} />
                  </div>
                </article>
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <article className="rounded-2xl border p-4"><h3 className="font-black">Audit & control</h3><p className="mt-2 text-sm">Hash chain: <span className="font-black">{boardPack.metrics.audit.audit_integrity.chain_valid ? "Valid" : "Broken"}</span></p><p className="mt-1 text-sm">Controls passed: {boardPack.metrics.audit.control_pass_count}</p><p className="mt-1 text-sm">Controls failed: {boardPack.metrics.audit.control_fail_count}</p><p className="mt-1 text-sm">Flagged journals: {boardPack.metrics.audit.journal_review.flagged_count}</p><p className="mt-1 text-sm">Missing evidence: {boardPack.metrics.audit.journal_review.evidence_missing_count}</p></article>
                <article className="rounded-2xl border p-4"><h3 className="font-black">Treasury outlook</h3><p className="mt-2 text-sm">Expected collections: <span className="font-black">{formatMoney(boardPack.metrics.treasury.total_expected_collections)}</span></p><p className="mt-1 text-sm">Approved obligations: {formatMoney(boardPack.metrics.treasury.total_approved_obligations)}</p><p className="mt-1 text-sm">Minimum projected cash: {formatMoney(boardPack.metrics.treasury.minimum_projected_cash)}</p><p className="mt-1 text-sm">Breach days: {boardPack.metrics.treasury.breach_count}</p></article>
                <article className="rounded-2xl border p-4"><h3 className="font-black">Prior pack comparison</h3>{boardPack.metrics.prior_pack_summary ? <><p className="mt-2 text-sm">Previous: <span className="font-black">{boardPack.metrics.prior_pack_summary.reference}</span></p><p className="mt-1 text-sm">Prior risk score: {boardPack.metrics.prior_pack_summary.enterprise_risk_score ?? "—"}</p><p className="mt-1 text-sm">Prior critical priorities: {boardPack.metrics.prior_pack_summary.critical_priorities ?? "—"}</p><p className="mt-1 text-sm">Prior overdue actions: {boardPack.metrics.prior_pack_summary.overdue_actions ?? "—"}</p></> : <p className="mt-2 text-sm text-muted-foreground">No previous governance pack exists yet.</p>}</article>
              </div>

              {boardPack.metrics.opportunities.length ? <article className="rounded-2xl border p-4"><h3 className="font-black">Evidence-backed opportunities</h3><div className="mt-3 grid gap-3 md:grid-cols-2">{boardPack.metrics.opportunities.map((item) => <div key={item.code} className="rounded-xl border p-3"><p className="font-black">{item.title}</p><p className="mt-2 text-sm leading-6 text-muted-foreground">{item.management_option}</p></div>)}</div></article> : null}
              <p className="rounded-2xl border bg-muted/30 p-4 text-xs leading-5 text-muted-foreground">{boardPack.metrics.governance_notice}</p>
            </div> : null}

            {boardPackHistory.length ? <div className="mt-6"><h3 className="font-black">Governance pack history</h3><div className="mt-3 space-y-2">{boardPackHistory.slice(0, 10).map((pack) => <button key={pack.id} type="button" onClick={() => setBoardPack(pack)} className="flex w-full items-center justify-between rounded-xl border p-3 text-left hover:bg-muted/40"><div><p className="font-black">{pack.title}</p><p className="text-xs text-muted-foreground">{pack.reference} · {formatDateTime(pack.generated_at)}</p></div><div className="text-right text-xs"><p>Risk {pack.metrics.command.enterprise_risk_score}/100</p><p>{pack.metrics.accountability.overdue_count} overdue</p></div></button>)}</div></div> : null}
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
