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
  getALMIntelligence,
  createALMFundingFacility,
  runALMStressTest,
  generateALMEvidencePack,
  getInterestRateRiskIntelligence,
  saveLoanRateProfile,
  runInterestRateRiskStress,
  generateInterestRateRiskEvidencePack,
  getFTPProfitability,
  saveFTPPolicy,
  runFTPScenario,
  generateFTPEvidencePack,
  calculateMinimumViableRate,
  generatePricingOptimizationEvidencePack,
  optimizeCreditDealStructures,
  generateDealStructuringEvidencePack,
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
  type ALMIntelligence,
  type InterestRateRiskIntelligence,
  type FTPProfitabilityIntelligence,
  type PricingOptimizationResult,
  type DealStructuringResult,
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
  ["alm", "ALM", ChartNoAxesCombined],
  ["rate-risk", "Rate Risk", Gauge],
  ["ftp", "FTP & Profit", Calculator],
  ["pricing-intel", "Pricing Intel", Calculator],
  ["deal-structuring", "Deal Structuring", Scale],
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
  const [alm, setAlm] = useState<ALMIntelligence | null>(null);
  const [rateRisk, setRateRisk] = useState<InterestRateRiskIntelligence | null>(null);
  const [ftp, setFtp] = useState<FTPProfitabilityIntelligence | null>(null);
  const [pricingIntel, setPricingIntel] = useState<PricingOptimizationResult | null>(null);
  const [dealStructuring, setDealStructuring] = useState<DealStructuringResult | null>(null);
  const [dealBorrowerId, setDealBorrowerId] = useState("");
  const [dealMinPrincipal, setDealMinPrincipal] = useState("5000");
  const [dealMaxPrincipal, setDealMaxPrincipal] = useState("20000");
  const [dealPrincipalStep, setDealPrincipalStep] = useState("2500");
  const [dealTerms, setDealTerms] = useState("3,6,9,12");
  const [dealFeePercent, setDealFeePercent] = useState("0");
  const [dealMethod, setDealMethod] = useState("micro_loan");
  const [dealExpectedLoss, setDealExpectedLoss] = useState("");
  const [dealTargetMargin, setDealTargetMargin] = useState("");
  const [dealLiquidityBuffer, setDealLiquidityBuffer] = useState("");
  const [pricingIntelPrincipal, setPricingIntelPrincipal] = useState("10000");
  const [pricingIntelTerm, setPricingIntelTerm] = useState("6");
  const [pricingIntelFee, setPricingIntelFee] = useState("0");
  const [pricingIntelMethod, setPricingIntelMethod] = useState("micro_loan");
  const [pricingIntelProposedRate, setPricingIntelProposedRate] = useState("10");
  const [pricingIntelExpectedLoss, setPricingIntelExpectedLoss] = useState("");
  const [pricingIntelTargetMargin, setPricingIntelTargetMargin] = useState("");
  const [ftpOperatingCost, setFtpOperatingCost] = useState("2");
  const [ftpCapitalAllocation, setFtpCapitalAllocation] = useState("15");
  const [ftpHurdleRate, setFtpHurdleRate] = useState("18");
  const [ftpMinimumMargin, setFtpMinimumMargin] = useState("0");
  const [ftpSource, setFtpSource] = useState("");
  const [ftpFundingShift, setFtpFundingShift] = useState("200");
  const [ftpEclMultiplier, setFtpEclMultiplier] = useState("1.25");
  const [ftpOperatingMultiplier, setFtpOperatingMultiplier] = useState("1.10");
  const [rateLoanId, setRateLoanId] = useState("");
  const [rateType, setRateType] = useState<"fixed" | "variable">("fixed");
  const [rateNextRepricing, setRateNextRepricing] = useState("");
  const [rateReference, setRateReference] = useState("");
  const [rateSpread, setRateSpread] = useState("");
  const [rateShockBps, setRateShockBps] = useState("200");
  const [rateAssetShockBps, setRateAssetShockBps] = useState("");
  const [rateFundingShockBps, setRateFundingShockBps] = useState("");
  const [rateHorizonDays, setRateHorizonDays] = useState("365");
  const [almLender, setAlmLender] = useState("");
  const [almOutstanding, setAlmOutstanding] = useState("");
  const [almMaturity, setAlmMaturity] = useState("");
  const [almRate, setAlmRate] = useState("");
  const [almCollectionRate, setAlmCollectionRate] = useState("75");
  const [almObligationRate, setAlmObligationRate] = useState("110");
  const [almRolloverRate, setAlmRolloverRate] = useState("50");
  const [almUnexpectedOutflow, setAlmUnexpectedOutflow] = useState("0");
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
    if (nextTab === "alm") {
      try {
        setAlm(await getALMIntelligence());
      } catch (nextError) {
        setError(errorMessage(nextError));
      }
    }
    if (nextTab === "rate-risk") {
      try {
        setRateRisk(await getInterestRateRiskIntelligence());
      } catch (nextError) {
        setError(errorMessage(nextError));
      }
    }
    if (nextTab === "ftp") {
      try {
        setFtp(await getFTPProfitability());
      } catch (nextError) {
        setError(errorMessage(nextError));
      }
    }
    if (nextTab === "pricing-intel") {
      setPricingIntel(null);
    }
    if (nextTab === "deal-structuring") {
      setDealStructuring(null);
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

  async function refreshRateRisk() {
    setBusy(true);
    setError(null);
    try {
      setRateRisk(await getInterestRateRiskIntelligence());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function saveRateProfile() {
    if (!rateLoanId.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await saveLoanRateProfile({
        loan_id: rateLoanId.trim(),
        rate_type: rateType,
        next_repricing_date: rateType === "variable" && rateNextRepricing ? new Date(`${rateNextRepricing}T17:00:00`).toISOString() : null,
        reference_rate_name: rateReference.trim() || null,
        spread_percent: rateSpread.trim() ? Number(rateSpread) : null,
      });
      setRateLoanId("");
      setRateNextRepricing("");
      setRateReference("");
      setRateSpread("");
      setRateRisk(await getInterestRateRiskIntelligence());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function runRateStress() {
    setBusy(true);
    setError(null);
    try {
      setRateRisk(await runInterestRateRiskStress({
        parallel_shock_bps: Number(rateShockBps || 0),
        asset_shock_bps: rateAssetShockBps.trim() ? Number(rateAssetShockBps) : null,
        funding_shock_bps: rateFundingShockBps.trim() ? Number(rateFundingShockBps) : null,
        horizon_days: Number(rateHorizonDays || 365),
      }));
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function exportRateRiskPack() {
    setBusy(true);
    setError(null);
    try {
      const result = await generateInterestRateRiskEvidencePack({
        parallel_shock_bps: Number(rateShockBps || 0),
        asset_shock_bps: rateAssetShockBps.trim() ? Number(rateAssetShockBps) : null,
        funding_shock_bps: rateFundingShockBps.trim() ? Number(rateFundingShockBps) : null,
        horizon_days: Number(rateHorizonDays || 365),
      });
      setRateRisk(result.metrics);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  function dealStructuringPayload() {
    return {
      borrower_id: dealBorrowerId.trim(),
      minimum_principal: Number(dealMinPrincipal || 0),
      maximum_principal: Number(dealMaxPrincipal || 0),
      principal_step: Number(dealPrincipalStep || 0),
      term_options: dealTerms.split(",").map((item) => Number(item.trim())).filter((item) => Number.isFinite(item) && item > 0),
      processing_fee_percent: Number(dealFeePercent || 0),
      interest_method: dealMethod,
      expected_loss_percent: dealExpectedLoss.trim() ? Number(dealExpectedLoss) : null,
      target_margin_percent: dealTargetMargin.trim() ? Number(dealTargetMargin) : null,
      maximum_search_rate_percent: 500,
      minimum_liquidity_buffer: dealLiquidityBuffer.trim() ? Number(dealLiquidityBuffer) : null,
    };
  }

  async function runDealStructuring() {
    setBusy(true);
    setError(null);
    try {
      setDealStructuring(await optimizeCreditDealStructures(dealStructuringPayload()));
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function exportDealStructuringPack() {
    setBusy(true);
    setError(null);
    try {
      const result = await generateDealStructuringEvidencePack({
        title: "Credit approval economics & deal structuring assessment",
        ...dealStructuringPayload(),
      });
      setDealStructuring(result.metrics);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  function pricingIntelPayload() {
    return {
      principal: Number(pricingIntelPrincipal || 0),
      term_months: Number(pricingIntelTerm || 0),
      processing_fee: Number(pricingIntelFee || 0),
      interest_method: pricingIntelMethod,
      proposed_rate_percent: pricingIntelProposedRate.trim() ? Number(pricingIntelProposedRate) : null,
      expected_loss_percent: pricingIntelExpectedLoss.trim() ? Number(pricingIntelExpectedLoss) : null,
      target_margin_percent: pricingIntelTargetMargin.trim() ? Number(pricingIntelTargetMargin) : null,
      maximum_search_rate_percent: 500,
    };
  }

  async function runPricingOptimization() {
    setBusy(true);
    setError(null);
    try {
      setPricingIntel(await calculateMinimumViableRate(pricingIntelPayload()));
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function exportPricingOptimizationPack() {
    setBusy(true);
    setError(null);
    try {
      const result = await generatePricingOptimizationEvidencePack({
        title: "Minimum viable lending rate assessment",
        ...pricingIntelPayload(),
      });
      setPricingIntel(result.metrics);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function refreshFtp() {
    setBusy(true);
    setError(null);
    try {
      setFtp(await getFTPProfitability());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function saveFtpConfiguration() {
    setBusy(true);
    setError(null);
    try {
      await saveFTPPolicy({
        policy_name: "LoanHub FTP & risk-adjusted profitability",
        operating_cost_percent_of_exposure: Number(ftpOperatingCost || 0),
        capital_allocation_percent_of_exposure: Number(ftpCapitalAllocation || 0),
        capital_hurdle_rate_percent: Number(ftpHurdleRate || 0),
        minimum_risk_adjusted_margin_percent: Number(ftpMinimumMargin || 0),
        source_reference: ftpSource.trim() || null,
      });
      setFtp(await getFTPProfitability());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function runFtpStress() {
    setBusy(true);
    setError(null);
    try {
      setFtp(await runFTPScenario({
        funding_cost_shift_bps: Number(ftpFundingShift || 0),
        ecl_multiplier: Number(ftpEclMultiplier || 0),
        operating_cost_multiplier: Number(ftpOperatingMultiplier || 0),
      }));
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function exportFtpPack() {
    setBusy(true);
    setError(null);
    try {
      const result = await generateFTPEvidencePack({
        funding_cost_shift_bps: Number(ftpFundingShift || 0),
        ecl_multiplier: Number(ftpEclMultiplier || 0),
        operating_cost_multiplier: Number(ftpOperatingMultiplier || 0),
      });
      setFtp(result.metrics);
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function refreshAlm() {
    setBusy(true);
    setError(null);
    try {
      setAlm(await getALMIntelligence());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function addAlmFundingFacility() {
    if (!almLender.trim() || Number(almOutstanding) <= 0 || !almMaturity) return;
    setBusy(true);
    setError(null);
    try {
      await createALMFundingFacility({
        lender_name: almLender.trim(),
        outstanding_amount: Number(almOutstanding),
        maturity_date: new Date(`${almMaturity}T17:00:00`).toISOString(),
        interest_rate_percent: almRate.trim() ? Number(almRate) : null,
      });
      setAlmLender("");
      setAlmOutstanding("");
      setAlmMaturity("");
      setAlmRate("");
      setAlm(await getALMIntelligence());
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function runAlmStress() {
    setBusy(true);
    setError(null);
    try {
      setAlm(await runALMStressTest({
        collection_rate_percent: Number(almCollectionRate || 0),
        obligation_rate_percent: Number(almObligationRate || 0),
        funding_rollover_percent: Number(almRolloverRate || 0),
        unexpected_outflow: Number(almUnexpectedOutflow || 0),
      }));
    } catch (nextError) {
      setError(errorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function exportAlmPack() {
    setBusy(true);
    setError(null);
    try {
      const result = await generateALMEvidencePack({
        collection_rate_percent: Number(almCollectionRate || 0),
        obligation_rate_percent: Number(almObligationRate || 0),
        funding_rollover_percent: Number(almRolloverRate || 0),
        unexpected_outflow: Number(almUnexpectedOutflow || 0),
      });
      setAlm(result.metrics);
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

      {tab === "rate-risk" ? (
        <div className="space-y-6">
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex items-center gap-2"><Gauge className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Interest Rate Risk & Repricing Intelligence</h2></div>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">Maps asset and funding repricing dates, separates fixed and variable balances, measures repricing gaps and estimates earnings-at-risk style changes in net interest income under basis-point shocks.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy} onClick={() => void refreshRateRisk()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Refresh rate risk</button>
                <button type="button" disabled={busy} onClick={() => void exportRateRiskPack()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Generate rate-risk evidence pack</button>
              </div>
            </div>

            {rateRisk ? <>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="Asset balance" value={formatMoney(rateRisk.summary.asset_balance)} />
                <Metric label="Variable assets" value={formatMoney(rateRisk.summary.variable_asset_balance)} />
                <Metric label="Funding balance" value={formatMoney(rateRisk.summary.funding_balance)} />
                <Metric label="Variable funding" value={formatMoney(rateRisk.summary.variable_funding_balance)} />
                <Metric label="Rate spread" value={rateRisk.summary.baseline_rate_spread_percent == null ? "—" : `${rateRisk.summary.baseline_rate_spread_percent.toFixed(3)}%`} />
                <Metric label="Δ net interest income" value={formatMoney(rateRisk.summary.estimated_delta_net_interest_income)} />
              </div>

              <div className="mt-5 overflow-x-auto rounded-2xl border">
                <table className="min-w-full text-sm">
                  <thead className="bg-muted/40 text-left"><tr><th className="p-3">Bucket</th><th className="p-3 text-right">Assets</th><th className="p-3 text-right">Funding</th><th className="p-3 text-right">Gap</th><th className="p-3 text-right">Cumulative</th><th className="p-3 text-right">Variable asset</th><th className="p-3 text-right">Variable funding</th><th className="p-3 text-right">Variable gap</th></tr></thead>
                  <tbody>{rateRisk.repricing_ladder.map((row) => <tr key={row.bucket} className="border-t"><td className="p-3 font-black">{titleCase(row.bucket)}</td><td className="p-3 text-right">{formatMoney(row.asset_balance)}</td><td className="p-3 text-right">{formatMoney(row.funding_balance)}</td><td className="p-3 text-right">{formatMoney(row.repricing_gap)}</td><td className="p-3 text-right">{formatMoney(row.cumulative_gap)}</td><td className="p-3 text-right">{formatMoney(row.variable_asset_balance)}</td><td className="p-3 text-right">{formatMoney(row.variable_funding_balance)}</td><td className="p-3 text-right font-black">{formatMoney(row.variable_repricing_gap)}</td></tr>)}</tbody>
                </table>
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <article className="rounded-2xl border p-4">
                  <h3 className="font-black">Rate-risk flags</h3>
                  <div className="mt-3 space-y-2">{Object.entries(rateRisk.risk_flags).map(([key, active]) => <div key={key} className="flex items-center justify-between rounded-xl border p-3 text-sm"><span>{titleCase(key)}</span><span className={active ? "font-black text-destructive" : "font-black text-emerald-700 dark:text-emerald-300"}>{active ? "Review" : "Clear"}</span></div>)}</div>
                </article>
                <article className="rounded-2xl border p-4">
                  <h3 className="font-black">Shock summary</h3>
                  <p className="mt-3 text-sm">Asset shock: <span className="font-black">{rateRisk.summary.asset_shock_bps} bps</span></p>
                  <p className="mt-1 text-sm">Funding shock: <span className="font-black">{rateRisk.summary.funding_shock_bps} bps</span></p>
                  <p className="mt-1 text-sm">Δ interest income: <span className="font-black">{formatMoney(rateRisk.summary.estimated_delta_interest_income)}</span></p>
                  <p className="mt-1 text-sm">Δ interest expense: <span className="font-black">{formatMoney(rateRisk.summary.estimated_delta_interest_expense)}</span></p>
                  <p className="mt-1 text-sm">Δ NII: <span className="font-black">{formatMoney(rateRisk.summary.estimated_delta_net_interest_income)}</span></p>
                </article>
              </div>
              <p className="mt-4 rounded-xl border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">{rateRisk.policy_note}</p>
            </> : null}
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">Loan repricing register</h2>
              <p className="mt-2 text-sm text-muted-foreground">Loans without an explicit variable-rate profile remain fixed-to-maturity. Variable loans require an explicit next repricing date.</p>
              <input value={rateLoanId} onChange={(e) => setRateLoanId(e.target.value)} placeholder="Loan UUID" className="mt-4 h-11 w-full rounded-xl border bg-background px-3" />
              <select value={rateType} onChange={(e) => setRateType(e.target.value as "fixed" | "variable")} className="mt-3 h-11 w-full rounded-xl border bg-background px-3"><option value="fixed">Fixed</option><option value="variable">Variable</option></select>
              {rateType === "variable" ? <input type="date" value={rateNextRepricing} onChange={(e) => setRateNextRepricing(e.target.value)} className="mt-3 h-11 w-full rounded-xl border bg-background px-3" /> : null}
              <input value={rateReference} onChange={(e) => setRateReference(e.target.value)} placeholder="Reference rate name (optional)" className="mt-3 h-11 w-full rounded-xl border bg-background px-3" />
              <input value={rateSpread} onChange={(e) => setRateSpread(e.target.value)} placeholder="Spread % (optional)" className="mt-3 h-11 w-full rounded-xl border bg-background px-3" />
              <button type="button" disabled={busy || !rateLoanId.trim() || (rateType === "variable" && !rateNextRepricing)} onClick={() => void saveRateProfile()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Save loan rate profile</button>
              {rateRisk?.loan_profiles?.length ? <div className="mt-4 max-h-96 space-y-2 overflow-auto">{rateRisk.loan_profiles.slice(0, 50).map((row) => <div key={row.loan_id} className="rounded-xl border p-3 text-sm"><div className="flex items-center justify-between gap-2"><p className="font-black">{row.loan_reference}</p><span>{titleCase(row.rate_type)}</span></div><p className="mt-1 text-xs text-muted-foreground">{formatMoney(row.balance)} · {row.contractual_rate_percent.toFixed(3)}% · reprices {row.repricing_date}</p></div>)}</div> : null}
            </section>

            <section className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">Rate-shock assumptions</h2>
              <p className="mt-2 text-sm text-muted-foreground">Parallel shock applies to both sides unless separate asset or funding shocks are supplied.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <input value={rateShockBps} onChange={(e) => setRateShockBps(e.target.value)} placeholder="Parallel shock bps" className="h-11 rounded-xl border bg-background px-3" />
                <input value={rateHorizonDays} onChange={(e) => setRateHorizonDays(e.target.value)} placeholder="Horizon days" className="h-11 rounded-xl border bg-background px-3" />
                <input value={rateAssetShockBps} onChange={(e) => setRateAssetShockBps(e.target.value)} placeholder="Asset shock bps (optional)" className="h-11 rounded-xl border bg-background px-3" />
                <input value={rateFundingShockBps} onChange={(e) => setRateFundingShockBps(e.target.value)} placeholder="Funding shock bps (optional)" className="h-11 rounded-xl border bg-background px-3" />
              </div>
              <button type="button" disabled={busy} onClick={() => void runRateStress()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Run rate shock</button>
            </section>
          </div>
        </div>
      ) : null}

      {tab === "alm" ? (
        <div className="space-y-6">
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex items-center gap-2"><ChartNoAxesCombined className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Asset & Liability Management Intelligence</h2></div>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">Builds a maturity ladder from scheduled loan inflows, approved treasury obligations and explicitly registered funding maturities. It highlights refinancing pressure, funding concentration, cumulative gaps and stress-adjusted funding requirements.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy} onClick={() => void refreshAlm()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Refresh ALM</button>
                <button type="button" disabled={busy} onClick={() => void exportAlmPack()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Generate ALM evidence pack</button>
              </div>
            </div>

            {alm ? <>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="Opening cash" value={formatMoney(alm.opening_available_cash)} />
                <Metric label="Funding outstanding" value={formatMoney(alm.funding.total_outstanding)} />
                <Metric label="30-day funding due" value={formatMoney(alm.funding.due_within_30_days)} />
                <Metric label="Max funding requirement" value={formatMoney(alm.maximum_funding_requirement)} />
                <Metric label="Top funder share" value={`${alm.funding.top_funder_share_percent.toFixed(2)}%`} />
                <Metric label="Maturity gap" value={alm.duration_style_maturity_gap_days == null ? "—" : `${alm.duration_style_maturity_gap_days.toFixed(0)} days`} />
              </div>

              <div className="mt-5 overflow-x-auto rounded-2xl border">
                <table className="min-w-full text-sm">
                  <thead className="bg-muted/40 text-left"><tr><th className="p-3">Bucket</th><th className="p-3 text-right">Asset inflows</th><th className="p-3 text-right">Scenario inflows</th><th className="p-3 text-right">Operating outflows</th><th className="p-3 text-right">Funding maturities</th><th className="p-3 text-right">Net gap</th><th className="p-3 text-right">Cumulative liquidity</th></tr></thead>
                  <tbody>{alm.liquidity_ladder.map((row) => <tr key={row.bucket} className="border-t"><td className="p-3 font-black">{titleCase(row.bucket)}</td><td className="p-3 text-right">{formatMoney(row.contractual_asset_inflows)}</td><td className="p-3 text-right">{formatMoney(row.scenario_asset_inflows)}</td><td className="p-3 text-right">{formatMoney(row.operating_outflows)}</td><td className="p-3 text-right">{formatMoney(row.funding_maturities)}</td><td className="p-3 text-right">{formatMoney(row.net_gap)}</td><td className="p-3 text-right font-black">{formatMoney(row.cumulative_liquidity)}</td></tr>)}</tbody>
                </table>
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <article className="rounded-2xl border p-4">
                  <h3 className="font-black">Funding concentration</h3>
                  <div className="mt-3 space-y-2">{alm.funding.concentration.length ? alm.funding.concentration.map((row) => <div key={row.lender_name} className="flex items-center justify-between rounded-xl border p-3 text-sm"><span className="font-bold">{row.lender_name}</span><span>{formatMoney(row.outstanding_amount)} · {row.share_percent.toFixed(2)}%</span></div>) : <p className="text-sm text-muted-foreground">No active funding facilities registered.</p>}</div>
                </article>
                <article className="rounded-2xl border p-4">
                  <h3 className="font-black">ALM risk flags</h3>
                  <div className="mt-3 space-y-2">{Object.entries(alm.risk_flags).map(([key, active]) => <div key={key} className="flex items-center justify-between rounded-xl border p-3 text-sm"><span>{titleCase(key)}</span><span className={active ? "font-black text-destructive" : "font-black text-emerald-700 dark:text-emerald-300"}>{active ? "Review" : "Clear"}</span></div>)}</div>
                </article>
              </div>
              <p className="mt-4 rounded-xl border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">{alm.policy_note}</p>
            </> : null}
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">Funding facility register</h2>
              <p className="mt-2 text-sm text-muted-foreground">Register contractual funding maturities explicitly so ALM does not guess maturity dates from the general ledger.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <input value={almLender} onChange={(e) => setAlmLender(e.target.value)} placeholder="Lender / funding source" className="h-11 rounded-xl border bg-background px-3" />
                <input value={almOutstanding} onChange={(e) => setAlmOutstanding(e.target.value)} placeholder="Outstanding amount" className="h-11 rounded-xl border bg-background px-3" />
                <input type="date" value={almMaturity} onChange={(e) => setAlmMaturity(e.target.value)} className="h-11 rounded-xl border bg-background px-3" />
                <input value={almRate} onChange={(e) => setAlmRate(e.target.value)} placeholder="Interest rate % (optional)" className="h-11 rounded-xl border bg-background px-3" />
              </div>
              <button type="button" disabled={busy || !almLender.trim() || Number(almOutstanding) <= 0 || !almMaturity} onClick={() => void addAlmFundingFacility()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Add funding facility</button>
              {alm?.funding.facilities?.length ? <div className="mt-4 space-y-2">{alm.funding.facilities.slice(0, 20).map((row) => <div key={row.id} className="rounded-xl border p-3 text-sm"><div className="flex items-center justify-between gap-2"><p className="font-black">{row.lender_name}</p><span>{formatMoney(row.outstanding_amount)}</span></div><p className="mt-1 text-xs text-muted-foreground">Matures {row.maturity_date} · {row.days_to_maturity} days · {row.reference}</p></div>)}</div> : null}
            </section>

            <section className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">ALM stress assumptions</h2>
              <p className="mt-2 text-sm text-muted-foreground">Test reduced collections, higher obligations, partial funding rollover and unexpected cash drains without changing live records.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <input value={almCollectionRate} onChange={(e) => setAlmCollectionRate(e.target.value)} placeholder="Collection rate %" className="h-11 rounded-xl border bg-background px-3" />
                <input value={almObligationRate} onChange={(e) => setAlmObligationRate(e.target.value)} placeholder="Obligation rate %" className="h-11 rounded-xl border bg-background px-3" />
                <input value={almRolloverRate} onChange={(e) => setAlmRolloverRate(e.target.value)} placeholder="Funding rollover %" className="h-11 rounded-xl border bg-background px-3" />
                <input value={almUnexpectedOutflow} onChange={(e) => setAlmUnexpectedOutflow(e.target.value)} placeholder="Unexpected outflow LSL" className="h-11 rounded-xl border bg-background px-3" />
              </div>
              <button type="button" disabled={busy} onClick={() => void runAlmStress()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Run ALM stress</button>
            </section>
          </div>
        </div>
      ) : null}

      {tab === "ftp" ? (
        <div className="space-y-6">
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex items-center gap-2"><Calculator className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Funds Transfer Pricing & Risk-Adjusted Profitability</h2></div>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">Combines contractual loan yield proxies, explicit funding costs, posted ECL, operating-cost assumptions and allocated-capital charges to show whether lending remains economically attractive after risk and funding.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy} onClick={() => void refreshFtp()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Refresh profitability</button>
                <button type="button" disabled={busy} onClick={() => void exportFtpPack()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Generate FTP evidence pack</button>
              </div>
            </div>

            {ftp ? <>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <Metric label="Exposure" value={formatMoney(ftp.summary.total_exposure)} />
                <Metric label="Risk-adjusted profit" value={formatMoney(ftp.summary.risk_adjusted_profit_proxy)} />
                <Metric label="Risk-adjusted margin" value={ftp.summary.risk_adjusted_margin_percent == null ? "—" : `${ftp.summary.risk_adjusted_margin_percent.toFixed(2)}%`} />
                <Metric label="Funding cost" value={ftp.funding.weighted_funding_cost_percent == null ? "—" : `${ftp.funding.weighted_funding_cost_percent.toFixed(2)}%`} detail={`${ftp.funding.funding_rate_coverage_percent.toFixed(1)}% funding-rate coverage`} />
                <Metric label="Below hurdle loans" value={String(ftp.summary.below_hurdle_loan_count)} />
                <Metric label="Not assessed" value={String(ftp.summary.not_assessed_loan_count)} />
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <article className="rounded-2xl border p-4">
                  <h3 className="font-black">Cost waterfall</h3>
                  <div className="mt-3 space-y-2 text-sm">
                    <div className="flex justify-between"><span>Gross revenue proxy</span><strong>{formatMoney(ftp.summary.gross_revenue_proxy)}</strong></div>
                    <div className="flex justify-between"><span>FTP funding charge</span><strong>{formatMoney(ftp.summary.ftp_funding_charge)}</strong></div>
                    <div className="flex justify-between"><span>ECL risk charge</span><strong>{formatMoney(ftp.summary.ecl_risk_charge)}</strong></div>
                    <div className="flex justify-between"><span>Operating-cost charge</span><strong>{formatMoney(ftp.summary.operating_cost_charge)}</strong></div>
                    <div className="flex justify-between"><span>Capital charge</span><strong>{formatMoney(ftp.summary.capital_charge)}</strong></div>
                    <div className="flex justify-between border-t pt-2"><span className="font-black">Risk-adjusted profit proxy</span><strong>{formatMoney(ftp.summary.risk_adjusted_profit_proxy)}</strong></div>
                  </div>
                </article>
                <article className="rounded-2xl border p-4">
                  <h3 className="font-black">Funding-rate completeness</h3>
                  <p className="mt-3 text-sm">Rated funding: <strong>{formatMoney(ftp.funding.rated_funding_amount)}</strong></p>
                  <p className="mt-1 text-sm">Total funding: <strong>{formatMoney(ftp.funding.total_funding_amount)}</strong></p>
                  <p className="mt-1 text-sm">Missing-rate exposure: <strong>{formatMoney(ftp.funding.missing_rate_amount)}</strong></p>
                  <p className="mt-1 text-sm">Latest posted ECL: <strong>{ftp.latest_posted_ecl_reference ?? "Unavailable"}</strong></p>
                </article>
              </div>

              <div className="mt-5 grid gap-4 xl:grid-cols-2">
                <article className="rounded-2xl border p-4"><h3 className="font-black">Branch profitability</h3><div className="mt-3 space-y-2">{ftp.by_branch.length ? ftp.by_branch.map((row) => <div key={row.key} className="flex items-center justify-between rounded-xl border p-3 text-sm"><div><p className="font-black">{row.label}</p><p className="text-xs text-muted-foreground">{row.loan_count} assessed loans · {formatMoney(row.exposure)} exposure</p></div><div className="text-right"><p className="font-black">{formatMoney(row.risk_adjusted_profit_proxy)}</p><p className="text-xs text-muted-foreground">{row.risk_adjusted_margin_percent?.toFixed(2) ?? "—"}%</p></div></div>) : <p className="text-sm text-muted-foreground">No assessed branch profitability yet.</p>}</div></article>
                <article className="rounded-2xl border p-4"><h3 className="font-black">Calculation-method profitability</h3><div className="mt-3 space-y-2">{ftp.by_calculation_method.length ? ftp.by_calculation_method.map((row) => <div key={row.key} className="flex items-center justify-between rounded-xl border p-3 text-sm"><div><p className="font-black">{titleCase(row.label)}</p><p className="text-xs text-muted-foreground">{row.loan_count} assessed loans · {formatMoney(row.exposure)} exposure</p></div><div className="text-right"><p className="font-black">{formatMoney(row.risk_adjusted_profit_proxy)}</p><p className="text-xs text-muted-foreground">{row.risk_adjusted_margin_percent?.toFixed(2) ?? "—"}%</p></div></div>) : <p className="text-sm text-muted-foreground">No assessed method profitability yet.</p>}</div></article>
              </div>

              <div className="mt-5 overflow-x-auto rounded-2xl border">
                <table className="min-w-full text-sm"><thead className="bg-muted/40 text-left"><tr><th className="p-3">Loan</th><th className="p-3">Branch</th><th className="p-3 text-right">Exposure</th><th className="p-3 text-right">Yield proxy</th><th className="p-3 text-right">Funding</th><th className="p-3 text-right">ECL</th><th className="p-3 text-right">Risk profit</th><th className="p-3 text-right">Margin</th><th className="p-3">Status</th></tr></thead><tbody>{ftp.loan_profitability.slice(0, 100).map((row) => <tr key={row.loan_id} className="border-t"><td className="p-3"><p className="font-black">{row.loan_reference}</p><p className="text-xs text-muted-foreground">{row.folio_number}</p></td><td className="p-3">{row.branch_name}</td><td className="p-3 text-right">{formatMoney(row.exposure)}</td><td className="p-3 text-right">{row.gross_contractual_yield_proxy_percent.toFixed(2)}%</td><td className="p-3 text-right">{row.ftp_funding_charge == null ? "—" : formatMoney(row.ftp_funding_charge)}</td><td className="p-3 text-right">{row.ecl_risk_charge == null ? "—" : formatMoney(row.ecl_risk_charge)}</td><td className="p-3 text-right">{row.risk_adjusted_profit_proxy == null ? "—" : formatMoney(row.risk_adjusted_profit_proxy)}</td><td className="p-3 text-right">{row.risk_adjusted_margin_percent == null ? "—" : `${row.risk_adjusted_margin_percent.toFixed(2)}%`}</td><td className="p-3 font-black">{titleCase(row.status)}</td></tr>)}</tbody></table>
              </div>
              <p className="mt-4 rounded-xl border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">{ftp.policy_note}</p>
            </> : null}
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">FTP profitability policy</h2>
              <p className="mt-2 text-sm text-muted-foreground">Configure management charges explicitly; these values are not accounting standards or prudential rules.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <input value={ftpOperatingCost} onChange={(e) => setFtpOperatingCost(e.target.value)} placeholder="Operating cost % of exposure" className="h-11 rounded-xl border bg-background px-3" />
                <input value={ftpCapitalAllocation} onChange={(e) => setFtpCapitalAllocation(e.target.value)} placeholder="Capital allocation % of exposure" className="h-11 rounded-xl border bg-background px-3" />
                <input value={ftpHurdleRate} onChange={(e) => setFtpHurdleRate(e.target.value)} placeholder="Capital hurdle rate %" className="h-11 rounded-xl border bg-background px-3" />
                <input value={ftpMinimumMargin} onChange={(e) => setFtpMinimumMargin(e.target.value)} placeholder="Minimum risk-adjusted margin %" className="h-11 rounded-xl border bg-background px-3" />
              </div>
              <input value={ftpSource} onChange={(e) => setFtpSource(e.target.value)} placeholder="Internal policy / board source reference" className="mt-3 h-11 w-full rounded-xl border bg-background px-3" />
              <button type="button" disabled={busy} onClick={() => void saveFtpConfiguration()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Save FTP policy</button>
            </section>
            <section className="rounded-3xl border bg-card p-5">
              <h2 className="text-lg font-black">Profitability stress scenario</h2>
              <p className="mt-2 text-sm text-muted-foreground">Test funding-cost increases, higher ECL and higher operating costs without changing contracts or accounting.</p>
              <div className="mt-4 grid gap-3">
                <input value={ftpFundingShift} onChange={(e) => setFtpFundingShift(e.target.value)} placeholder="Funding cost shift bps" className="h-11 rounded-xl border bg-background px-3" />
                <input value={ftpEclMultiplier} onChange={(e) => setFtpEclMultiplier(e.target.value)} placeholder="ECL multiplier" className="h-11 rounded-xl border bg-background px-3" />
                <input value={ftpOperatingMultiplier} onChange={(e) => setFtpOperatingMultiplier(e.target.value)} placeholder="Operating cost multiplier" className="h-11 rounded-xl border bg-background px-3" />
              </div>
              <button type="button" disabled={busy} onClick={() => void runFtpStress()} className="mt-3 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Run profitability stress</button>
            </section>
          </div>
        </div>
      ) : null}

      {tab === "pricing-intel" ? (
        <div className="space-y-6">
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex items-center gap-2"><Calculator className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Pricing Optimization & Minimum Viable Lending Rate</h2></div>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">Calculates the economic rate floor needed to cover explicit funding cost, expected credit loss, operating cost, capital hurdle and target margin. The solver uses LoanHub’s authoritative contractual interest engine for the selected pricing method.</p>
              </div>
              <button type="button" disabled={busy || !pricingIntel} onClick={() => void exportPricingOptimizationPack()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Generate pricing evidence pack</button>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <input value={pricingIntelPrincipal} onChange={(e) => setPricingIntelPrincipal(e.target.value)} placeholder="Principal" className="h-11 rounded-xl border bg-background px-3" />
              <input value={pricingIntelTerm} onChange={(e) => setPricingIntelTerm(e.target.value)} placeholder="Term months" className="h-11 rounded-xl border bg-background px-3" />
              <input value={pricingIntelFee} onChange={(e) => setPricingIntelFee(e.target.value)} placeholder="Processing fee" className="h-11 rounded-xl border bg-background px-3" />
              <select value={pricingIntelMethod} onChange={(e) => setPricingIntelMethod(e.target.value)} className="h-11 rounded-xl border bg-background px-3">
                <option value="micro_loan">LoanHub Micro Loan</option>
                <option value="simple_interest">Simple interest</option>
                <option value="flat_rate">Flat rate</option>
                <option value="compound_interest">Compound interest</option>
                <option value="reducing_balance">Reducing balance</option>
                <option value="daily_accrual_reducing">Daily accrual reducing</option>
              </select>
              <input value={pricingIntelProposedRate} onChange={(e) => setPricingIntelProposedRate(e.target.value)} placeholder="Proposed borrower rate %" className="h-11 rounded-xl border bg-background px-3" />
              <input value={pricingIntelExpectedLoss} onChange={(e) => setPricingIntelExpectedLoss(e.target.value)} placeholder="Expected loss % (optional)" className="h-11 rounded-xl border bg-background px-3" />
              <input value={pricingIntelTargetMargin} onChange={(e) => setPricingIntelTargetMargin(e.target.value)} placeholder="Target margin % (optional)" className="h-11 rounded-xl border bg-background px-3" />
              <button type="button" disabled={busy || Number(pricingIntelPrincipal) <= 0 || Number(pricingIntelTerm) <= 0} onClick={() => void runPricingOptimization()} className="h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Calculate minimum viable rate</button>
            </div>
          </section>

          {pricingIntel ? <section className="space-y-5 rounded-3xl border bg-card p-5">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="Minimum viable rate" value={pricingIntel.minimum_viable_rate_percent == null ? "—" : `${pricingIntel.minimum_viable_rate_percent.toFixed(4)}%`} detail={titleCase(pricingIntel.solver_status)} />
              <Metric label="Proposed rate" value={pricingIntel.inputs.proposed_rate_percent == null ? "—" : `${pricingIntel.inputs.proposed_rate_percent.toFixed(4)}%`} />
              <Metric label="Required gross yield" value={pricingIntel.cost_stack.required_gross_yield_proxy_percent == null ? "—" : `${pricingIntel.cost_stack.required_gross_yield_proxy_percent.toFixed(2)}%`} />
              <Metric label="Funding cost" value={pricingIntel.cost_stack.weighted_funding_cost_percent == null ? "—" : `${pricingIntel.cost_stack.weighted_funding_cost_percent.toFixed(2)}%`} />
              <Metric label="Expected loss" value={pricingIntel.cost_stack.expected_loss_percent_of_principal == null ? "—" : `${pricingIntel.cost_stack.expected_loss_percent_of_principal.toFixed(2)}%`} />
              <Metric label="Decision support" value={titleCase(pricingIntel.decision_support)} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <article className="rounded-2xl border p-4">
                <h3 className="font-black">Economic floor components</h3>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between"><span>Funding cost</span><strong>{pricingIntel.cost_stack.weighted_funding_cost_percent?.toFixed(2) ?? "—"}%</strong></div>
                  <div className="flex justify-between"><span>Operating cost</span><strong>{pricingIntel.cost_stack.operating_cost_percent.toFixed(2)}%</strong></div>
                  <div className="flex justify-between"><span>Annualized capital charge</span><strong>{pricingIntel.cost_stack.annualized_capital_charge_percent.toFixed(2)}%</strong></div>
                  <div className="flex justify-between"><span>Annualized expected-loss charge</span><strong>{pricingIntel.cost_stack.annualized_expected_loss_charge_percent?.toFixed(2) ?? "—"}%</strong></div>
                  <div className="flex justify-between"><span>Target margin</span><strong>{pricingIntel.cost_stack.target_margin_percent.toFixed(2)}%</strong></div>
                  <div className="flex justify-between"><span>Fee yield contribution</span><strong>{pricingIntel.cost_stack.annualized_fee_yield_proxy_percent.toFixed(2)}%</strong></div>
                  <div className="flex justify-between border-t pt-2"><span className="font-black">Required interest yield</span><strong>{pricingIntel.cost_stack.required_interest_yield_proxy_percent?.toFixed(2) ?? "—"}%</strong></div>
                </div>
              </article>
              <article className="rounded-2xl border p-4">
                <h3 className="font-black">Evidence & assumptions</h3>
                <p className="mt-3 text-sm">Funding-rate coverage: <strong>{pricingIntel.evidence.funding.funding_rate_coverage_percent.toFixed(1)}%</strong></p>
                <p className="mt-1 text-sm">Expected-loss source: <strong>{titleCase(pricingIntel.evidence.expected_loss.source)}</strong></p>
                <p className="mt-1 text-sm">Expected-loss policy: <strong>{pricingIntel.evidence.expected_loss.policy_name ?? "Explicit input / unavailable"}</strong></p>
                <p className="mt-1 text-sm">FTP policy: <strong>{pricingIntel.evidence.ftp_policy.policy_name}</strong></p>
                {pricingIntel.missing_evidence.length ? <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"><strong>Missing evidence:</strong> {pricingIntel.missing_evidence.map(titleCase).join(", ")}</div> : null}
              </article>
            </div>

            {pricingIntel.proposed_pricing ? <article className={`rounded-2xl border p-4 ${pricingIntel.proposed_pricing.status === "below_minimum" ? "border-destructive/40" : ""}`}>
              <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-black">Proposed pricing comparison</h3><p className="mt-1 text-sm text-muted-foreground">Economic floor comparison only; borrower affordability and legal pricing controls remain separate.</p></div><span className={`rounded-full px-3 py-1 text-xs font-black ${pricingIntel.proposed_pricing.status === "below_minimum" ? "bg-destructive/10 text-destructive" : pricingIntel.proposed_pricing.status === "meets_minimum" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>{titleCase(pricingIntel.proposed_pricing.status)}</span></div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <Metric label="Monthly installment" value={formatMoney(pricingIntel.proposed_pricing.monthly_installment)} />
                <Metric label="Total repayable" value={formatMoney(pricingIntel.proposed_pricing.total_repayable)} />
                <Metric label="Gross yield proxy" value={`${pricingIntel.proposed_pricing.gross_contractual_yield_proxy_percent.toFixed(2)}%`} />
                <Metric label="Risk-adjusted margin" value={pricingIntel.proposed_pricing.risk_adjusted_margin_proxy_percent == null ? "—" : `${pricingIntel.proposed_pricing.risk_adjusted_margin_proxy_percent.toFixed(2)}%`} />
                <Metric label="Rate gap" value={pricingIntel.proposed_pricing.minimum_rate_gap_bps == null ? "—" : `${pricingIntel.proposed_pricing.minimum_rate_gap_bps.toFixed(0)} bps`} />
              </div>
            </article> : null}

            {pricingIntel.minimum_viable_terms ? <article className="rounded-2xl border p-4"><h3 className="font-black">Minimum-rate contractual illustration</h3><div className="mt-3 grid gap-3 sm:grid-cols-3"><Metric label="Monthly installment" value={formatMoney(pricingIntel.minimum_viable_terms.monthly_installment)} /><Metric label="Total repayable" value={formatMoney(pricingIntel.minimum_viable_terms.total_repayable)} /><Metric label="Gross yield proxy" value={`${pricingIntel.minimum_viable_terms.gross_contractual_yield_proxy_percent.toFixed(2)}%`} /></div></article> : null}
            <p className="rounded-xl border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">{pricingIntel.policy_note}</p>
          </section> : null}
        </div>
      ) : null}

      {tab === "deal-structuring" ? (
        <div className="space-y-6">
          <section className="rounded-3xl border bg-card p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex items-center gap-2"><Scale className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Credit Approval Economics & Deal Structuring Intelligence</h2></div>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">Searches principal and term combinations, solves the minimum viable rate, then tests affordability, liquidity and configured concentration limits. It recommends structures for human review; it never approves the borrower.</p>
              </div>
              <button type="button" disabled={busy || !dealStructuring} onClick={() => void exportDealStructuringPack()} className="h-11 rounded-xl border bg-background px-4 text-sm font-black">Generate deal evidence pack</button>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <input value={dealBorrowerId} onChange={(e) => setDealBorrowerId(e.target.value)} placeholder="Borrower UUID" className="h-11 rounded-xl border bg-background px-3" />
              <input value={dealMinPrincipal} onChange={(e) => setDealMinPrincipal(e.target.value)} placeholder="Minimum principal" className="h-11 rounded-xl border bg-background px-3" />
              <input value={dealMaxPrincipal} onChange={(e) => setDealMaxPrincipal(e.target.value)} placeholder="Maximum principal" className="h-11 rounded-xl border bg-background px-3" />
              <input value={dealPrincipalStep} onChange={(e) => setDealPrincipalStep(e.target.value)} placeholder="Principal step" className="h-11 rounded-xl border bg-background px-3" />
              <input value={dealTerms} onChange={(e) => setDealTerms(e.target.value)} placeholder="Terms: 3,6,9,12" className="h-11 rounded-xl border bg-background px-3" />
              <input value={dealFeePercent} onChange={(e) => setDealFeePercent(e.target.value)} placeholder="Fee % of principal" className="h-11 rounded-xl border bg-background px-3" />
              <select value={dealMethod} onChange={(e) => setDealMethod(e.target.value)} className="h-11 rounded-xl border bg-background px-3">
                <option value="micro_loan">LoanHub Micro Loan</option>
                <option value="simple_interest">Simple interest</option>
                <option value="flat_rate">Flat rate</option>
                <option value="compound_interest">Compound interest</option>
                <option value="reducing_balance">Reducing balance</option>
                <option value="daily_accrual_reducing">Daily accrual reducing</option>
              </select>
              <input value={dealExpectedLoss} onChange={(e) => setDealExpectedLoss(e.target.value)} placeholder="Expected loss % (optional)" className="h-11 rounded-xl border bg-background px-3" />
              <input value={dealTargetMargin} onChange={(e) => setDealTargetMargin(e.target.value)} placeholder="Target margin % (optional)" className="h-11 rounded-xl border bg-background px-3" />
              <input value={dealLiquidityBuffer} onChange={(e) => setDealLiquidityBuffer(e.target.value)} placeholder="Liquidity buffer LSL (optional)" className="h-11 rounded-xl border bg-background px-3" />
            </div>
            <button type="button" disabled={busy || !dealBorrowerId.trim() || Number(dealMinPrincipal) <= 0 || Number(dealMaxPrincipal) <= 0 || Number(dealPrincipalStep) <= 0} onClick={() => void runDealStructuring()} className="mt-4 h-11 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground">Find viable deal structures</button>
          </section>

          {dealStructuring ? <section className="space-y-5 rounded-3xl border bg-card p-5">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="Candidates tested" value={String(dealStructuring.search.candidate_count)} />
              <Metric label="Viable structures" value={String(dealStructuring.viable_structure_count)} />
              <Metric label="Fully viable" value={String(dealStructuring.fully_viable_structure_count)} />
              <Metric label="Existing exposure" value={formatMoney(dealStructuring.portfolio_constraints.existing_borrower_exposure)} />
              <Metric label="30-day min cash" value={formatMoney(dealStructuring.portfolio_constraints.baseline_30d_minimum_cash)} />
              <Metric label="Decision support" value={titleCase(dealStructuring.decision_support)} />
            </div>

            {dealStructuring.best_structure ? <article className="rounded-2xl border bg-emerald-500/5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-black uppercase text-muted-foreground">Best available structure</p><h3 className="mt-1 text-xl font-black">{formatMoney(dealStructuring.best_structure.principal)} over {dealStructuring.best_structure.term_months} months</h3></div><span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-black text-emerald-700 dark:text-emerald-300">{titleCase(dealStructuring.best_structure.status)}</span></div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <Metric label="Minimum rate" value={dealStructuring.best_structure.minimum_viable_rate_percent == null ? "—" : `${dealStructuring.best_structure.minimum_viable_rate_percent.toFixed(4)}%`} />
                <Metric label="Installment" value={dealStructuring.best_structure.monthly_installment == null ? "—" : formatMoney(dealStructuring.best_structure.monthly_installment)} />
                <Metric label="Affordability headroom" value={dealStructuring.best_structure.affordability.headroom == null ? "—" : formatMoney(dealStructuring.best_structure.affordability.headroom)} />
                <Metric label="Post-deal 30d cash" value={formatMoney(dealStructuring.best_structure.liquidity.post_disbursement_30d_minimum_cash_proxy)} />
                <Metric label="Exposure / equity" value={dealStructuring.best_structure.concentration.post_deal_exposure_percent_of_equity == null ? "—" : `${dealStructuring.best_structure.concentration.post_deal_exposure_percent_of_equity.toFixed(2)}%`} />
              </div>
            </article> : <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">No candidate satisfied the currently assessable economic, affordability and liquidity constraints.</div>}

            <div className="overflow-x-auto rounded-2xl border">
              <table className="min-w-full text-sm"><thead className="bg-muted/40 text-left"><tr><th className="p-3">Principal</th><th className="p-3">Term</th><th className="p-3 text-right">Min rate</th><th className="p-3 text-right">Installment</th><th className="p-3">Affordability</th><th className="p-3">Liquidity</th><th className="p-3">Concentration</th><th className="p-3">Status</th></tr></thead><tbody>{dealStructuring.options.slice(0, 100).map((row, index) => <tr key={`${row.principal}-${row.term_months}-${index}`} className="border-t"><td className="p-3 font-black">{formatMoney(row.principal)}</td><td className="p-3">{row.term_months} months</td><td className="p-3 text-right">{row.minimum_viable_rate_percent == null ? "—" : `${row.minimum_viable_rate_percent.toFixed(4)}%`}</td><td className="p-3 text-right">{row.monthly_installment == null ? "—" : formatMoney(row.monthly_installment)}</td><td className="p-3">{titleCase(row.affordability.status)}</td><td className="p-3">{titleCase(row.liquidity.status)}</td><td className="p-3">{titleCase(row.concentration.status)}</td><td className="p-3 font-black">{titleCase(row.status)}</td></tr>)}</tbody></table>
            </div>
            <p className="rounded-xl border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">{dealStructuring.policy_note}</p>
          </section> : null}
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
