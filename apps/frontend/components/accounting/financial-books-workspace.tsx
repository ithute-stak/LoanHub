"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { BookOpenCheck, CalendarCheck2, Download, FileSpreadsheet, RefreshCcw, Scale, Upload } from "lucide-react";

import { approveFinancialPlan, approveTreasuryCommitment, cancelYearEndClosingDraft, createFinancialPlan, createMonthEndAdjustmentDraft, createOpeningBalanceMigration, createRollingForecast, createTreasuryCommitment, createYearEndClosingDraft, depreciateAssetsForPeriod, exportFinancialBooks, getAccountingAuditCompliancePack, getFinancialBooks, getLatestPreparedFinancialBooks, getFinancialPlanVariance, getMonthEndControlPack, getTreasuryCashForecast, getTreasuryStressTest, listAccountingAccounts, listFinancialPlans, listTreasuryCommitments, prepareMonthEndReversalDrafts, previewYearEndClosing, type AccountingAuditCompliancePack, type FinancialPlan, type FinancialPlanVariance, type MonthEndControlPack, type TreasuryCashForecast, type TreasuryCommitment, type TreasuryStressTest } from "@/api/accounting";
import { governanceControlsApi, type ControlRecord } from "@/api/governanceControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import type { AccountingAccount, FinancialBooksPack } from "@/types/accounting";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type OpeningLine = { account_id: string; debit: number; credit: number; description: string };
type PlanningLine = { account_code: string; period_start: string; amount: number; note: string };

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function yearStart() {
  const now = new Date();
  return `${now.getFullYear()}-01-01`;
}

function yearEnd() {
  const now = new Date();
  return `${now.getFullYear()}-12-31`;
}

export function FinancialBooksWorkspace() {
  const { currentCompany, currentBranch, branches } = useAppData();
  const [fromDate, setFromDate] = useState(yearStart());
  const [toDate, setToDate] = useState(isoToday());
  const [branchId, setBranchId] = useState(currentBranch?.id ?? "all");
  const [books, setBooks] = useState<FinancialBooksPack | null>(null);
  const [preparedSnapshot, setPreparedSnapshot] = useState<{ preparedAt?: string | null; scopeName?: string | null } | null>(null);
  const [periods, setPeriods] = useState<ControlRecord[]>([]);
  const [readiness, setReadiness] = useState<Record<string, unknown> | null>(null);
  const [monthEndPack, setMonthEndPack] = useState<MonthEndControlPack | null>(null);
  const [monthEndWorking, setMonthEndWorking] = useState(false);
  const [adjustmentWorking, setAdjustmentWorking] = useState(false);
  const [adjustmentType, setAdjustmentType] = useState<"accrual" | "prepayment" | "accrued_income">("accrual");
  const [adjustmentAmount, setAdjustmentAmount] = useState("");
  const [adjustmentAccountCode, setAdjustmentAccountCode] = useState("6500");
  const [adjustmentDescription, setAdjustmentDescription] = useState("");
  const [adjustmentReversalDate, setAdjustmentReversalDate] = useState("");
  const [selectedPeriod, setSelectedPeriod] = useState<string>("");
  const [accounts, setAccounts] = useState<AccountingAccount[]>([]);
  const [plans, setPlans] = useState<FinancialPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [planVariance, setPlanVariance] = useState<FinancialPlanVariance | null>(null);
  const [planningWorking, setPlanningWorking] = useState(false);
  const [treasuryWorking, setTreasuryWorking] = useState(false);
  const [auditWorking, setAuditWorking] = useState(false);
  const [auditPack, setAuditPack] = useState<AccountingAuditCompliancePack | null>(null);
  const [treasuryCommitments, setTreasuryCommitments] = useState<TreasuryCommitment[]>([]);
  const [treasuryForecast, setTreasuryForecast] = useState<TreasuryCashForecast | null>(null);
  const [treasuryStress, setTreasuryStress] = useState<TreasuryStressTest | null>(null);
  const [treasuryFrom, setTreasuryFrom] = useState(isoToday());
  const [treasuryTo, setTreasuryTo] = useState(yearEnd());
  const [minimumCash, setMinimumCash] = useState("0");
  const [collectionRate, setCollectionRate] = useState("100");
  const [obligationRate, setObligationRate] = useState("100");
  const [unexpectedOutflow, setUnexpectedOutflow] = useState("0");
  const [commitmentTitle, setCommitmentTitle] = useState("");
  const [commitmentCategory, setCommitmentCategory] = useState<"expense" | "payroll" | "provider" | "tax" | "refund" | "capital" | "other">("expense");
  const [commitmentDueDate, setCommitmentDueDate] = useState(isoToday());
  const [commitmentAmount, setCommitmentAmount] = useState("");
  const [commitmentDescription, setCommitmentDescription] = useState("");
  const [planName, setPlanName] = useState(`Budget ${new Date().getFullYear()}`);
  const [planType, setPlanType] = useState<"budget" | "forecast">("budget");
  const [planStart, setPlanStart] = useState(yearStart());
  const [planEnd, setPlanEnd] = useState(yearEnd());
  const [planNotes, setPlanNotes] = useState("");
  const [planningLines, setPlanningLines] = useState<PlanningLine[]>([
    { account_code: "4000", period_start: yearStart(), amount: 0, note: "" },
  ]);
  const [loading, setLoading] = useState(false);
  const [periodWorking, setPeriodWorking] = useState(false);
  const [openingWorking, setOpeningWorking] = useState(false);
  const [exportWorking, setExportWorking] = useState<"pdf" | "xlsx" | null>(null);
  const [yearEndWorking, setYearEndWorking] = useState(false);
  const [yearEndPreview, setYearEndPreview] = useState<Record<string, unknown> | null>(null);
  const [yearEndStart, setYearEndStart] = useState(yearStart());
  const [yearEndEnd, setYearEndEnd] = useState(yearEnd());
  const [periodNote, setPeriodNote] = useState("Reviewed and supported by period close evidence.");
  const [newPeriodStart, setNewPeriodStart] = useState(yearStart());
  const [newPeriodEnd, setNewPeriodEnd] = useState(isoToday());
  const [openingDate, setOpeningDate] = useState(yearStart());
  const [openingReference, setOpeningReference] = useState(`OPENING-${new Date().getFullYear()}`);
  const [openingDescription, setOpeningDescription] = useState("Opening balances migrated into LoanHub");
  const [openingLines, setOpeningLines] = useState<OpeningLine[]>([
    { account_id: "", debit: 0, credit: 0, description: "" },
    { account_id: "", debit: 0, credit: 0, description: "" },
  ]);

  useEffect(() => {
    setBranchId(currentBranch?.id ?? "all");
  }, [currentBranch?.id]);

  const companyId = currentCompany?.id;
  const effectiveBranchId = branchId === "all" ? null : branchId;

  const loadBooks = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    try {
      const result = await getFinancialBooks({
        companyId,
        branchId: effectiveBranchId,
        fromDate,
        toDate,
        includeLedgerDetail: false,
      });
      setBooks(result);
      setPreparedSnapshot(null);
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not prepare the financial books"));
    } finally {
      setLoading(false);
    }
  }, [companyId, effectiveBranchId, fromDate, toDate]);

  const loadLatestPreparedBooks = useCallback(async () => {
    if (!companyId) return;
    try {
      const result = await getLatestPreparedFinancialBooks(companyId, effectiveBranchId);
      if (result.available && result.books) {
        setBooks(result.books);
        setPreparedSnapshot({
          preparedAt: result.prepared_at,
          scopeName: result.scope_name,
        });
      }
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not load the latest prepared financial books"));
    }
  }, [companyId, effectiveBranchId]);

  const loadControls = useCallback(async () => {
    if (!companyId) return;
    try {
      const [periodRows, accountRows, planRows, commitmentRows] = await Promise.all([
        governanceControlsApi.accountingPeriods(),
        listAccountingAccounts(companyId),
        listFinancialPlans(companyId, effectiveBranchId),
        listTreasuryCommitments(companyId, effectiveBranchId),
      ]);
      setPeriods(periodRows);
      setAccounts(accountRows);
      setPlans(planRows);
      setTreasuryCommitments(commitmentRows);
      setSelectedPlanId((current) => current || planRows[0]?.id || "");
      setSelectedPeriod((current) => current || periodRows[0]?.id || "");
      if (accountRows.length >= 2) {
        setOpeningLines((current) => current.map((line, index) => ({
          ...line,
          account_id: line.account_id || accountRows[index]?.id || accountRows[0]?.id || "",
        })));
      }
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not load accounting controls"));
    }
  }, [companyId, effectiveBranchId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadControls();
      void loadLatestPreparedBooks();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadControls, loadLatestPreparedBooks]);

  const openingTotals = useMemo(
    () => openingLines.reduce(
      (sum, line) => ({ debit: sum.debit + Number(line.debit || 0), credit: sum.credit + Number(line.credit || 0) }),
      { debit: 0, credit: 0 },
    ),
    [openingLines],
  );
  const openingBalanced = openingTotals.debit > 0 && Math.abs(openingTotals.debit - openingTotals.credit) < 0.005;

  async function loadMonthEndPack() {
    if (!companyId || !selectedPeriod) return;
    const period = periods.find((item) => item.id === selectedPeriod);
    if (!period) return;
    setMonthEndWorking(true);
    try {
      const result = await getMonthEndControlPack({
        companyId,
        branchId: effectiveBranchId,
        periodStart: String(period.period_start),
        periodEnd: String(period.period_end),
      });
      setMonthEndPack(result);
      toast.success(result.ready_to_lock ? "Month-end controls are green" : "Month-end controls need attention");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not prepare month-end control pack"));
    } finally {
      setMonthEndWorking(false);
    }
  }

  async function prepareAdjustmentDraft() {
    if (!companyId || !selectedPeriod || !adjustmentDescription.trim() || Number(adjustmentAmount) <= 0) return;
    const period = periods.find((item) => item.id === selectedPeriod);
    if (!period) return;
    setAdjustmentWorking(true);
    try {
      const entry = await createMonthEndAdjustmentDraft({
        adjustment_type: adjustmentType,
        amount: Number(adjustmentAmount),
        account_code: adjustmentAccountCode,
        description: adjustmentDescription.trim(),
        entry_date: String(period.period_end),
        branch_id: effectiveBranchId,
        reversal_date: adjustmentReversalDate || null,
      }, companyId);
      toast.success("Month-end adjustment draft prepared", { description: `${entry.entry_number} requires a different finance user to post it.` });
      setAdjustmentAmount("");
      setAdjustmentDescription("");
      await loadMonthEndPack();
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not prepare month-end adjustment draft"));
    } finally {
      setAdjustmentWorking(false);
    }
  }

  async function postDeterministicDepreciation() {
    if (!companyId || !selectedPeriod) return;
    const period = periods.find((item) => item.id === selectedPeriod);
    if (!period) return;
    setAdjustmentWorking(true);
    try {
      const result = await depreciateAssetsForPeriod({
        companyId,
        branchId: effectiveBranchId,
        periodStart: String(period.period_start),
        periodEnd: String(period.period_end),
      });
      toast.success("Period depreciation posted", { description: `${result.posted.length} asset entries · ${formatMoney(result.total_depreciation)}` });
      await loadMonthEndPack();
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not post period depreciation"));
    } finally {
      setAdjustmentWorking(false);
    }
  }

  async function prepareScheduledReversals() {
    if (!companyId || !selectedPeriod) return;
    const period = periods.find((item) => item.id === selectedPeriod);
    if (!period) return;
    setAdjustmentWorking(true);
    try {
      const result = await prepareMonthEndReversalDrafts({
        companyId,
        branchId: effectiveBranchId,
        asOf: String(period.period_end),
      });
      toast.success("Scheduled reversal preparation complete", { description: `${result.prepared_count} draft(s) prepared; ${result.waiting_for_source_post_count} awaiting source posting.` });
      await loadMonthEndPack();
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not prepare scheduled reversal drafts"));
    } finally {
      setAdjustmentWorking(false);
    }
  }

  async function createPlan() {
    if (!companyId || !planName.trim()) return;
    setPlanningWorking(true);
    try {
      const row = await createFinancialPlan({
        name: planName.trim(),
        plan_type: planType,
        fiscal_start: planStart,
        fiscal_end: planEnd,
        branch_id: effectiveBranchId,
        notes: planNotes.trim() || undefined,
        lines: planningLines.filter((line) => line.account_code && Number(line.amount) >= 0).map((line) => ({
          account_code: line.account_code,
          period_start: line.period_start,
          amount: Number(line.amount),
          note: line.note.trim() || undefined,
        })),
      }, companyId);
      toast.success("Financial plan draft created");
      await loadControls();
      setSelectedPlanId(row.id);
      setPlanVariance(null);
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not create financial plan"));
    } finally {
      setPlanningWorking(false);
    }
  }

  async function approvePlan() {
    if (!companyId || !selectedPlanId) return;
    setPlanningWorking(true);
    try {
      await approveFinancialPlan(selectedPlanId, companyId);
      toast.success("Financial plan approved");
      await loadControls();
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not approve financial plan"));
    } finally {
      setPlanningWorking(false);
    }
  }

  async function analyzePlan() {
    if (!companyId || !selectedPlanId) return;
    setPlanningWorking(true);
    try {
      const result = await getFinancialPlanVariance(selectedPlanId, toDate, companyId, effectiveBranchId);
      setPlanVariance(result);
      toast.success("Budget variance analysis refreshed");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not analyse financial plan"));
    } finally {
      setPlanningWorking(false);
    }
  }

  async function rollForecast() {
    if (!companyId || !selectedPlanId) return;
    setPlanningWorking(true);
    try {
      const row = await createRollingForecast(selectedPlanId, toDate, `Rolling forecast ${toDate}`, companyId);
      toast.success("Rolling forecast draft created");
      await loadControls();
      setSelectedPlanId(row.id);
      setPlanVariance(null);
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not create rolling forecast"));
    } finally {
      setPlanningWorking(false);
    }
  }

  function updatePlanningLine(index: number, patch: Partial<PlanningLine>) {
    setPlanningLines((rows) => rows.map((row, i) => i === index ? { ...row, ...patch } : row));
  }

  async function prepareTreasuryForecast() {
    if (!companyId) return;
    setTreasuryWorking(true);
    try {
      const payload = {
        from_date: treasuryFrom,
        to_date: treasuryTo,
        minimum_cash: Number(minimumCash || 0),
        collection_rate: Number(collectionRate || 0) / 100,
        obligation_rate: Number(obligationRate || 0) / 100,
        unexpected_outflow: Number(unexpectedOutflow || 0),
        branch_id: effectiveBranchId,
      };
      const [forecast, stress] = await Promise.all([
        getTreasuryCashForecast(payload, companyId),
        getTreasuryStressTest({
          from_date: treasuryFrom,
          to_date: treasuryTo,
          minimum_cash: Number(minimumCash || 0),
          branch_id: effectiveBranchId,
        }, companyId),
      ]);
      setTreasuryForecast(forecast);
      setTreasuryStress(stress);
      toast.success(forecast.breach_count ? "Liquidity forecast has minimum-cash breaches" : "Liquidity forecast is above the minimum-cash threshold");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not prepare treasury forecast"));
    } finally {
      setTreasuryWorking(false);
    }
  }

  async function createCommitment() {
    if (!companyId || !commitmentTitle.trim() || Number(commitmentAmount) <= 0) return;
    setTreasuryWorking(true);
    try {
      await createTreasuryCommitment({
        title: commitmentTitle.trim(),
        category: commitmentCategory,
        due_date: commitmentDueDate,
        amount: Number(commitmentAmount),
        branch_id: effectiveBranchId,
        description: commitmentDescription.trim() || undefined,
      }, companyId);
      toast.success("Treasury commitment draft created");
      setCommitmentTitle("");
      setCommitmentAmount("");
      setCommitmentDescription("");
      await loadControls();
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not create treasury commitment"));
    } finally {
      setTreasuryWorking(false);
    }
  }

  async function approveCommitment(id: string) {
    if (!companyId) return;
    setTreasuryWorking(true);
    try {
      await approveTreasuryCommitment(id, companyId);
      toast.success("Treasury commitment approved");
      await loadControls();
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not approve treasury commitment"));
    } finally {
      setTreasuryWorking(false);
    }
  }

  async function loadAuditPack() {
    if (!companyId) return;
    setAuditWorking(true);
    try {
      const result = await getAccountingAuditCompliancePack({
        companyId,
        branchId: effectiveBranchId,
        periodStart: fromDate,
        periodEnd: toDate,
      });
      setAuditPack(result);
      toast.success(result.control_fail_count ? "Audit pack prepared with control exceptions" : "Audit pack controls are green");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not prepare audit compliance pack"));
    } finally {
      setAuditWorking(false);
    }
  }

  function exportAuditEvidence() {
    if (!auditPack) return;
    const blob = new Blob([JSON.stringify(auditPack, null, 2)], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = `${currentCompany?.name ?? "LoanHub"}_Audit_Evidence_${fromDate}_${toDate}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(href);
    toast.success("Audit evidence pack exported");
  }

  async function createPeriod() {
    if (!newPeriodStart || !newPeriodEnd) return;
    setPeriodWorking(true);
    try {
      const created = await governanceControlsApi.createAccountingPeriod(newPeriodStart, newPeriodEnd);
      toast.success("Accounting period created");
      await loadControls();
      setSelectedPeriod(created.id);
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not create accounting period"));
    } finally {
      setPeriodWorking(false);
    }
  }

  async function checkReadiness() {
    if (!selectedPeriod) return;
    setPeriodWorking(true);
    try {
      const result = await governanceControlsApi.periodReadiness(selectedPeriod);
      setReadiness(result.close_pack);
      toast.success("Period close readiness refreshed");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not evaluate period readiness"));
    } finally {
      setPeriodWorking(false);
    }
  }

  async function periodAction(action: "lock" | "close" | "reopen") {
    if (!selectedPeriod || periodNote.trim().length < 5) return;
    setPeriodWorking(true);
    try {
      await governanceControlsApi.periodAction(selectedPeriod, action, periodNote.trim());
      toast.success(action === "lock" ? "Period soft-closed" : action === "close" ? "Period hard-closed" : "Period reopened");
      setReadiness(null);
      setYearEndPreview(null);
      await loadControls();
    } catch (error) {
      toast.error(getErrorMessage(error, `Could not ${action} accounting period`));
    } finally {
      setPeriodWorking(false);
    }
  }

  async function downloadBooks(format: "pdf" | "xlsx") {
    if (!companyId) return;
    setExportWorking(format);
    try {
      const blob = await exportFinancialBooks({
        companyId,
        branchId: effectiveBranchId,
        fromDate,
        toDate,
        format,
      });
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = `${currentCompany?.name ?? "LoanHub"}_Financial_Books_${fromDate}_${toDate}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(href);
      toast.success(format === "pdf" ? "Financial books PDF prepared" : "Financial books Excel workbook prepared");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not export financial books"));
    } finally {
      setExportWorking(null);
    }
  }

  async function previewYearEnd() {
    if (!companyId) return;
    setYearEndWorking(true);
    try {
      const result = await previewYearEndClosing({
        companyId,
        branchId: effectiveBranchId,
        financialYearStart: yearEndStart,
        financialYearEnd: yearEndEnd,
      });
      setYearEndPreview(result);
      toast.success("Year-end closing preview prepared");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not prepare year-end closing preview"));
    } finally {
      setYearEndWorking(false);
    }
  }

  async function prepareYearEndDraft() {
    if (!companyId) return;
    setYearEndWorking(true);
    try {
      const journal = await createYearEndClosingDraft({
        companyId,
        branchId: effectiveBranchId,
        financialYearStart: yearEndStart,
        financialYearEnd: yearEndEnd,
      });
      toast.success("Year-end closing draft created", {
        description: `${journal.entry_number} is waiting for a different authorised finance user to post it.`,
      });
      const result = await previewYearEndClosing({
        companyId,
        branchId: effectiveBranchId,
        financialYearStart: yearEndStart,
        financialYearEnd: yearEndEnd,
      });
      setYearEndPreview(result);
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not create year-end closing draft"));
    } finally {
      setYearEndWorking(false);
    }
  }

  async function cancelYearEndDraft() {
    if (!companyId || !yearEndPreview?.existing_journal_id) return;
    setYearEndWorking(true);
    try {
      await cancelYearEndClosingDraft(String(yearEndPreview.existing_journal_id), companyId);
      toast.success("Year-end closing draft cancelled");
      const result = await previewYearEndClosing({
        companyId,
        branchId: effectiveBranchId,
        financialYearStart: yearEndStart,
        financialYearEnd: yearEndEnd,
      });
      setYearEndPreview(result);
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not cancel year-end closing draft"));
    } finally {
      setYearEndWorking(false);
    }
  }

  function updateOpeningLine(index: number, patch: Partial<OpeningLine>) {
    setOpeningLines((current) => current.map((line, i) => i === index ? { ...line, ...patch } : line));
  }

  async function createOpeningDraft() {
    if (!companyId || !openingBalanced) {
      toast.error("Opening balance debits and credits must be equal");
      return;
    }
    setOpeningWorking(true);
    try {
      await createOpeningBalanceMigration({
        entry_date: openingDate,
        description: openingDescription.trim(),
        migration_reference: openingReference.trim(),
        branch_id: effectiveBranchId,
        lines: openingLines
          .filter((line) => Number(line.debit || 0) > 0 || Number(line.credit || 0) > 0)
          .map((line) => ({
            account_id: line.account_id,
            description: line.description.trim() || undefined,
            debit: Number(line.debit || 0),
            credit: Number(line.credit || 0),
          })),
      }, companyId);
      toast.success("Opening-balance draft created", { description: "A different finance user must post it before it becomes official ledger truth." });
      await loadBooks();
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not create opening balances"));
    } finally {
      setOpeningWorking(false);
    }
  }

  const currentPeriod = periods.find((period) => period.id === selectedPeriod);
  const closeChecks = ((readiness?.checks ?? {}) as Record<string, boolean>);
  const ratioGroups = books?.financial_ratios ?? {};

  return (
    <div className="loanhub-page space-y-6">
      <section className="loanhub-hero flex flex-col justify-between gap-5 p-6 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Frank Wood engine</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Financial Books</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
            Prepare the official accounting books from posted LoanHub transactions, close accounting periods, and migrate balanced opening balances.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadBooks()} disabled={loading}><RefreshCcw className="h-4 w-4" />Refresh books</Button>
      </section>

      <Tabs defaultValue="books" className="space-y-5">
        <TabsList className="grid h-auto w-full grid-cols-2 rounded-2xl p-1 md:grid-cols-7">
          <TabsTrigger value="books">Financial books</TabsTrigger>
          <TabsTrigger value="periods">Period close</TabsTrigger>
          <TabsTrigger value="month-end">Month-end controls</TabsTrigger>
          <TabsTrigger value="planning">Planning</TabsTrigger>
          <TabsTrigger value="treasury">Treasury</TabsTrigger>
          <TabsTrigger value="audit">Audit & compliance</TabsTrigger>
          <TabsTrigger value="opening">Opening balances</TabsTrigger>
        </TabsList>

        <TabsContent value="books" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader>
              <CardTitle>Reporting period</CardTitle>
              <CardDescription>
                Choose the scope used to prepare the complete accounting book pack.
                {preparedSnapshot?.preparedAt ? ` Latest automatic snapshot: ${new Date(preparedSnapshot.preparedAt).toLocaleString()} (${preparedSnapshot.scopeName || "selected scope"}).` : ""}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-4">
              <Field label="From"><Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} /></Field>
              <Field label="To"><Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} /></Field>
              <Field label="Branch"><Select value={branchId} onValueChange={setBranchId}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All branches</SelectItem>{branches.map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}</SelectItem>)}</SelectContent></Select></Field>
              <div className="flex items-end"><LoadingButton className="w-full" loading={loading} onClick={() => void loadBooks()}><BookOpenCheck className="h-4 w-4" />Prepare books</LoadingButton></div>
            </CardContent>
          </Card>

          {books ? <>
            <div className="grid gap-4 md:grid-cols-4">
              <Metric label="Trial balance difference" value={formatMoney(books.trial_balance.difference)} />
              <Metric label="Net profit" value={formatMoney(Number(books.income_statement.totals.net_profit ?? 0))} />
              <Metric label="Total assets" value={formatMoney(Number(books.statement_of_financial_position.totals.total_assets ?? books.statement_of_financial_position.totals.asset ?? 0))} />
              <Metric label="General ledger accounts" value={String(books.general_ledger.length)} />
            </div>
            <div className="flex flex-wrap gap-2">
              <LoadingButton variant="outline" loading={exportWorking === "pdf"} onClick={() => void downloadBooks("pdf")}><Download className="h-4 w-4" />Export PDF</LoadingButton>
              <LoadingButton variant="outline" loading={exportWorking === "xlsx"} onClick={() => void downloadBooks("xlsx")}><FileSpreadsheet className="h-4 w-4" />Export Excel</LoadingButton>
            </div>

            <Card className="loanhub-panel overflow-hidden">
              <CardHeader><CardTitle>Book index</CardTitle><CardDescription>{books.preparation_note}</CardDescription></CardHeader>
              <CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>#</TableHead><TableHead>Book</TableHead><TableHead>Purpose</TableHead></TableRow></TableHeader><TableBody>{books.book_index.map((item) => <TableRow key={item.order}><TableCell>{item.order}</TableCell><TableCell className="font-black">{titleCase(item.book)}</TableCell><TableCell>{item.purpose}</TableCell></TableRow>)}</TableBody></Table></CardContent>
            </Card>

            <Card className="loanhub-panel overflow-hidden">
              <CardHeader><CardTitle>General ledger</CardTitle><CardDescription>Opening, period movements and closing balance for every active account.</CardDescription></CardHeader>
              <CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Account</TableHead><TableHead className="text-right">Opening</TableHead><TableHead className="text-right">Debit</TableHead><TableHead className="text-right">Credit</TableHead><TableHead className="text-right">Closing</TableHead></TableRow></TableHeader><TableBody>{books.general_ledger.map((row) => <TableRow key={row.account_id}><TableCell><span className="font-mono text-xs font-black text-primary">{row.account_code}</span><p className="font-semibold">{row.account_name}</p></TableCell><TableCell className="text-right">{formatMoney(row.opening_balance)}</TableCell><TableCell className="text-right">{formatMoney(row.period_debit)}</TableCell><TableCell className="text-right">{formatMoney(row.period_credit)}</TableCell><TableCell className="text-right font-black">{formatMoney(row.closing_balance)}</TableCell></TableRow>)}</TableBody></Table></div></CardContent>
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Statement title="Income statement" statement={books.income_statement} />
              <Statement title="Statement of financial position" statement={books.statement_of_financial_position} />
            </div>

            <Card className="loanhub-panel">
              <CardHeader><CardTitle>Financial analysis</CardTitle><CardDescription>Frank Wood Chapters 38–39 ratios. These are signals for interpretation, not conclusions by themselves.</CardDescription></CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {Object.entries(ratioGroups).filter(([, value]) => value && typeof value === "object" && !Array.isArray(value)).slice(0, 4).map(([group, values]) => <div key={group} className="rounded-2xl border p-4"><p className="mb-3 font-black">{titleCase(group)}</p><div className="space-y-2 text-sm">{Object.entries(values as Record<string, unknown>).slice(0, 6).map(([key, value]) => <div key={key} className="flex justify-between gap-4"><span className="text-muted-foreground">{titleCase(key)}</span><span className="font-bold">{value == null ? "—" : typeof value === "number" ? value.toFixed(2) : String(value)}</span></div>)}</div></div>)}
              </CardContent>
            </Card>
          </> : <Card className="loanhub-panel"><CardContent className="py-14 text-center text-muted-foreground">Prepare the books to view the full accounting pack.</CardContent></Card>}
        </TabsContent>

        <TabsContent value="periods" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader><CardTitle className="flex items-center gap-2"><CalendarCheck2 className="h-5 w-5 text-primary" />Accounting period close</CardTitle><CardDescription>Open → locked (soft-close) → closed (hard-close). Locking is allowed only when the full close pack is green.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
                <Field label="New period start"><Input type="date" value={newPeriodStart} onChange={(e) => setNewPeriodStart(e.target.value)} /></Field>
                <Field label="New period end"><Input type="date" value={newPeriodEnd} onChange={(e) => setNewPeriodEnd(e.target.value)} /></Field>
                <div className="flex items-end"><LoadingButton loading={periodWorking} variant="outline" onClick={() => void createPeriod()}>Create period</LoadingButton></div>
              </div>
              <Field label="Period"><Select value={selectedPeriod} onValueChange={(value) => { setSelectedPeriod(value); setReadiness(null); }}><SelectTrigger><SelectValue placeholder="Select accounting period" /></SelectTrigger><SelectContent>{periods.map((period) => <SelectItem key={period.id} value={period.id}>{String(period.period_start)} – {String(period.period_end)} · {titleCase(period.status)}</SelectItem>)}</SelectContent></Select></Field>
              {currentPeriod ? <div className="flex flex-wrap gap-2"><Badge>{titleCase(currentPeriod.status)}</Badge><Badge variant="outline">{String(currentPeriod.period_start)} – {String(currentPeriod.period_end)}</Badge></div> : null}
              <Field label="Control note"><Textarea value={periodNote} onChange={(e) => setPeriodNote(e.target.value)} /></Field>
              <div className="flex flex-wrap gap-2">
                <LoadingButton loading={periodWorking} variant="outline" onClick={() => void checkReadiness()}><Scale className="h-4 w-4" />Check readiness</LoadingButton>
                {currentPeriod?.status === "open" ? <LoadingButton loading={periodWorking} onClick={() => void periodAction("lock")}>Soft-close</LoadingButton> : null}
                {currentPeriod?.status === "locked" ? <LoadingButton loading={periodWorking} onClick={() => void periodAction("close")}>Hard-close</LoadingButton> : null}
                {currentPeriod && ["locked", "closed"].includes(String(currentPeriod.status)) ? <LoadingButton loading={periodWorking} variant="destructive" onClick={() => void periodAction("reopen")}>Reopen</LoadingButton> : null}
                <LoadingButton loading={yearEndWorking} variant="outline" onClick={() => void previewYearEnd()}>Preview year-end close</LoadingButton>
              </div>
            </CardContent>
          </Card>

          {readiness ? <Card className="loanhub-panel"><CardHeader><CardTitle>Close readiness</CardTitle><CardDescription>{Boolean(readiness.ready_to_lock) ? "All hard controls currently pass." : "Resolve the failed controls before soft-close."}</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{Object.entries(closeChecks).map(([key, passed]) => <div key={key} className="flex items-center justify-between rounded-xl border p-3"><span className="text-sm">{titleCase(key)}</span><Badge variant={passed ? "default" : "destructive"}>{passed ? "Pass" : "Fail"}</Badge></div>)}</CardContent></Card> : null}

          <Card className="loanhub-panel">
            <CardHeader><CardTitle>Financial year closing range</CardTitle><CardDescription>Every monthly/quarterly accounting period inside this range must already be hard-closed, with no gaps. The next accounting period must be open.</CardDescription></CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
              <Field label="Financial year start"><Input type="date" value={yearEndStart} onChange={(e) => { setYearEndStart(e.target.value); setYearEndPreview(null); }} /></Field>
              <Field label="Financial year end"><Input type="date" value={yearEndEnd} onChange={(e) => { setYearEndEnd(e.target.value); setYearEndPreview(null); }} /></Field>
              <div className="flex items-end"><LoadingButton loading={yearEndWorking} variant="outline" onClick={() => void previewYearEnd()}>Preview year-end</LoadingButton></div>
            </CardContent>
          </Card>

          {yearEndPreview ? <Card className="loanhub-panel">
            <CardHeader><CardTitle>Year-end closing transfer</CardTitle><CardDescription>{String(yearEndPreview.policy ?? "")}</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-4">
                <Metric label="Revenue" value={formatMoney(Number(yearEndPreview.revenue_total ?? 0))} />
                <Metric label="Expenses" value={formatMoney(Number(yearEndPreview.expense_total ?? 0))} />
                <Metric label="Profit / loss" value={formatMoney(Number(yearEndPreview.net_profit_or_loss ?? 0))} />
                <Metric label="Closing date" value={String(yearEndPreview.closing_date ?? "—")} />
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant={Boolean(yearEndPreview.balanced) ? "default" : "destructive"}>{Boolean(yearEndPreview.balanced) ? "Balanced" : "Unbalanced"}</Badge>
                {yearEndPreview.existing_journal_id ? <Badge variant="outline">Draft already prepared</Badge> : null}
              </div>
              {!yearEndPreview.existing_journal_id ? <LoadingButton loading={yearEndWorking} onClick={() => void prepareYearEndDraft()}>Prepare maker/checker closing draft</LoadingButton> : null}
              {yearEndPreview.existing_journal_id && yearEndPreview.existing_journal_status === "draft" ? <LoadingButton loading={yearEndWorking} variant="destructive" onClick={() => void cancelYearEndDraft()}>Cancel closing draft</LoadingButton> : null}
            </CardContent>
          </Card> : null}
        </TabsContent>

        <TabsContent value="month-end" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader>
              <CardTitle>Month-end control pack</CardTitle>
              <CardDescription>Reconcile the loan folio subledger to GL control 1100, inspect depreciation due, and review period adjustments before locking the books.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Accounting period"><Select value={selectedPeriod} onValueChange={(value) => { setSelectedPeriod(value); setMonthEndPack(null); }}><SelectTrigger><SelectValue placeholder="Select accounting period" /></SelectTrigger><SelectContent>{periods.map((period) => <SelectItem key={period.id} value={period.id}>{String(period.period_start)} – {String(period.period_end)} · {titleCase(period.status)}</SelectItem>)}</SelectContent></Select></Field>
              <LoadingButton loading={monthEndWorking} onClick={() => void loadMonthEndPack()}><Scale className="h-4 w-4" />Prepare month-end pack</LoadingButton>
            </CardContent>
          </Card>

          {monthEndPack ? <>
            <div className="grid gap-4 md:grid-cols-4">
              <Metric label="Close status" value={monthEndPack.ready_to_lock ? "Ready" : "Attention"} />
              <Metric label="Loan folios" value={String(monthEndPack.loan_receivables_subledger.folio_count)} />
              <Metric label="GL receivables" value={formatMoney(monthEndPack.loan_receivables_subledger.general_ledger_total)} />
              <Metric label="Depreciation due" value={formatMoney(monthEndPack.fixed_asset_depreciation.total_due)} />
            </div>

            <Card className="loanhub-panel">
              <CardHeader><CardTitle>Control checklist</CardTitle><CardDescription>{monthEndPack.policy_note}</CardDescription></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {Object.entries(monthEndPack.checks).map(([key, passed]) => <div key={key} className="flex items-center justify-between rounded-xl border p-3"><span className="text-sm">{titleCase(key)}</span><Badge variant={passed ? "default" : "destructive"}>{passed ? "Pass" : "Fail"}</Badge></div>)}
              </CardContent>
            </Card>

            <Card className="loanhub-panel">
              <CardHeader>
                <CardTitle>Adjustment preparation</CardTitle>
                <CardDescription>Prepare judgemental adjustments as maker/checker drafts. Deterministic fixed-asset depreciation can be posted from the asset schedule.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <Field label="Adjustment"><Select value={adjustmentType} onValueChange={(value) => { const kind = value as "accrual" | "prepayment" | "accrued_income"; setAdjustmentType(kind); setAdjustmentAccountCode(kind === "accrued_income" ? "4900" : "6500"); }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="accrual">Accrual</SelectItem><SelectItem value="prepayment">Prepayment</SelectItem><SelectItem value="accrued_income">Accrued income</SelectItem></SelectContent></Select></Field>
                  <Field label={adjustmentType === "accrued_income" ? "Revenue account" : "Expense account"}><Select value={adjustmentAccountCode} onValueChange={setAdjustmentAccountCode}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{accounts.filter((account) => adjustmentType === "accrued_income" ? account.account_type === "revenue" : account.account_type === "expense").map((account) => <SelectItem key={account.id} value={account.code}>{account.code} · {account.name}</SelectItem>)}</SelectContent></Select></Field>
                  <Field label="Amount"><Input type="number" min={0} step="0.01" value={adjustmentAmount} onChange={(e) => setAdjustmentAmount(e.target.value)} /></Field>
                  <Field label="Reverse on (optional)"><Input type="date" value={adjustmentReversalDate} onChange={(e) => setAdjustmentReversalDate(e.target.value)} /></Field>
                </div>
                <Field label="Evidence / description"><Textarea value={adjustmentDescription} onChange={(e) => setAdjustmentDescription(e.target.value)} placeholder="Describe the source evidence and accounting judgement supporting this adjustment." /></Field>
                <div className="flex flex-wrap gap-2">
                  <LoadingButton loading={adjustmentWorking} onClick={() => void prepareAdjustmentDraft()}>Prepare maker/checker draft</LoadingButton>
                  <LoadingButton loading={adjustmentWorking} variant="outline" disabled={!monthEndPack?.fixed_asset_depreciation.asset_count_due} onClick={() => void postDeterministicDepreciation()}>Post due depreciation</LoadingButton>
                  <LoadingButton loading={adjustmentWorking} variant="outline" onClick={() => void prepareScheduledReversals()}>Prepare due reversal drafts</LoadingButton>
                </div>
              </CardContent>
            </Card>

            <Card className="loanhub-panel">
              <CardHeader><CardTitle>VAT control reconciliation</CardTitle><CardDescription>{monthEndPack.vat_reconciliation.policy_note}</CardDescription></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-4">
                <Metric label="Input VAT receivable" value={formatMoney(monthEndPack.vat_reconciliation.closing_input_vat_receivable)} />
                <Metric label="Output VAT payable" value={formatMoney(monthEndPack.vat_reconciliation.closing_output_vat_payable)} />
                <Metric label="Net VAT payable" value={formatMoney(monthEndPack.vat_reconciliation.net_vat_payable)} />
                <Metric label="Net VAT receivable" value={formatMoney(monthEndPack.vat_reconciliation.net_vat_receivable)} />
              </CardContent>
            </Card>

            <Card className="loanhub-panel overflow-hidden">
              <CardHeader><CardTitle>Loan receivables subsidiary ledger</CardTitle><CardDescription>Independent loan folios rebuilt from successful source transactions and reconciled to the general ledger control account.</CardDescription></CardHeader>
              <CardContent className="space-y-4 p-0">
                <div className="grid gap-3 px-6 md:grid-cols-4">
                  <Metric label="Folio total" value={formatMoney(monthEndPack.loan_receivables_subledger.folio_total)} />
                  <Metric label="Control source total" value={formatMoney(monthEndPack.loan_receivables_subledger.control_source_total)} />
                  <Metric label="GL control 1100" value={formatMoney(monthEndPack.loan_receivables_subledger.general_ledger_total)} />
                  <Metric label="GL variance" value={formatMoney(monthEndPack.loan_receivables_subledger.control_to_gl_variance)} />
                </div>
                <div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Loan folio</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Operational balance</TableHead><TableHead className="text-right">Source principal</TableHead><TableHead>Written off</TableHead></TableRow></TableHeader><TableBody>{monthEndPack.loan_receivables_subledger.folios.map((folio) => <TableRow key={folio.loan_id}><TableCell><p className="font-black">{folio.folio_number}</p><p className="font-mono text-xs text-muted-foreground">{folio.loan_reference}</p></TableCell><TableCell>{titleCase(folio.status || "unknown")}</TableCell><TableCell className="text-right">{formatMoney(folio.operational_balance)}</TableCell><TableCell className="text-right font-black">{formatMoney(folio.source_principal_outstanding)}</TableCell><TableCell>{folio.written_off ? "Yes" : "No"}</TableCell></TableRow>)}</TableBody></Table></div>
              </CardContent>
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="loanhub-panel">
                <CardHeader><CardTitle>Fixed-asset depreciation due</CardTitle><CardDescription>Deterministic depreciation still outstanding for the selected period.</CardDescription></CardHeader>
                <CardContent className="space-y-3">
                  {monthEndPack.fixed_asset_depreciation.assets.length ? monthEndPack.fixed_asset_depreciation.assets.map((asset) => <div key={asset.asset_id} className="flex items-center justify-between rounded-xl border p-3"><div><p className="font-bold">{asset.reference} · {asset.name}</p><p className="text-xs text-muted-foreground">Carrying amount {formatMoney(asset.carrying_amount_before)}</p></div><span className="font-black">{formatMoney(asset.amount_due)}</span></div>) : <p className="text-sm text-muted-foreground">No depreciation remains due for this period.</p>}
                </CardContent>
              </Card>
              <Card className="loanhub-panel">
                <CardHeader><CardTitle>Adjustment register</CardTitle><CardDescription>Accruals, prepayments, accrued income, depreciation, credit losses and other period-end adjustments.</CardDescription></CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-3"><Metric label="Posted" value={String(monthEndPack.adjustment_register.posted_count)} /><Metric label="Draft" value={String(monthEndPack.adjustment_register.draft_count)} /></div>
                  {monthEndPack.adjustment_register.entries.slice(0, 12).map((entry) => <div key={entry.journal_entry_id} className="flex items-center justify-between gap-3 rounded-xl border p-3"><div><p className="font-bold">{entry.entry_number}</p><p className="text-xs text-muted-foreground">{titleCase(entry.reference_type || "adjustment")} · {entry.entry_date}</p></div><div className="text-right"><p className="font-black">{formatMoney(entry.amount)}</p><Badge variant={entry.status === "posted" ? "default" : "outline"}>{titleCase(entry.status)}</Badge></div></div>)}
                </CardContent>
              </Card>
            </div>
          </> : null}
        </TabsContent>

        <TabsContent value="planning" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader><CardTitle>Budgeting & forecasting</CardTitle><CardDescription>Create versioned management plans without changing posted accounting truth. Approval uses maker/checker control.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Field label="Plan name"><Input value={planName} onChange={(e) => setPlanName(e.target.value)} /></Field>
                <Field label="Plan type"><Select value={planType} onValueChange={(value) => setPlanType(value as "budget" | "forecast")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="budget">Budget</SelectItem><SelectItem value="forecast">Forecast</SelectItem></SelectContent></Select></Field>
                <Field label="Start"><Input type="date" value={planStart} onChange={(e) => setPlanStart(e.target.value)} /></Field>
                <Field label="End"><Input type="date" value={planEnd} onChange={(e) => setPlanEnd(e.target.value)} /></Field>
              </div>
              <Field label="Planning notes"><Textarea value={planNotes} onChange={(e) => setPlanNotes(e.target.value)} /></Field>
              <div className="overflow-x-auto rounded-2xl border">
                <Table><TableHeader><TableRow><TableHead>Account</TableHead><TableHead>Month</TableHead><TableHead>Planned amount</TableHead><TableHead>Note</TableHead></TableRow></TableHeader><TableBody>{planningLines.map((line, index) => <TableRow key={index}><TableCell><Select value={line.account_code} onValueChange={(account_code) => updatePlanningLine(index, { account_code })}><SelectTrigger className="min-w-64"><SelectValue /></SelectTrigger><SelectContent>{accounts.filter((account) => ["revenue","expense","asset","liability","equity"].includes(account.account_type)).map((account) => <SelectItem key={account.id} value={account.code}>{account.code} · {account.name}</SelectItem>)}</SelectContent></Select></TableCell><TableCell><Input type="date" value={line.period_start} onChange={(e) => updatePlanningLine(index, { period_start: e.target.value })} /></TableCell><TableCell><Input type="number" min={0} step="0.01" value={line.amount || ""} onChange={(e) => updatePlanningLine(index, { amount: Number(e.target.value || 0) })} /></TableCell><TableCell><Input value={line.note} onChange={(e) => updatePlanningLine(index, { note: e.target.value })} /></TableCell></TableRow>)}</TableBody></Table>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => setPlanningLines((rows) => [...rows, { account_code: accounts[0]?.code ?? "4000", period_start: planStart, amount: 0, note: "" }])}>Add plan line</Button>
                <LoadingButton loading={planningWorking} onClick={() => void createPlan()}>Create plan draft</LoadingButton>
              </div>
            </CardContent>
          </Card>

          <Card className="loanhub-panel">
            <CardHeader><CardTitle>Plan control & variance intelligence</CardTitle><CardDescription>Actuals are recomputed from posted journal lines; explanations state observed variances only and do not invent business causes.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <Field label="Financial plan"><Select value={selectedPlanId} onValueChange={(value) => { setSelectedPlanId(value); setPlanVariance(null); }}><SelectTrigger><SelectValue placeholder="Select plan" /></SelectTrigger><SelectContent>{plans.map((plan) => <SelectItem key={plan.id} value={plan.id}>{plan.name} · {titleCase(plan.plan_type)} · {titleCase(plan.status)} · v{plan.version}</SelectItem>)}</SelectContent></Select></Field>
              <div className="flex flex-wrap gap-2">
                <LoadingButton loading={planningWorking} variant="outline" onClick={() => void approvePlan()}>Approve plan</LoadingButton>
                <LoadingButton loading={planningWorking} onClick={() => void analyzePlan()}>Analyse actual vs plan</LoadingButton>
                <LoadingButton loading={planningWorking} variant="outline" onClick={() => void rollForecast()}>Create rolling forecast</LoadingButton>
              </div>
              {planVariance ? <>
                <div className="grid gap-3 md:grid-cols-3"><Metric label="Planned" value={formatMoney(planVariance.planned_total)} /><Metric label="Actual" value={formatMoney(planVariance.actual_total)} /><Metric label="Net variance" value={formatMoney(planVariance.net_variance)} /></div>
                <p className="text-xs text-muted-foreground">{planVariance.intelligence_policy}</p>
                <div className="space-y-2">{planVariance.top_variances.map((row) => <div key={`${row.account_code}-${row.period}`} className="rounded-xl border p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="font-black">{row.account_code} · {row.account_name}</p><p className="text-xs text-muted-foreground">{row.period}</p></div><Badge variant={row.favorability === "unfavorable" ? "destructive" : row.favorability === "favorable" ? "default" : "outline"}>{titleCase(row.favorability)}</Badge></div><p className="mt-2 text-sm">{row.explanation}</p></div>)}</div>
              </> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="treasury" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader><CardTitle>Treasury & cash-flow intelligence</CardTitle><CardDescription>Forecast forward liquidity from posted cash/bank balances, scheduled loan collections and approved future commitments. Scenarios never alter the ledger.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Field label="From"><Input type="date" value={treasuryFrom} onChange={(e) => setTreasuryFrom(e.target.value)} /></Field>
                <Field label="To"><Input type="date" value={treasuryTo} onChange={(e) => setTreasuryTo(e.target.value)} /></Field>
                <Field label="Minimum cash"><Input type="number" min={0} step="0.01" value={minimumCash} onChange={(e) => setMinimumCash(e.target.value)} /></Field>
                <Field label="Unexpected outflow"><Input type="number" min={0} step="0.01" value={unexpectedOutflow} onChange={(e) => setUnexpectedOutflow(e.target.value)} /></Field>
                <Field label="Collection assumption %"><Input type="number" min={0} max={100} step="1" value={collectionRate} onChange={(e) => setCollectionRate(e.target.value)} /></Field>
                <Field label="Obligation assumption %"><Input type="number" min={0} step="1" value={obligationRate} onChange={(e) => setObligationRate(e.target.value)} /></Field>
              </div>
              <LoadingButton loading={treasuryWorking} onClick={() => void prepareTreasuryForecast()}>Run liquidity forecast & stress test</LoadingButton>
            </CardContent>
          </Card>

          <Card className="loanhub-panel">
            <CardHeader><CardTitle>Future treasury commitments</CardTitle><CardDescription>Record known obligations such as payroll, provider settlements, tax, refunds or capital purchases. Draft commitments require a different finance user to approve them before they enter forecasts.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Field label="Title"><Input value={commitmentTitle} onChange={(e) => setCommitmentTitle(e.target.value)} /></Field>
                <Field label="Category"><Select value={commitmentCategory} onValueChange={(v) => setCommitmentCategory(v as typeof commitmentCategory)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["expense","payroll","provider","tax","refund","capital","other"].map((v) => <SelectItem key={v} value={v}>{titleCase(v)}</SelectItem>)}</SelectContent></Select></Field>
                <Field label="Due date"><Input type="date" value={commitmentDueDate} onChange={(e) => setCommitmentDueDate(e.target.value)} /></Field>
                <Field label="Amount"><Input type="number" min={0} step="0.01" value={commitmentAmount} onChange={(e) => setCommitmentAmount(e.target.value)} /></Field>
              </div>
              <Field label="Description"><Textarea value={commitmentDescription} onChange={(e) => setCommitmentDescription(e.target.value)} /></Field>
              <LoadingButton loading={treasuryWorking} onClick={() => void createCommitment()}>Create commitment draft</LoadingButton>
              <div className="space-y-2">{treasuryCommitments.slice(0, 20).map((row) => <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3"><div><p className="font-black">{row.title}</p><p className="text-xs text-muted-foreground">{titleCase(row.category)} · {row.due_date} · {row.reference}</p></div><div className="flex items-center gap-2"><span className="font-black">{formatMoney(row.amount)}</span><Badge variant={row.status === "approved" ? "default" : "outline"}>{titleCase(row.status)}</Badge>{row.status === "draft" ? <LoadingButton size="sm" variant="outline" loading={treasuryWorking} onClick={() => void approveCommitment(row.id)}>Approve</LoadingButton> : null}</div></div>)}</div>
            </CardContent>
          </Card>

          {treasuryForecast ? <>
            <div className="grid gap-4 md:grid-cols-4">
              <Metric label="Opening available cash" value={formatMoney(treasuryForecast.opening_liquidity.available_cash)} />
              <Metric label="Expected collections" value={formatMoney(treasuryForecast.total_expected_collections)} />
              <Metric label="Approved obligations" value={formatMoney(treasuryForecast.total_approved_obligations)} />
              <Metric label="Projected closing cash" value={formatMoney(treasuryForecast.projected_closing_cash)} />
            </div>
            <Card className="loanhub-panel">
              <CardHeader><CardTitle>Liquidity alerts</CardTitle><CardDescription>{treasuryForecast.policy_note}</CardDescription></CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2"><Badge variant={treasuryForecast.breach_count ? "destructive" : "default"}>{treasuryForecast.breach_count ? `${treasuryForecast.breach_count} breach day(s)` : "No minimum-cash breaches"}</Badge></div>
                {treasuryForecast.breaches.slice(0, 10).map((b) => <div key={b.date} className="flex items-center justify-between rounded-xl border p-3"><span>{b.date}</span><span className="font-black">Shortfall {formatMoney(b.shortfall)}</span></div>)}
              </CardContent>
            </Card>
            <Card className="loanhub-panel overflow-hidden">
              <CardHeader><CardTitle>Daily cash forecast</CardTitle></CardHeader>
              <CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead className="text-right">Opening</TableHead><TableHead className="text-right">Collections</TableHead><TableHead className="text-right">Obligations</TableHead><TableHead className="text-right">Closing</TableHead></TableRow></TableHeader><TableBody>{treasuryForecast.daily_forecast.map((row) => <TableRow key={row.date}><TableCell>{row.date}</TableCell><TableCell className="text-right">{formatMoney(row.opening_cash)}</TableCell><TableCell className="text-right">{formatMoney(row.expected_collections)}</TableCell><TableCell className="text-right">{formatMoney(row.approved_obligations)}</TableCell><TableCell className="text-right font-black">{formatMoney(row.projected_closing_cash)} {row.minimum_cash_breach ? <Badge variant="destructive" className="ml-2">Breach</Badge> : null}</TableCell></TableRow>)}</TableBody></Table></div></CardContent>
            </Card>
          </> : null}

          {treasuryStress ? <Card className="loanhub-panel">
            <CardHeader><CardTitle>Liquidity stress scenarios</CardTitle><CardDescription>{treasuryStress.policy_note}</CardDescription></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">{treasuryStress.scenarios.map((row) => <div key={row.scenario} className="rounded-xl border p-3"><p className="font-black">{titleCase(row.scenario)}</p><p className="mt-2 text-sm">Closing: {formatMoney(row.projected_closing_cash)}</p><p className="text-sm">Minimum: {formatMoney(row.minimum_projected_cash)}</p><Badge variant={row.breach_count ? "destructive" : "default"} className="mt-2">{row.breach_count ? `${row.breach_count} breach(es)` : "Pass"}</Badge></div>)}</CardContent>
          </Card> : null}
        </TabsContent>

        <TabsContent value="audit" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader><CardTitle>Audit, compliance & statutory finance pack</CardTitle><CardDescription>Verify the sealed audit chain, test accounting controls, review unusual journals, inspect supporting evidence and prepare auditor-ready schedules without changing ledger truth.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-4">
                <Field label="From"><Input type="date" value={fromDate} onChange={(e) => { setFromDate(e.target.value); setAuditPack(null); }} /></Field>
                <Field label="To"><Input type="date" value={toDate} onChange={(e) => { setToDate(e.target.value); setAuditPack(null); }} /></Field>
                <Field label="Branch"><Select value={branchId} onValueChange={(value) => { setBranchId(value); setAuditPack(null); }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All branches</SelectItem>{branches.map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}</SelectItem>)}</SelectContent></Select></Field>
                <div className="flex items-end"><LoadingButton className="w-full" loading={auditWorking} onClick={() => void loadAuditPack()}><Scale className="h-4 w-4" />Prepare audit pack</LoadingButton></div>
              </div>
              {auditPack ? <Button variant="outline" onClick={exportAuditEvidence}><Download className="h-4 w-4" />Export evidence JSON</Button> : null}
            </CardContent>
          </Card>

          {auditPack ? <>
            <div className="grid gap-4 md:grid-cols-4">
              <Metric label="Controls passed" value={String(auditPack.control_pass_count)} />
              <Metric label="Control exceptions" value={String(auditPack.control_fail_count)} />
              <Metric label="Flagged journals" value={String(auditPack.journal_review.flagged_count)} />
              <Metric label="Missing evidence" value={String(auditPack.journal_review.evidence_missing_count)} />
            </div>

            <Card className="loanhub-panel">
              <CardHeader><CardTitle>Audit integrity</CardTitle><CardDescription>LoanHub audit events are cryptographically chained and sealed against mutation.</CardDescription></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-4">
                <Metric label="Sealed events" value={String(auditPack.audit_integrity.sealed_event_count)} />
                <Metric label="Period events" value={String(auditPack.audit_integrity.company_period_event_count)} />
                <div className="rounded-2xl border bg-card p-4"><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">Hash chain</p><Badge className="mt-2" variant={auditPack.audit_integrity.chain_valid ? "default" : "destructive"}>{auditPack.audit_integrity.chain_valid ? "Valid" : "Broken"}</Badge>{auditPack.audit_integrity.broken_event_id ? <p className="mt-2 font-mono text-xs">{auditPack.audit_integrity.broken_event_id}</p> : null}</div>
                <div className="rounded-2xl border bg-card p-4"><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">Severity mix</p><p className="mt-2 text-sm">{Object.entries(auditPack.audit_integrity.severity_counts).map(([key, value]) => `${titleCase(key)} ${value}`).join(" · ") || "No events"}</p></div>
              </CardContent>
            </Card>

            <Card className="loanhub-panel">
              <CardHeader><CardTitle>Finance control checklist</CardTitle><CardDescription>{auditPack.statutory_assessment.note}</CardDescription></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{Object.entries(auditPack.controls).map(([key, passed]) => <div key={key} className="flex items-center justify-between gap-3 rounded-xl border p-3"><span className="text-sm">{titleCase(key)}</span><Badge variant={passed ? "default" : "destructive"}>{passed ? "Pass" : "Exception"}</Badge></div>)}</CardContent>
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="loanhub-panel">
                <CardHeader><CardTitle>VAT control schedule</CardTitle><CardDescription>{auditPack.vat_control.policy_note}</CardDescription></CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2"><Metric label="Input VAT receivable" value={formatMoney(auditPack.vat_control.closing_input_vat_receivable)} /><Metric label="Output VAT payable" value={formatMoney(auditPack.vat_control.closing_output_vat_payable)} /><Metric label="Net VAT payable" value={formatMoney(auditPack.vat_control.net_vat_payable)} /><Metric label="Net VAT receivable" value={formatMoney(auditPack.vat_control.net_vat_receivable)} /></CardContent>
              </Card>
              <Card className="loanhub-panel">
                <CardHeader><CardTitle>Corporation tax control schedule</CardTitle><CardDescription>{auditPack.corporation_tax_control.policy_note}</CardDescription></CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2"><Metric label="Tax expense" value={formatMoney(auditPack.corporation_tax_control.closing_tax_expense)} /><Metric label="Tax payable" value={formatMoney(auditPack.corporation_tax_control.closing_tax_payable)} />{Object.entries(auditPack.corporation_tax_control.control_flags).map(([key, passed]) => <div key={key} className="flex items-center justify-between rounded-xl border p-3"><span className="text-sm">{titleCase(key)}</span><Badge variant={passed ? "default" : "destructive"}>{passed ? "Pass" : "Review"}</Badge></div>)}</CardContent>
              </Card>
            </div>

            <Card className="loanhub-panel overflow-hidden">
              <CardHeader><CardTitle>Unusual-journal review</CardTitle><CardDescription>{auditPack.journal_review.policy_note}</CardDescription></CardHeader>
              <CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Entry</TableHead><TableHead>Date</TableHead><TableHead>Description</TableHead><TableHead>Review flags</TableHead><TableHead>Evidence</TableHead><TableHead className="text-right">Amount</TableHead></TableRow></TableHeader><TableBody>{auditPack.journal_review.flagged_entries.slice(0, 50).map((row) => <TableRow key={row.journal_entry_id}><TableCell className="font-black">{row.entry_number}</TableCell><TableCell>{row.entry_date}</TableCell><TableCell className="max-w-80">{row.description}</TableCell><TableCell><div className="flex max-w-96 flex-wrap gap-1">{row.flags.map((flag) => <Badge key={flag} variant={flag === "supporting_evidence_missing" ? "destructive" : "outline"}>{titleCase(flag)}</Badge>)}</div></TableCell><TableCell>{row.evidence_files.length ? `${row.evidence_files.length} file(s)` : "None"}</TableCell><TableCell className="text-right font-black">{formatMoney(row.amount)}</TableCell></TableRow>)}</TableBody></Table></div></CardContent>
            </Card>

            <Card className="loanhub-panel">
              <CardHeader><CardTitle>Deterministic auditor sample</CardTitle><CardDescription>Prioritises higher-risk flagged entries, then adds deterministic coverage. It is reproducible and contains no hidden random selection.</CardDescription></CardHeader>
              <CardContent className="space-y-2">{auditPack.audit_sample.map((row) => <div key={row.journal_entry_id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3"><div><p className="font-black">{row.entry_number} · {row.entry_date}</p><p className="text-sm text-muted-foreground">{row.description}</p></div><div className="text-right"><p className="font-black">{formatMoney(row.amount)}</p><p className="text-xs text-muted-foreground">{row.flags.map(titleCase).join(", ")}</p></div></div>)}</CardContent>
            </Card>
          </> : null}
        </TabsContent>

        <TabsContent value="opening" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader><CardTitle className="flex items-center gap-2"><Upload className="h-5 w-5 text-primary" />Opening balance migration</CardTitle><CardDescription>Create a balanced draft. A different authorised finance user must post it through the normal maker/checker journal workflow.</CardDescription></CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-4 md:grid-cols-3">
                <Field label="Opening date"><Input type="date" value={openingDate} onChange={(e) => setOpeningDate(e.target.value)} /></Field>
                <Field label="Migration reference"><Input value={openingReference} onChange={(e) => setOpeningReference(e.target.value)} /></Field>
                <Field label="Description"><Input value={openingDescription} onChange={(e) => setOpeningDescription(e.target.value)} /></Field>
              </div>
              <div className="overflow-x-auto rounded-2xl border">
                <Table><TableHeader><TableRow><TableHead>Account</TableHead><TableHead>Description</TableHead><TableHead className="w-40">Debit</TableHead><TableHead className="w-40">Credit</TableHead></TableRow></TableHeader><TableBody>{openingLines.map((line, index) => <TableRow key={index}><TableCell><Select value={line.account_id} onValueChange={(account_id) => updateOpeningLine(index, { account_id })}><SelectTrigger className="min-w-64"><SelectValue placeholder="Select account" /></SelectTrigger><SelectContent>{accounts.map((account) => <SelectItem key={account.id} value={account.id}>{account.code} · {account.name}</SelectItem>)}</SelectContent></Select></TableCell><TableCell><Input value={line.description} onChange={(e) => updateOpeningLine(index, { description: e.target.value })} /></TableCell><TableCell><Input type="number" min={0} step="0.01" value={line.debit || ""} onChange={(e) => updateOpeningLine(index, { debit: Number(e.target.value || 0), credit: e.target.value ? 0 : line.credit })} /></TableCell><TableCell><Input type="number" min={0} step="0.01" value={line.credit || ""} onChange={(e) => updateOpeningLine(index, { credit: Number(e.target.value || 0), debit: e.target.value ? 0 : line.debit })} /></TableCell></TableRow>)}</TableBody></Table>
              </div>
              <Button variant="outline" onClick={() => setOpeningLines((rows) => [...rows, { account_id: accounts[0]?.id ?? "", debit: 0, credit: 0, description: "" }])}>Add line</Button>
              <div className="grid gap-3 md:grid-cols-3"><Metric label="Opening debits" value={formatMoney(openingTotals.debit)} /><Metric label="Opening credits" value={formatMoney(openingTotals.credit)} /><Metric label="Difference" value={formatMoney(Math.abs(openingTotals.debit - openingTotals.credit))} /></div>
              <LoadingButton loading={openingWorking} disabled={!openingBalanced || !openingReference.trim() || !openingDescription.trim()} onClick={() => void createOpeningDraft()}><Upload className="h-4 w-4" />Create opening-balance draft</LoadingButton>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border bg-card p-4"><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-2 text-xl font-black">{value}</p></div>;
}

function Statement({ title, statement }: { title: string; statement: FinancialBooksPack["income_statement"] }) {
  return <Card className="loanhub-panel"><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="space-y-4">{Object.entries(statement.sections ?? {}).map(([section, rows]) => <div key={section} className="rounded-xl border"><div className="flex justify-between bg-muted/30 px-3 py-2 font-black"><span>{titleCase(section)}</span><span>{formatMoney(Number(statement.totals[section] ?? 0))}</span></div>{rows.map((row) => <div key={`${section}-${row.code}`} className="flex justify-between gap-4 border-t px-3 py-2 text-sm"><span>{row.code} · {row.name}</span><span className="font-bold">{formatMoney(row.amount)}</span></div>)}</div>)}</CardContent></Card>;
}
