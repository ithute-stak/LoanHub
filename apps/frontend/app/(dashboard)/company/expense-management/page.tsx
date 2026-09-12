"use client";

import { createUuid } from "@/lib/uuid";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Banknote,
  BookOpenCheck,
  Calculator,
  CheckCircle2,
  Clock3,
  Download,
  FileCheck2,
  Landmark,
  Plus,
  Printer,
  RefreshCcw,
  RotateCcw,
  Send,
  Settings2,
  ShieldCheck,
  Tags,
  WalletCards,
  XCircle,
} from "lucide-react";

import { expenseManagementApi } from "@/api/expenseManagement";
import { AccountingBooksPanel } from "@/components/accounting/accounting-books-panel";
import { SubmissionReportsPanel } from "@/components/accounting/submission-reports-panel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DataPagination } from "@/components/ui/data-pagination";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import {
  loadFinancialWorkspace,
  setFinancialBranch,
  setFinancialBusinessDate,
  setFinancialStatement,
} from "@/store/features/slices/financialOperationsSlice";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { ACCOUNTING_ROLES, COMPANY_MANAGEMENT_ROLES, REPORTING_ROLES, hasRole } from "@/types/auth";
import type {
  BranchFundingTransfer,
  OpeningSourceCreate,
  PaymentMethod,
  PaymentMethodOption,
  TreasuryEntry,
  TreasuryEntryCreate,
  TreasuryEntryType,
  TreasurySettings,
  TreasurySettingsUpdate,
} from "@/types/expenseManagement";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const today = () => {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
};
const monthStart = () => `${today().slice(0, 8)}01`;
const writableStatuses = new Set(["open", "reopened"]);
const approvalRoles = new Set(["company_owner", "company_admin", "branch_manager"]);
const writeRoles = new Set(["company_owner", "company_admin", "branch_manager", "finance_officer"]);
const PAGE_SIZE = 10;

const EMPTY_ENTRY: TreasuryEntryCreate = {
  branch_id: null,
  direction: "money_out",
  entry_type: "expense",
  payment_method: "cash",
  amount: 0,
  currency: "LSL",
  description: "",
  proof_reference: null,
  proof_url: null,
  proof_notes: null,
  external_reference: null,
  expense_category_id: null,
  idempotency_key: null,
  voucher_number: null,
};

const EMPTY_SOURCE: OpeningSourceCreate = {
  branch_id: null,
  business_date: today(),
  source_type: "cash_float",
  payment_method: "cash",
  amount: 0,
  currency: "LSL",
  description: "",
  source_reference: null,
  proof_reference: null,
  proof_url: null,
  proof_notes: null,
};

export default function UnifiedAccountingExpensePage() {
  const dispatch = useAppDispatch();
  const { branches } = useAppData();
  const { activeBranchId, activeRole } = useTenant();
  const {
    status,
    refreshing,
    error,
    businessDate,
    selectedBranchId,
    methods,
    settings,
    categories,
    dashboard,
    ledger,
    transfers,
    statement,
    integrity,
  } = useAppSelector((state) => state.financialOperations);

  const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
  const canWrite = writeRoles.has(activeRole ?? "");
  const canApprove = approvalRoles.has(activeRole ?? "");
  const canAccessAccounting = hasRole(activeRole, ACCOUNTING_ROLES);
  const canAccessReports = hasRole(activeRole, REPORTING_ROLES);
  const [working, setWorking] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  const [entryDialog, setEntryDialog] = useState(false);
  const [entryForm, setEntryForm] = useState<TreasuryEntryCreate>(EMPTY_ENTRY);
  const [sourceDialog, setSourceDialog] = useState(false);
  const [sourceForm, setSourceForm] = useState<OpeningSourceCreate>(EMPTY_SOURCE);
  const [submitDialog, setSubmitDialog] = useState(false);
  const [declaredClosing, setDeclaredClosing] = useState("");
  const [submissionNotes, setSubmissionNotes] = useState("");
  const [reopenDialog, setReopenDialog] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const [decisionEntry, setDecisionEntry] = useState<TreasuryEntry | null>(null);
  const [decisionMode, setDecisionMode] = useState<"approve" | "reject">("approve");
  const [decisionReason, setDecisionReason] = useState("");

  const [transferDialog, setTransferDialog] = useState(false);
  const [transferForm, setTransferForm] = useState({
    target_branch_id: "",
    amount: 0,
    payment_method: "cash" as PaymentMethod,
    proof_reference: "",
    proof_url: "",
    notes: "",
  });
  const [categoryDialog, setCategoryDialog] = useState(false);
  const [categoryForm, setCategoryForm] = useState({ name: "", description: "" });
  const [settingsDialog, setSettingsDialog] = useState(false);
  const [settingsForm, setSettingsForm] = useState<TreasurySettingsUpdate | null>(null);

  const [statementFrom, setStatementFrom] = useState(monthStart());
  const [statementTo, setStatementTo] = useState(today());
  const [statementMethods, setStatementMethods] = useState<PaymentMethod[]>([]);
  const [statementDirections, setStatementDirections] = useState<Array<"money_in" | "money_out">>([]);
  const [entrySearch, setEntrySearch] = useState("");
  const [entryDirection, setEntryDirection] = useState<"all" | "money_in" | "money_out">("all");
  const [entryPage, setEntryPage] = useState(1);
  const [sourcePage, setSourcePage] = useState(1);
  const [approvalPage, setApprovalPage] = useState(1);
  const [branchPage, setBranchPage] = useState(1);
  const [transferPage, setTransferPage] = useState(1);
  const [statementPage, setStatementPage] = useState(1);

  const selectedBranch = useMemo(
    () => branches.find((item) => item.id === selectedBranchId) ?? null,
    [branches, selectedBranchId],
  );
  const ledgerLocked = Boolean(ledger && !writableStatuses.has(ledger.status));
  const pendingEntries = useMemo(
    () => ledger?.entries.filter((entry) => !entry.is_voided && entry.approval_status === "pending") ?? [],
    [ledger],
  );
  const selectedChannelTotal = useMemo(() => {
    if (statementMethods.length === 0) return 0;
    const rows = statement?.method_totals ?? dashboard?.method_totals ?? [];
    return rows
      .filter((row) => statementMethods.includes(row.method))
      .reduce((sum, row) => sum + Number(row.net), 0);
  }, [dashboard, statement, statementMethods]);

  const visibleEntries = useMemo(() => {
    const query = entrySearch.trim().toLowerCase();
    return (ledger?.entries ?? []).filter((entry) => {
      if (entry.is_voided) return false;
      if (entryDirection !== "all" && entry.direction !== entryDirection) return false;
      if (!query) return true;
      return [entry.description, entry.voucher_number, entry.proof_reference, entry.entry_type, entry.payment_method]
        .some((value) => String(value ?? "").toLowerCase().includes(query));
    });
  }, [entryDirection, entrySearch, ledger?.entries]);

  const pagedEntries = visibleEntries.slice((entryPage - 1) * PAGE_SIZE, entryPage * PAGE_SIZE);
  const openingSources = (ledger?.opening_sources ?? []).filter((item) => !item.is_voided);
  const pagedSources = openingSources.slice((sourcePage - 1) * PAGE_SIZE, sourcePage * PAGE_SIZE);
  const pagedApprovals = pendingEntries.slice((approvalPage - 1) * PAGE_SIZE, approvalPage * PAGE_SIZE);
  const branchRows = dashboard?.branches ?? [];
  const pagedBranches = branchRows.slice((branchPage - 1) * PAGE_SIZE, branchPage * PAGE_SIZE);
  const pagedTransfers = transfers.slice((transferPage - 1) * PAGE_SIZE, transferPage * PAGE_SIZE);
  const statementEntries = statement?.entries ?? [];
  const pagedStatementEntries = statementEntries.slice((statementPage - 1) * PAGE_SIZE, statementPage * PAGE_SIZE);

  const reload = useCallback(async () => {
    try {
      await dispatch(loadFinancialWorkspace({
        businessDate,
        branchId: canManage ? selectedBranchId : (selectedBranchId ?? activeBranchId),
        statementFrom,
        statementTo,
        includeAccounting: canAccessAccounting,
        includeReports: canAccessReports,
      })).unwrap();
    } catch (loadError: unknown) {
      toast.error(getErrorMessage(loadError, "The accounting and expense workspace could not be loaded"));
    }
  }, [activeBranchId, businessDate, canAccessAccounting, canAccessReports, canManage, dispatch, selectedBranchId, statementFrom, statementTo]);

  useEffect(() => {
    const timer = window.setTimeout(() => void reload(), 0);
    return () => window.clearTimeout(timer);
  }, [reload]);

  async function refreshAfter(message?: string) {
    await reload();
    if (message) toast.success(message);
  }

  function changeBusinessDate(value: string) {
    dispatch(setFinancialBusinessDate(value));
    setEntryPage(1);
    setSourcePage(1);
  }

  function changeBranch(value: string) {
    dispatch(setFinancialBranch(value === "all" ? null : value));
    setEntryPage(1);
    setSourcePage(1);
  }

  function openEntry(direction: "money_in" | "money_out", entryType: TreasuryEntryType) {
    if (!ledger) {
      toast.warning("Select a branch with an open financial day first");
      return;
    }
    if (ledgerLocked) {
      toast.warning(`The ${formatDate(ledger.business_date)} branch day is ${titleCase(ledger.status)}. Reopen it for a late entry or use the next financial day.`);
      if (canManage || (activeRole === "branch_manager" && settings?.allow_branch_reopen)) setReopenDialog(true);
      return;
    }
    setEntryForm({
      ...EMPTY_ENTRY,
      branch_id: selectedBranchId,
      direction,
      entry_type: entryType,
      currency: settings?.currency ?? "LSL",
      idempotency_key: createUuid(),
    });
    setEntryDialog(true);
  }

  async function saveEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (entryForm.entry_type === "expense" && !entryForm.expense_category_id) {
      toast.error("Select an expense category");
      return;
    }
    if (entryForm.payment_method !== "cash" && settings?.require_proof_for_non_cash && !entryForm.proof_reference?.trim() && !entryForm.proof_url?.trim()) {
      toast.error("Enter a transaction reference or proof document for this non-cash channel");
      return;
    }
    setWorking(true);
    try {
      const created = await expenseManagementApi.recordEntry({
        ...entryForm,
        branch_id: selectedBranchId,
        description: entryForm.description.trim(),
        proof_reference: entryForm.proof_reference?.trim() || null,
        proof_url: entryForm.proof_url?.trim() || null,
        proof_notes: entryForm.proof_notes?.trim() || null,
        voucher_number: entryForm.voucher_number?.trim() || null,
      });
      setEntryDialog(false);
      setEntryForm(EMPTY_ENTRY);
      await refreshAfter(created.approval_status === "pending" ? "Expense saved and sent for approval" : "Money movement recorded and posted to accounting");
    } catch (saveError: unknown) {
      toast.error(getErrorMessage(saveError, "The money movement could not be recorded"));
    } finally {
      setWorking(false);
    }
  }

  async function saveOpeningSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorking(true);
    try {
      await expenseManagementApi.createOpeningSource({
        ...sourceForm,
        branch_id: selectedBranchId,
        business_date: businessDate,
        description: sourceForm.description.trim(),
        source_reference: sourceForm.source_reference?.trim() || null,
        proof_reference: sourceForm.proof_reference?.trim() || null,
        proof_url: sourceForm.proof_url?.trim() || null,
      });
      setSourceDialog(false);
      setSourceForm({ ...EMPTY_SOURCE, business_date: businessDate });
      await refreshAfter("Opening-balance source recorded and journalled");
    } catch (saveError: unknown) {
      toast.error(getErrorMessage(saveError, "The opening source could not be recorded"));
    } finally {
      setWorking(false);
    }
  }

  async function decideEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!decisionEntry) return;
    if (decisionMode === "reject" && decisionReason.trim().length < 5) {
      toast.error("Enter a rejection reason of at least five characters");
      return;
    }
    setWorking(true);
    try {
      if (decisionMode === "approve") {
        await expenseManagementApi.approveEntry(decisionEntry.id, decisionReason.trim() || null);
      } else {
        await expenseManagementApi.rejectEntry(decisionEntry.id, decisionReason.trim());
      }
      setDecisionEntry(null);
      setDecisionReason("");
      await refreshAfter(decisionMode === "approve" ? "Expense approved and posted" : "Expense rejected");
    } catch (decisionError: unknown) {
      toast.error(getErrorMessage(decisionError, "The expense decision could not be saved"));
    } finally {
      setWorking(false);
    }
  }

  async function submitDay(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ledger) return;
    setWorking(true);
    try {
      const submission = await expenseManagementApi.submitDay(ledger.id, {
        declared_closing_balance: declaredClosing ? Number(declaredClosing) : null,
        notes: submissionNotes.trim() || null,
      });
      setSubmitDialog(false);
      setDeclaredClosing("");
      setSubmissionNotes("");
      await refreshAfter(`Branch day submitted to headquarters as sequence ${submission.sequence_number}. Its PDF is stored in Files.`);
      setActiveTab("reports");
    } catch (submitError: unknown) {
      toast.error(getErrorMessage(submitError, "The branch day could not be submitted"));
    } finally {
      setWorking(false);
    }
  }

  async function reopenDay(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ledger) return;
    setWorking(true);
    try {
      await expenseManagementApi.reopenDay(ledger.id, reopenReason.trim());
      setReopenDialog(false);
      setReopenReason("");
      await refreshAfter("Branch day reopened with a permanent audit reason");
    } catch (reopenError: unknown) {
      toast.error(getErrorMessage(reopenError, "The branch day could not be reopened"));
    } finally {
      setWorking(false);
    }
  }

  async function saveTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorking(true);
    try {
      await expenseManagementApi.createTransfer({
        target_branch_id: transferForm.target_branch_id,
        amount: transferForm.amount,
        payment_method: transferForm.payment_method,
        business_date: businessDate,
        proof_reference: transferForm.proof_reference.trim() || null,
        proof_url: transferForm.proof_url.trim() || null,
        notes: transferForm.notes.trim() || null,
      });
      setTransferDialog(false);
      setTransferForm({ target_branch_id: "", amount: 0, payment_method: "cash", proof_reference: "", proof_url: "", notes: "" });
      await refreshAfter("Headquarters funding issued. The receiving branch must confirm receipt.");
    } catch (transferError: unknown) {
      toast.error(getErrorMessage(transferError, "The branch funding could not be issued"));
    } finally {
      setWorking(false);
    }
  }

  async function receiveTransfer(transfer: BranchFundingTransfer) {
    setWorking(true);
    try {
      await expenseManagementApi.receiveTransfer(transfer.id);
      await refreshAfter("Funding received and included in the branch opening balance");
    } catch (receiveError: unknown) {
      toast.error(getErrorMessage(receiveError, "The funding receipt could not be confirmed"));
    } finally {
      setWorking(false);
    }
  }

  async function saveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorking(true);
    try {
      await expenseManagementApi.createCategory({ name: categoryForm.name.trim(), description: categoryForm.description.trim() || null });
      setCategoryDialog(false);
      setCategoryForm({ name: "", description: "" });
      await refreshAfter("Expense category created");
    } catch (categoryError: unknown) {
      toast.error(getErrorMessage(categoryError, "The category could not be created"));
    } finally {
      setWorking(false);
    }
  }

  function openSettings() {
    if (!settings) return;
    setSettingsForm(toSettingsUpdate(settings));
    setSettingsDialog(true);
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settingsForm) return;
    setWorking(true);
    try {
      await expenseManagementApi.updateSettings(settingsForm);
      setSettingsDialog(false);
      await refreshAfter("Treasury and accounting controls updated");
    } catch (settingsError: unknown) {
      toast.error(getErrorMessage(settingsError, "The controls could not be saved"));
    } finally {
      setWorking(false);
    }
  }

  async function runCycle() {
    setWorking(true);
    try {
      const result = await expenseManagementApi.runDailyCycle();
      await refreshAfter(`Daily cycle completed: ${result.opened_ledgers} opened, ${result.submitted_ledgers} submitted`);
    } catch (cycleError: unknown) {
      toast.error(getErrorMessage(cycleError, "The daily cycle could not be run"));
    } finally {
      setWorking(false);
    }
  }

  async function repairIntegrity() {
    if (!canManage) return;
    setWorking(true);
    try {
      const result = await expenseManagementApi.repairIntegrity(businessDate, selectedBranchId);
      const repaired = result.repaired_treasury_entries + result.repaired_journals;
      await refreshAfter(
        repaired > 0
          ? `Financial integrity repaired: ${result.repaired_treasury_entries} money-book link(s), ${result.repaired_journals} journal(s), ${result.recalculated_ledgers} ledger(s) recalculated.`
          : `Integrity scan completed. ${result.recalculated_ledgers} ledger(s) recalculated; no missing derived records required repair.`,
      );
      setActiveTab("integrity");
    } catch (repairError: unknown) {
      toast.error(getErrorMessage(repairError, "Financial integrity repair could not be completed"));
    } finally {
      setWorking(false);
    }
  }

  async function buildStatement() {
    setWorking(true);
    try {
      const result = await expenseManagementApi.statement({
        dateFrom: statementFrom,
        dateTo: statementTo,
        branchId: selectedBranchId,
        paymentMethods: statementMethods,
        directions: statementDirections,
      });
      dispatch(setFinancialStatement(result));
      setStatementPage(1);
      toast.success("Statement calculated");
    } catch (statementError: unknown) {
      toast.error(getErrorMessage(statementError, "The statement could not be calculated"));
    } finally {
      setWorking(false);
    }
  }

  async function downloadCsv() {
    setWorking(true);
    try {
      await expenseManagementApi.downloadStatementCsv({
        dateFrom: statementFrom,
        dateTo: statementTo,
        branchId: selectedBranchId,
        paymentMethods: statementMethods,
        directions: statementDirections,
      });
    } catch (downloadError: unknown) {
      toast.error(getErrorMessage(downloadError, "The statement CSV could not be downloaded"));
    } finally {
      setWorking(false);
    }
  }

  if (status === "idle" || status === "loading") return <PageLoader rows={10} />;

  return (
    <div className="loanhub-page space-y-6">
      <section className="loanhub-hero relative overflow-hidden p-5 sm:p-6">
        <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full bg-primary/12 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-5 xl:flex-row xl:items-center">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-primary"><Landmark className="h-5 w-5" /><span className="text-xs font-black uppercase tracking-[0.2em]">Financial control centre</span></div>
            <h1 className="mt-2 text-3xl font-black tracking-tight">Accounting & expenses</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">One source of truth for branch money, payment channels, expenses, loan cashflows, opening funds, transfers, journals, submissions and reconciliation.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge variant="outline">{selectedBranch?.name ?? "Company consolidated"}</Badge>
              <Badge variant="outline">{formatDate(businessDate)}</Badge>
              <Badge variant={integrity?.status === "critical" ? "destructive" : "secondary"}>
                {integrity?.status === "critical" ? `${integrity.critical_count} critical exception${integrity.critical_count === 1 ? "" : "s"}` : integrity?.status === "warning" ? `${integrity.warning_count} reconciliation warning${integrity.warning_count === 1 ? "" : "s"}` : "Integrity checks healthy"}
              </Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => { setActiveTab("integrity"); }}><ShieldCheck className="h-4 w-4" />Audit integrity</Button>
            <Button variant="outline" onClick={() => void reload()} disabled={refreshing}><RefreshCcw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />Refresh</Button>
            {canManage ? <Button variant="outline" onClick={() => void runCycle()} disabled={working}><Clock3 className="h-4 w-4" />Run daily cycle</Button> : null}
            {canWrite ? <Button onClick={() => openEntry("money_out", "expense")} disabled={!selectedBranchId} title={!selectedBranchId ? "Select a branch before recording an expense" : undefined}><ArrowUpRight className="h-4 w-4" />Record expense</Button> : null}
          </div>
        </div>
      </section>

      {error ? <Alert variant="destructive"><XCircle className="h-4 w-4" /><AlertTitle>Financial workspace warning</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}

      {integrity && integrity.status !== "healthy" ? (
        <Alert variant={integrity.status === "critical" ? "destructive" : "default"}>
          {integrity.status === "critical" ? <XCircle className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
          <AlertTitle>{integrity.status === "critical" ? "Financial integrity exceptions require attention" : "Financial reconciliation warnings"}</AlertTitle>
          <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>{integrity.issue_count} issue(s) detected for this scope: {integrity.missing_treasury_count} missing money-book link(s), {integrity.missing_journal_count} missing journal(s), {integrity.proof_exception_count} proof exception(s), and {integrity.ledger_variance_count} declared closing variance(s).</span>
            <div className="flex shrink-0 gap-2">
              <Button size="sm" variant="outline" onClick={() => setActiveTab("integrity")}>Review</Button>
              {canManage && integrity.repairable_count > 0 ? <Button size="sm" onClick={() => void repairIntegrity()} disabled={working}>Repair derived records</Button> : null}
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      <Card className="rounded-3xl border-border/70">
        <CardContent className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-[1fr_1.2fr_1fr_1.25fr]">
          <Field label="Business date"><Input type="date" value={businessDate} onChange={(event) => changeBusinessDate(event.target.value)} /></Field>
          <Field label="Financial scope"><Select value={selectedBranchId ?? "all"} onValueChange={changeBranch}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{canManage ? <SelectItem value="all">Company consolidated</SelectItem> : null}{branches.filter((branch) => branch.is_active).map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}{branch.is_headquarters ? " · HQ" : ""}</SelectItem>)}</SelectContent></Select></Field>
          <Setting label="Day status" value={ledger ? titleCase(ledger.status) : "Consolidated view"} />
          <Setting label="Automated control cycle" value={`${settings?.auto_open_time?.slice(0, 5) ?? "00:01"} open · ${settings?.auto_submit_time?.slice(0, 5) ?? "16:30"} immutable snapshot`} />
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        <Metric icon={WalletCards} label="Opening funds" value={formatMoney(dashboard?.total_opening_balance ?? 0)} hint="Confirmed opening sources" />
        <Metric icon={ArrowDownLeft} label="Money in" value={formatMoney(dashboard?.total_money_in ?? 0)} hint="All posted inflows" />
        <Metric icon={ArrowUpRight} label="External money out" value={formatMoney(dashboard?.external_money_out ?? dashboard?.total_money_out ?? 0)} hint="Disbursements, expenses & external outflows" />
        <Metric icon={Landmark} label="Internal transfers" value={formatMoney(dashboard?.internal_transfer_out ?? 0)} hint="HQ-to-branch movement, not company expense" />
        <Metric icon={Banknote} label="Expected closing" value={formatMoney(dashboard?.consolidated_closing_balance ?? 0)} hint="Opening + in − all out" />
        <Metric icon={ShieldCheck} label="Pending approvals" value={formatMoney(dashboard?.pending_expense_amount ?? 0)} hint="Excluded until approved" />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 rounded-2xl p-1">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="money-book">Money book</TabsTrigger>
          <TabsTrigger value="opening">Opening sources</TabsTrigger>
          <TabsTrigger value="approvals">Approvals</TabsTrigger>
          <TabsTrigger value="branches">Branches</TabsTrigger>
          <TabsTrigger value="funding">HQ funding</TabsTrigger>
          <TabsTrigger value="statements">Statements</TabsTrigger>
          {canAccessAccounting ? <TabsTrigger value="accounting">Accounting books</TabsTrigger> : null}
          {canAccessReports ? <TabsTrigger value="reports">Reports & PDFs</TabsTrigger> : null}
          <TabsTrigger value="integrity">Integrity & audit</TabsTrigger>
          <TabsTrigger value="controls">Controls</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
            <Card className="rounded-3xl">
              <CardHeader><CardTitle>Opening funds</CardTitle><CardDescription>Confirmed sources carried into the selected business date. Previous closing balances are preserved by payment channel.</CardDescription></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2"><SourceMini label="Previous closings" value={dashboard?.consolidated_previous_closing ?? 0} /><SourceMini label="Owner contributions" value={dashboard?.owner_contributions ?? 0} /><SourceMini label="HQ funding" value={dashboard?.headquarters_funding ?? 0} /><SourceMini label="Other sources" value={dashboard?.other_opening_sources ?? 0} /></CardContent>
            </Card>
            <Card className="overflow-hidden rounded-3xl">
              <CardHeader><CardTitle>Payment-channel positions</CardTitle><CardDescription>Opening position plus today&apos;s posted movement. This is a position view, not just a movement total.</CardDescription></CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader><TableRow><TableHead>Channel</TableHead><TableHead className="text-right">Opening</TableHead><TableHead className="text-right">In</TableHead><TableHead className="text-right">Out</TableHead><TableHead className="text-right">Closing</TableHead><TableHead className="text-right">Entries</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {(dashboard?.method_totals ?? []).length === 0 ? <EmptyRow columns={6} text="No channel position exists for this date." /> : dashboard?.method_totals.map((row) => <TableRow key={row.method}><TableCell className="font-bold">{methodLabel(methods, row.method)}</TableCell><TableCell className="text-right">{formatMoney(row.opening_balance)}</TableCell><TableCell className="text-right font-semibold text-emerald-700">+{formatMoney(row.money_in)}</TableCell><TableCell className="text-right font-semibold text-red-700">−{formatMoney(row.money_out)}</TableCell><TableCell className="text-right font-black">{formatMoney(row.closing_balance)}</TableCell><TableCell className="text-right">{row.entry_count}</TableCell></TableRow>)}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <Value label="Gross movement out" value={formatMoney(dashboard?.total_money_out ?? 0)} />
            <Value label="Less internal branch funding" value={formatMoney(dashboard?.internal_transfer_out ?? 0)} />
            <Value label="External company outflow" value={formatMoney(dashboard?.external_money_out ?? dashboard?.total_money_out ?? 0)} emphasis />
          </div>
          <Alert><BookOpenCheck className="h-4 w-4" /><AlertTitle>Automatic accounting</AlertTitle><AlertDescription>Successful payments, approved expenses, loan disbursements, repayments, owner contributions and qualifying opening adjustments create balanced journals automatically. Internal branch funding is tracked as movement, not double-counted as consolidated company expense.</AlertDescription></Alert>
        </TabsContent>

        <TabsContent value="integrity" className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <IntegrityMetric label="Successful payments" value={integrity?.succeeded_payment_count ?? 0} hint="Payments completed in this scope" />
            <IntegrityMetric label="Treasury linked" value={integrity?.treasury_payment_count ?? 0} hint="Successful payments represented in money book" />
            <IntegrityMetric label="Posted journals" value={integrity?.posted_journal_count ?? 0} hint="Balanced journal headers checked" />
            <IntegrityMetric label="Exceptions" value={integrity?.issue_count ?? 0} hint={`${integrity?.critical_count ?? 0} critical · ${integrity?.warning_count ?? 0} warning`} alert={(integrity?.critical_count ?? 0) > 0} />
          </div>

          <Card className="overflow-hidden rounded-3xl">
            <CardHeader className="border-b bg-muted/20">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div><CardTitle>Transaction completeness & reconciliation</CardTitle><CardDescription>Cross-checks successful payments, money-book rows, journals, proof, branch ledgers, transfers and closing variances for {formatDate(businessDate)}.</CardDescription></div>
                {canManage && (integrity?.repairable_count ?? 0) > 0 ? <LoadingButton loading={working} variant="outline" onClick={() => void repairIntegrity()}><RefreshCcw className="h-4 w-4" />Repair derived records</LoadingButton> : null}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {(integrity?.issues ?? []).length === 0 ? (
                <div className="flex min-h-48 flex-col items-center justify-center px-6 text-center"><CheckCircle2 className="h-10 w-10 text-emerald-600" /><p className="mt-3 font-black">Core financial checks passed</p><p className="mt-1 max-w-2xl text-sm text-muted-foreground">No missing treasury links, missing journals, proof exceptions, stale ledger totals, unbalanced journals or declared closing variances were found in this scope.</p></div>
              ) : (
                <div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Severity</TableHead><TableHead>Control exception</TableHead><TableHead>Branch</TableHead><TableHead className="text-right">Amount</TableHead><TableHead>Repair</TableHead></TableRow></TableHeader><TableBody>{integrity?.issues.map((issue, index) => <TableRow key={`${issue.code}-${issue.record_id ?? index}`}><TableCell><Badge variant={issue.severity === "critical" ? "destructive" : "secondary"}>{titleCase(issue.severity)}</Badge></TableCell><TableCell className="min-w-[28rem]"><p className="font-bold">{issue.title}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{issue.detail}</p></TableCell><TableCell>{issue.branch_id ? branchName(branches, issue.branch_id) : "Company"}</TableCell><TableCell className="text-right font-semibold">{issue.amount !== null && issue.amount !== undefined ? formatMoney(issue.amount) : "—"}</TableCell><TableCell>{issue.repairable ? <Badge variant="outline">Derived record</Badge> : <span className="text-xs text-muted-foreground">Review source</span>}</TableCell></TableRow>)}</TableBody></Table></div>
              )}
            </CardContent>
          </Card>

          <Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Safe repair policy</AlertTitle><AlertDescription>The repair action only reconstructs missing derived money-book links and accounting journals from already successful/confirmed source records, then recalculates cached ledger totals. It never invents a payment, approves an expense, changes a provider result, or overwrites a declared cash count.</AlertDescription></Alert>
        </TabsContent>

        <TabsContent value="money-book" className="space-y-4">
          <Card className="overflow-hidden rounded-3xl">
            <CardHeader className="border-b bg-muted/20"><div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center"><div><CardTitle>Daily branch money book</CardTitle><CardDescription>{selectedBranch?.name ?? "Select a branch"} · {formatDate(businessDate)}</CardDescription></div><div className="flex flex-wrap gap-2">{canWrite ? <><Button variant="outline" onClick={() => openEntry("money_in", "manual_income")}><ArrowDownLeft className="h-4 w-4" />Money in</Button><Button onClick={() => openEntry("money_out", "expense")}><ArrowUpRight className="h-4 w-4" />Money out</Button></> : null}{ledger && writableStatuses.has(ledger.status) ? <Button variant="secondary" onClick={() => setSubmitDialog(true)}><Send className="h-4 w-4" />Submit to HQ</Button> : null}{ledgerLocked && (canManage || (activeRole === "branch_manager" && settings?.allow_branch_reopen)) ? <Button variant="outline" onClick={() => setReopenDialog(true)}><RotateCcw className="h-4 w-4" />Reopen</Button> : null}</div></div></CardHeader>
            <CardContent className="space-y-4 p-4 sm:p-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5"><Value label="Opening" value={formatMoney(ledger?.opening_balance ?? 0)} /><Value label="Money in" value={formatMoney(ledger?.total_money_in ?? 0)} /><Value label="Money out" value={formatMoney(ledger?.total_money_out ?? 0)} /><Value label="Expected close" value={formatMoney(ledger?.expected_closing_balance ?? 0)} emphasis /><Value label="Variance" value={formatMoney(ledger?.variance_amount ?? 0)} /></div>
              <StickyFilterBar
                ariaLabel="Money book search and direction filters"
                className="rounded-2xl data-[floating=true]:border"
              >
                <div className="flex flex-col gap-3 rounded-[inherit] border bg-card/95 p-3 backdrop-blur lg:flex-row"><SuggestionSearch
                  value={entrySearch}
                  onValueChange={(value) => { setEntrySearch(value); setEntryPage(1); }}
                  suggestions={(ledger?.entries ?? []).filter((entry) => !entry.is_voided).map((entry) => ({
                    value: entry.description || entry.voucher_number || entry.proof_reference || entry.external_reference || entry.id,
                    label: entry.description || entry.voucher_number || entry.proof_reference || "Money movement",
                    description: [entry.voucher_number, entry.proof_reference, entry.external_reference].filter(Boolean).join(" · "),
                    keywords: [entry.id, entry.entry_type, entry.direction, entry.payment_method],
                  }))}
                  placeholder="Type a description, voucher or reference..."
                  suggestionLabel="Money movements"
                  emptyMessage="No money movement matches that text."
                  wrapperClassName="min-w-0 flex-1"
                /><Select value={entryDirection} onValueChange={(value) => { setEntryDirection(value as "all" | "money_in" | "money_out"); setEntryPage(1); }}><SelectTrigger className="lg:w-48"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All directions</SelectItem><SelectItem value="money_in">Money in</SelectItem><SelectItem value="money_out">Money out</SelectItem></SelectContent></Select></div>
              </StickyFilterBar>
              <div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Movement</TableHead><TableHead>Channel</TableHead><TableHead>Reference</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Money in</TableHead><TableHead className="text-right">Money out</TableHead></TableRow></TableHeader><TableBody>{pagedEntries.length === 0 ? <EmptyRow columns={7} text="No posted money movements match the filters." /> : pagedEntries.map((entry) => <TableRow key={entry.id}><TableCell>{formatDateTime(entry.occurred_at)}</TableCell><TableCell><p className="font-black">{entry.description}</p><p className="text-xs text-muted-foreground">{titleCase(entry.entry_type)}{entry.voucher_number ? ` · ${entry.voucher_number}` : ""}</p></TableCell><TableCell>{methodLabel(methods, entry.payment_method)}</TableCell><TableCell className="font-mono text-xs">{entry.proof_reference ?? entry.external_reference ?? "-"}</TableCell><TableCell><Status value={entry.approval_status} /></TableCell><TableCell className="text-right font-black text-emerald-700">{entry.direction === "money_in" ? formatMoney(entry.amount) : "-"}</TableCell><TableCell className="text-right font-black text-red-700">{entry.direction === "money_out" ? formatMoney(entry.amount) : "-"}</TableCell></TableRow>)}</TableBody></Table></div>
              <DataPagination page={entryPage} pageSize={PAGE_SIZE} total={visibleEntries.length} onPageChange={setEntryPage} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="opening" className="space-y-4">
          <Card className="overflow-hidden rounded-3xl"><CardHeader className="border-b"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><CardTitle>Opening-balance sources</CardTitle><CardDescription>The opening balance is built from traceable sources, never a single unexplained figure.</CardDescription></div>{canWrite ? <Button onClick={() => { setSourceForm({ ...EMPTY_SOURCE, branch_id: selectedBranchId, business_date: businessDate, currency: settings?.currency ?? "LSL" }); setSourceDialog(true); }}><Plus className="h-4 w-4" />Add source</Button> : null}</div></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Source</TableHead><TableHead>Description</TableHead><TableHead>Channel</TableHead><TableHead>Reference</TableHead><TableHead className="text-right">Amount</TableHead></TableRow></TableHeader><TableBody>{pagedSources.length === 0 ? <EmptyRow columns={5} text="No opening sources are recorded for this branch and date." /> : pagedSources.map((source) => <TableRow key={source.id}><TableCell><Status value={source.source_type} /></TableCell><TableCell><p className="font-black">{source.description}</p><p className="text-xs text-muted-foreground">{source.is_system_generated ? "System generated" : "Manually recorded"}</p></TableCell><TableCell>{methodLabel(methods, source.payment_method)}</TableCell><TableCell className="font-mono text-xs">{source.proof_reference ?? source.source_reference}</TableCell><TableCell className="text-right font-black">{formatMoney(source.amount)}</TableCell></TableRow>)}</TableBody></Table></div><div className="p-4"><DataPagination page={sourcePage} pageSize={PAGE_SIZE} total={openingSources.length} onPageChange={setSourcePage} /></div></CardContent></Card>
        </TabsContent>

        <TabsContent value="approvals" className="space-y-4">
          <Card className="overflow-hidden rounded-3xl"><CardHeader><CardTitle>Expense approval queue</CardTitle><CardDescription>Expenses above the configured threshold remain outside posted balances until approved.</CardDescription></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Expense</TableHead><TableHead>Channel</TableHead><TableHead>Voucher</TableHead><TableHead className="text-right">Amount</TableHead><TableHead className="text-right">Decision</TableHead></TableRow></TableHeader><TableBody>{pagedApprovals.length === 0 ? <EmptyRow columns={5} text="No expenses are waiting for approval." /> : pagedApprovals.map((entry) => <TableRow key={entry.id}><TableCell><p className="font-black">{entry.description}</p><p className="text-xs text-muted-foreground">{formatDateTime(entry.occurred_at)}</p></TableCell><TableCell>{methodLabel(methods, entry.payment_method)}</TableCell><TableCell>{entry.voucher_number ?? "-"}</TableCell><TableCell className="text-right font-black">{formatMoney(entry.amount)}</TableCell><TableCell><div className="flex justify-end gap-2">{canApprove ? <><Button size="sm" variant="outline" onClick={() => { setDecisionMode("reject"); setDecisionEntry(entry); setDecisionReason(""); }}><XCircle className="h-4 w-4" />Reject</Button><Button size="sm" onClick={() => { setDecisionMode("approve"); setDecisionEntry(entry); setDecisionReason(""); }}><CheckCircle2 className="h-4 w-4" />Approve</Button></> : <Badge variant="secondary">Manager required</Badge>}</div></TableCell></TableRow>)}</TableBody></Table></div><div className="p-4"><DataPagination page={approvalPage} pageSize={PAGE_SIZE} total={pendingEntries.length} onPageChange={setApprovalPage} /></div></CardContent></Card>
        </TabsContent>

        <TabsContent value="branches" className="space-y-4">
          <Card className="overflow-hidden rounded-3xl"><CardHeader><CardTitle>Branch financial position</CardTitle><CardDescription>Headquarters and the owner can see every branch&apos;s day status, expected cash and variance.</CardDescription></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Branch</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Opening</TableHead><TableHead className="text-right">Money in</TableHead><TableHead className="text-right">Money out</TableHead><TableHead className="text-right">Expected close</TableHead><TableHead className="text-right">Variance</TableHead></TableRow></TableHeader><TableBody>{pagedBranches.length === 0 ? <EmptyRow columns={7} text="No branch ledgers are available for this date." /> : pagedBranches.map((branch) => <TableRow key={branch.branch_id}><TableCell><p className="font-black">{branch.branch_name}</p>{branch.is_headquarters ? <Badge variant="secondary">Headquarters</Badge> : null}</TableCell><TableCell><Status value={branch.status} /></TableCell><TableCell className="text-right">{formatMoney(branch.opening_balance)}</TableCell><TableCell className="text-right text-emerald-700">{formatMoney(branch.total_money_in)}</TableCell><TableCell className="text-right text-red-700">{formatMoney(branch.total_money_out)}</TableCell><TableCell className="text-right font-black">{formatMoney(branch.expected_closing_balance)}</TableCell><TableCell className={`text-right font-black ${Number(branch.variance_amount) === 0 ? "text-emerald-700" : "text-amber-700"}`}>{formatMoney(branch.variance_amount)}</TableCell></TableRow>)}</TableBody></Table></div><div className="p-4"><DataPagination page={branchPage} pageSize={PAGE_SIZE} total={branchRows.length} onPageChange={setBranchPage} /></div></CardContent></Card>
        </TabsContent>

        <TabsContent value="funding" className="space-y-4">
          <Card className="overflow-hidden rounded-3xl"><CardHeader className="border-b"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><CardTitle>Headquarters morning funding</CardTitle><CardDescription>Funds become part of the receiving branch opening balance only after receipt is confirmed.</CardDescription></div>{canManage ? <Button onClick={() => setTransferDialog(true)}><Send className="h-4 w-4" />Issue funding</Button> : null}</div></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Reference</TableHead><TableHead>From → To</TableHead><TableHead>Channel</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Amount</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{pagedTransfers.length === 0 ? <EmptyRow columns={6} text="No branch funding transfers are recorded for this date." /> : pagedTransfers.map((transfer) => <TableRow key={transfer.id}><TableCell className="font-mono text-xs font-black">{transfer.reference}</TableCell><TableCell>{branchName(branches, transfer.source_branch_id)} → {branchName(branches, transfer.target_branch_id)}</TableCell><TableCell>{methodLabel(methods, transfer.payment_method)}</TableCell><TableCell><Status value={transfer.status} /></TableCell><TableCell className="text-right font-black">{formatMoney(transfer.amount)}</TableCell><TableCell className="text-right">{transfer.status === "issued" && transfer.target_branch_id === selectedBranchId ? <LoadingButton size="sm" loading={working} onClick={() => void receiveTransfer(transfer)}>Confirm receipt</LoadingButton> : "-"}</TableCell></TableRow>)}</TableBody></Table></div><div className="p-4"><DataPagination page={transferPage} pageSize={PAGE_SIZE} total={transfers.length} onPageChange={setTransferPage} /></div></CardContent></Card>
        </TabsContent>

        <TabsContent value="statements" className="space-y-4">
          <Card className="rounded-3xl"><CardHeader><CardTitle>Statement builder and channel calculator</CardTitle><CardDescription>Filter by period, branch, direction and one or more payment channels.</CardDescription></CardHeader><CardContent className="space-y-5"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Field label="From"><Input type="date" value={statementFrom} onChange={(event) => setStatementFrom(event.target.value)} /></Field><Field label="To"><Input type="date" value={statementTo} onChange={(event) => setStatementTo(event.target.value)} /></Field><Setting label="Selected-channel net" value={formatMoney(selectedChannelTotal)} /><div className="flex items-end gap-2"><LoadingButton className="flex-1" loading={working} onClick={() => void buildStatement()}><Calculator className="h-4 w-4" />Calculate</LoadingButton><Button variant="outline" onClick={() => window.print()}><Printer className="h-4 w-4" /></Button><Button variant="outline" onClick={() => void downloadCsv()}><Download className="h-4 w-4" /></Button></div></div><div><p className="mb-2 text-xs font-black uppercase tracking-wide text-muted-foreground">Directions</p><div className="flex flex-wrap gap-3"><Check label="Money in" checked={statementDirections.includes("money_in")} onChange={(checked) => setStatementDirections((current) => toggle(current, "money_in", checked))} /><Check label="Money out" checked={statementDirections.includes("money_out")} onChange={(checked) => setStatementDirections((current) => toggle(current, "money_out", checked))} /></div></div><div><p className="mb-2 text-xs font-black uppercase tracking-wide text-muted-foreground">Payment methods</p><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{methods.map((method) => <Check key={method.value} label={method.label} checked={statementMethods.includes(method.value)} onChange={(checked) => setStatementMethods((current) => toggle(current, method.value, checked))} />)}</div></div></CardContent></Card>
          {statement ? <Card className="overflow-hidden rounded-3xl"><CardHeader><CardTitle>Calculated financial statement</CardTitle><CardDescription>{statement.date_from} to {statement.date_to}</CardDescription></CardHeader><CardContent className="space-y-4 p-4 sm:p-5"><div className="grid gap-3 sm:grid-cols-4"><Value label="Opening" value={formatMoney(statement.opening_balance)} /><Value label="Money in" value={formatMoney(statement.total_money_in)} /><Value label="Money out" value={formatMoney(statement.total_money_out)} /><Value label="Closing" value={formatMoney(statement.closing_balance)} emphasis /></div><div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Description</TableHead><TableHead>Channel</TableHead><TableHead>Direction</TableHead><TableHead className="text-right">Amount</TableHead></TableRow></TableHeader><TableBody>{pagedStatementEntries.length === 0 ? <EmptyRow columns={5} text="No entries match this statement." /> : pagedStatementEntries.map((entry) => <TableRow key={entry.id}><TableCell>{formatDateTime(entry.occurred_at)}</TableCell><TableCell className="font-bold">{entry.description}</TableCell><TableCell>{methodLabel(methods, entry.payment_method)}</TableCell><TableCell><Status value={entry.direction} /></TableCell><TableCell className="text-right font-black">{formatMoney(entry.amount)}</TableCell></TableRow>)}</TableBody></Table></div><DataPagination page={statementPage} pageSize={PAGE_SIZE} total={statementEntries.length} onPageChange={setStatementPage} /></CardContent></Card> : null}
        </TabsContent>

        {canAccessAccounting ? <TabsContent value="accounting"><AccountingBooksPanel businessDate={businessDate} branchId={selectedBranchId} onRefresh={reload} /></TabsContent> : null}
        {canAccessReports ? <TabsContent value="reports"><SubmissionReportsPanel branches={branches} selectedBranchId={selectedBranchId} dateFrom={statementFrom} dateTo={statementTo} onRefresh={reload} /></TabsContent> : null}

        <TabsContent value="controls" className="space-y-4">
          <div className="grid gap-5 lg:grid-cols-2"><Card className="rounded-3xl"><CardHeader><CardTitle>Financial day controls</CardTitle><CardDescription>Defaults reopen at 00:01 and submit to headquarters at 16:30 in the configured timezone.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2"><Setting label="Headquarters" value={settings?.headquarters_branch_id ? branchName(branches, settings.headquarters_branch_id) : "Not configured"} /><Setting label="Timezone" value={settings?.timezone ?? "Africa/Maseru"} /><Setting label="Automatic open" value={`${settings?.auto_open_enabled ? "Enabled" : "Disabled"} · ${settings?.auto_open_time?.slice(0, 5) ?? "00:01"}`} /><Setting label="Automatic submit" value={`${settings?.auto_submit_enabled ? "Enabled" : "Disabled"} · ${settings?.auto_submit_time?.slice(0, 5) ?? "16:30"}`} /><Setting label="Approval threshold" value={formatMoney(settings?.expense_approval_threshold ?? 0)} /><Setting label="Dual control" value={settings?.dual_control_expenses ? "Enabled" : "Disabled"} /></CardContent></Card><Card className="rounded-3xl"><CardHeader><CardTitle>Administration</CardTitle><CardDescription>Manage reusable categories and company-level accounting controls.</CardDescription></CardHeader><CardContent className="space-y-3"><Button className="w-full justify-start" variant="outline" onClick={() => setCategoryDialog(true)} disabled={!canManage}><Tags className="h-4 w-4" />Create expense category</Button><Button className="w-full justify-start" variant="outline" onClick={openSettings} disabled={!canManage}><Settings2 className="h-4 w-4" />Configure treasury</Button>{canAccessAccounting ? <Button className="w-full justify-start" variant="outline" onClick={() => setActiveTab("accounting")}><Landmark className="h-4 w-4" />Open chart of accounts and journals</Button> : null}{canAccessReports ? <Button className="w-full justify-start" variant="outline" onClick={() => setActiveTab("reports")}><FileCheck2 className="h-4 w-4" />Open submissions and stored PDFs</Button> : null}</CardContent></Card></div>
        </TabsContent>
      </Tabs>

      <CustomDialog open={entryDialog} onOpenChange={(open) => !working && setEntryDialog(open)} title={entryForm.direction === "money_in" ? "Record money in" : "Record money out"} description="The posted movement is included in the branch money book and automatically journalled in accounting.">
        <form onSubmit={saveEntry} className="space-y-5 p-6 sm:p-8">
          <div className="grid gap-4 sm:grid-cols-2"><Field label="Movement type"><Select value={entryForm.entry_type} onValueChange={(value) => { const entryType = value as TreasuryEntryType; setEntryForm((current) => ({ ...current, entry_type: entryType, expense_category_id: entryType === "expense" ? current.expense_category_id : null })); }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{entryForm.direction === "money_in" ? <><SelectItem value="manual_income">Other income</SelectItem><SelectItem value="owner_contribution">Owner contribution</SelectItem><SelectItem value="refund">Refund received</SelectItem><SelectItem value="adjustment">Positive adjustment</SelectItem><SelectItem value="other">Other money in</SelectItem></> : <><SelectItem value="expense">Operating expense</SelectItem><SelectItem value="refund">Refund paid</SelectItem><SelectItem value="adjustment">Negative adjustment</SelectItem><SelectItem value="other">Other money out</SelectItem></>}</SelectContent></Select></Field><Field label="Payment channel"><MethodSelect methods={methods} value={entryForm.payment_method} onChange={(value) => setEntryForm((current) => ({ ...current, payment_method: value }))} /></Field><Field label="Amount"><Input required type="number" min={0.01} step="0.01" value={entryForm.amount || ""} onChange={(event) => setEntryForm((current) => ({ ...current, amount: Number(event.target.value || 0) }))} /></Field><Field label="Voucher number"><Input value={entryForm.voucher_number ?? ""} onChange={(event) => setEntryForm((current) => ({ ...current, voucher_number: event.target.value }))} placeholder="EXP-0001" /></Field>{entryForm.entry_type === "expense" ? <Field label="Expense category"><Select value={entryForm.expense_category_id ?? "none"} onValueChange={(value) => setEntryForm((current) => ({ ...current, expense_category_id: value === "none" ? null : value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="none" disabled>Select category</SelectItem>{categories.filter((category) => category.is_active).map((category) => <SelectItem key={category.id} value={category.id}>{category.name}</SelectItem>)}</SelectContent></Select></Field> : null}<Field label="Transaction/proof reference"><Input value={entryForm.proof_reference ?? ""} onChange={(event) => setEntryForm((current) => ({ ...current, proof_reference: event.target.value }))} /></Field><div className="sm:col-span-2"><Field label="Description"><Textarea required minLength={3} value={entryForm.description} onChange={(event) => setEntryForm((current) => ({ ...current, description: event.target.value }))} placeholder="Describe the business purpose clearly" /></Field></div><div className="sm:col-span-2"><Field label="Proof document URL or location"><Input value={entryForm.proof_url ?? ""} onChange={(event) => setEntryForm((current) => ({ ...current, proof_url: event.target.value }))} /></Field></div></div>
          <DialogFooter><Button type="button" variant="outline" onClick={() => setEntryDialog(false)}>Cancel</Button><LoadingButton type="submit" loading={working} loadingText="Posting movement..."><BookOpenCheck className="h-4 w-4" />Save and post</LoadingButton></DialogFooter>
        </form>
      </CustomDialog>

      <CustomDialog open={sourceDialog} onOpenChange={(open) => !working && setSourceDialog(open)} title="Add opening-balance source" description="Each source keeps its own channel, reference and audit evidence.">
        <form onSubmit={saveOpeningSource} className="space-y-5 p-6 sm:p-8"><div className="grid gap-4 sm:grid-cols-2"><Field label="Source type"><Select value={sourceForm.source_type} onValueChange={(value) => setSourceForm((current) => ({ ...current, source_type: value as OpeningSourceCreate["source_type"] }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="owner_contribution">Owner contribution</SelectItem><SelectItem value="bank_float">Bank float</SelectItem><SelectItem value="cash_float">Cash float</SelectItem><SelectItem value="retained_funds">Retained funds</SelectItem><SelectItem value="opening_adjustment">Opening adjustment</SelectItem><SelectItem value="other">Other described source</SelectItem></SelectContent></Select></Field><Field label="Payment channel"><MethodSelect methods={methods} value={sourceForm.payment_method} onChange={(value) => setSourceForm((current) => ({ ...current, payment_method: value }))} /></Field><Field label="Amount"><Input required type="number" min={0.01} step="0.01" value={sourceForm.amount || ""} onChange={(event) => setSourceForm((current) => ({ ...current, amount: Number(event.target.value || 0) }))} /></Field><Field label="Source reference"><Input value={sourceForm.source_reference ?? ""} onChange={(event) => setSourceForm((current) => ({ ...current, source_reference: event.target.value }))} /></Field><div className="sm:col-span-2"><Field label="Description"><Textarea required value={sourceForm.description} onChange={(event) => setSourceForm((current) => ({ ...current, description: event.target.value }))} /></Field></div></div><DialogFooter><Button type="button" variant="outline" onClick={() => setSourceDialog(false)}>Cancel</Button><LoadingButton type="submit" loading={working}>Save source</LoadingButton></DialogFooter></form>
      </CustomDialog>

      <CustomDialog open={submitDialog} onOpenChange={(open) => !working && setSubmitDialog(open)} title="Submit branch day to headquarters" description="Submission creates an immutable numbered snapshot and a detailed PDF in LoanHub Files.">
        <form onSubmit={submitDay} className="space-y-5 p-6 sm:p-8"><div className="grid gap-3 sm:grid-cols-2"><Value label="Expected closing" value={formatMoney(ledger?.expected_closing_balance ?? 0)} emphasis /><Value label="Pending entries" value={String(ledger?.pending_entry_count ?? 0)} /></div><Field label="Declared closing balance"><Input type="number" min={0} step="0.01" value={declaredClosing} onChange={(event) => setDeclaredClosing(event.target.value)} placeholder={String(ledger?.expected_closing_balance ?? 0)} /></Field><Field label="Submission notes"><Textarea value={submissionNotes} onChange={(event) => setSubmissionNotes(event.target.value)} placeholder="Cash count, handover details or variance explanation" /></Field><DialogFooter><Button type="button" variant="outline" onClick={() => setSubmitDialog(false)}>Cancel</Button><LoadingButton type="submit" loading={working}><Send className="h-4 w-4" />Submit and create PDF</LoadingButton></DialogFooter></form>
      </CustomDialog>

      <CustomDialog open={reopenDialog} onOpenChange={(open) => !working && setReopenDialog(open)} title="Reopen submitted branch day" description="The previous submission remains immutable. A corrected submission receives a new sequence number.">
        <form onSubmit={reopenDay} className="space-y-5 p-6 sm:p-8"><Field label="Mandatory reason"><Textarea required minLength={8} value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} placeholder="Late verified expense received after automatic submission" /></Field><DialogFooter><Button type="button" variant="outline" onClick={() => setReopenDialog(false)}>Cancel</Button><LoadingButton type="submit" loading={working}><RotateCcw className="h-4 w-4" />Reopen day</LoadingButton></DialogFooter></form>
      </CustomDialog>

      <CustomDialog open={Boolean(decisionEntry)} onOpenChange={(open) => !working && !open && setDecisionEntry(null)} title={`${titleCase(decisionMode)} expense`} description={decisionEntry?.description}>
        <form onSubmit={decideEntry} className="space-y-5 p-6 sm:p-8"><Value label="Amount" value={formatMoney(decisionEntry?.amount ?? 0)} emphasis /><Field label={decisionMode === "reject" ? "Rejection reason" : "Approval note"}><Textarea required={decisionMode === "reject"} value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} /></Field><DialogFooter><Button type="button" variant="outline" onClick={() => setDecisionEntry(null)}>Cancel</Button><LoadingButton type="submit" loading={working} variant={decisionMode === "reject" ? "destructive" : "default"}>{decisionMode === "reject" ? <XCircle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}{titleCase(decisionMode)}</LoadingButton></DialogFooter></form>
      </CustomDialog>

      <CustomDialog open={transferDialog} onOpenChange={(open) => !working && setTransferDialog(open)} title="Issue headquarters funding" description="The receiving branch must confirm receipt before it becomes opening balance.">
        <form onSubmit={saveTransfer} className="space-y-5 p-6 sm:p-8"><div className="grid gap-4 sm:grid-cols-2"><Field label="Target branch"><Select value={transferForm.target_branch_id || "none"} onValueChange={(value) => setTransferForm((current) => ({ ...current, target_branch_id: value === "none" ? "" : value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="none" disabled>Select branch</SelectItem>{branches.filter((branch) => branch.id !== settings?.headquarters_branch_id).map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}</SelectItem>)}</SelectContent></Select></Field><Field label="Amount"><Input required type="number" min={0.01} step="0.01" value={transferForm.amount || ""} onChange={(event) => setTransferForm((current) => ({ ...current, amount: Number(event.target.value || 0) }))} /></Field><Field label="Channel"><MethodSelect methods={methods} value={transferForm.payment_method} onChange={(value) => setTransferForm((current) => ({ ...current, payment_method: value }))} /></Field><Field label="Proof reference"><Input value={transferForm.proof_reference} onChange={(event) => setTransferForm((current) => ({ ...current, proof_reference: event.target.value }))} /></Field><div className="sm:col-span-2"><Field label="Notes"><Textarea value={transferForm.notes} onChange={(event) => setTransferForm((current) => ({ ...current, notes: event.target.value }))} /></Field></div></div><DialogFooter><Button type="button" variant="outline" onClick={() => setTransferDialog(false)}>Cancel</Button><LoadingButton type="submit" loading={working}>Issue funding</LoadingButton></DialogFooter></form>
      </CustomDialog>

      <CustomDialog open={categoryDialog} onOpenChange={(open) => !working && setCategoryDialog(open)} title="Create expense category"><form onSubmit={saveCategory} className="space-y-5 p-6 sm:p-8"><Field label="Category name"><Input required value={categoryForm.name} onChange={(event) => setCategoryForm((current) => ({ ...current, name: event.target.value }))} placeholder="Airtime and communication" /></Field><Field label="Description"><Textarea value={categoryForm.description} onChange={(event) => setCategoryForm((current) => ({ ...current, description: event.target.value }))} /></Field><DialogFooter><Button type="button" variant="outline" onClick={() => setCategoryDialog(false)}>Cancel</Button><LoadingButton type="submit" loading={working}>Create category</LoadingButton></DialogFooter></form></CustomDialog>

      <CustomDialog open={settingsDialog} onOpenChange={(open) => !working && setSettingsDialog(open)} title="Configure branch treasury" description="Use Africa/Maseru unless the company operates in another timezone.">
        {settingsForm ? <form onSubmit={saveSettings} className="space-y-5 p-6 sm:p-8"><div className="grid gap-4 sm:grid-cols-2"><Field label="Headquarters branch"><Select value={settingsForm.headquarters_branch_id ?? "none"} onValueChange={(value) => setSettingsForm((current) => current ? ({ ...current, headquarters_branch_id: value === "none" ? null : value }) : current)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="none">Not configured</SelectItem>{branches.map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}</SelectItem>)}</SelectContent></Select></Field><Field label="Timezone"><Input value={settingsForm.timezone} onChange={(event) => setSettingsForm((current) => current ? ({ ...current, timezone: event.target.value }) : current)} /></Field><Field label="Open new day at"><Input type="time" value={settingsForm.auto_open_time.slice(0, 5)} onChange={(event) => setSettingsForm((current) => current ? ({ ...current, auto_open_time: `${event.target.value}:00` }) : current)} /></Field><Field label="Submit to HQ at"><Input type="time" value={settingsForm.auto_submit_time.slice(0, 5)} onChange={(event) => setSettingsForm((current) => current ? ({ ...current, auto_submit_time: `${event.target.value}:00` }) : current)} /></Field><Field label="Expense approval threshold"><Input type="number" min={0} step="0.01" value={settingsForm.expense_approval_threshold} onChange={(event) => setSettingsForm((current) => current ? ({ ...current, expense_approval_threshold: Number(event.target.value || 0) }) : current)} /></Field></div><div className="grid gap-3 rounded-2xl border p-4 sm:grid-cols-2"><SwitchLine label="Automatic daily opening" checked={settingsForm.auto_open_enabled} onChange={(value) => setSettingsForm((current) => current ? ({ ...current, auto_open_enabled: value }) : current)} /><SwitchLine label="Automatic HQ submission" checked={settingsForm.auto_submit_enabled} onChange={(value) => setSettingsForm((current) => current ? ({ ...current, auto_submit_enabled: value }) : current)} /><SwitchLine label="Require non-cash proof" checked={settingsForm.require_proof_for_non_cash} onChange={(value) => setSettingsForm((current) => current ? ({ ...current, require_proof_for_non_cash: value }) : current)} /><SwitchLine label="Allow branch-manager reopen" checked={settingsForm.allow_branch_reopen} onChange={(value) => setSettingsForm((current) => current ? ({ ...current, allow_branch_reopen: value }) : current)} /><SwitchLine label="Dual control for qualifying expenses" checked={settingsForm.dual_control_expenses} onChange={(value) => setSettingsForm((current) => current ? ({ ...current, dual_control_expenses: value }) : current)} /></div><DialogFooter><Button type="button" variant="outline" onClick={() => setSettingsDialog(false)}>Cancel</Button><LoadingButton type="submit" loading={working}>Save controls</LoadingButton></DialogFooter></form> : null}
      </CustomDialog>
    </div>
  );
}

function toSettingsUpdate(settings: TreasurySettings): TreasurySettingsUpdate {
  return {
    headquarters_branch_id: settings.headquarters_branch_id,
    currency: settings.currency,
    timezone: settings.timezone,
    auto_open_enabled: settings.auto_open_enabled,
    auto_open_time: settings.auto_open_time,
    auto_submit_enabled: settings.auto_submit_enabled,
    auto_submit_time: settings.auto_submit_time,
    require_proof_for_non_cash: settings.require_proof_for_non_cash,
    allow_branch_reopen: settings.allow_branch_reopen,
    expense_approval_threshold: Number(settings.expense_approval_threshold),
    dual_control_expenses: settings.dual_control_expenses,
  };
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function Metric({ icon: Icon, label, value, hint }: { icon: typeof Banknote; label: string; value: string; hint: string }) {
  return <Card className="rounded-3xl bg-gradient-to-br from-card to-primary/5"><CardContent className="flex gap-4 p-5"><div className="rounded-2xl bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5" /></div><div><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-black">{value}</p><p className="mt-1 text-xs text-muted-foreground">{hint}</p></div></CardContent></Card>;
}

function SourceMini({ label, value }: { label: string; value: number }) {
  return <div className="rounded-2xl border bg-muted/20 p-4"><p className="text-xs font-black uppercase text-muted-foreground">{label}</p><p className="mt-2 text-xl font-black">{formatMoney(value)}</p></div>;
}

function IntegrityMetric({ label, value, hint, alert = false }: { label: string; value: number; hint: string; alert?: boolean }) {
  return <Card className={`rounded-2xl ${alert ? "border-destructive/40 bg-destructive/5" : "bg-muted/10"}`}><CardContent className="p-4"><p className="text-[11px] font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p><p className={`mt-1 text-2xl font-black ${alert ? "text-destructive" : ""}`}>{value}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{hint}</p></CardContent></Card>;
}

function Setting({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border p-3"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 font-bold">{value}</p></div>;
}

function Value({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return <div className="rounded-2xl border bg-background/70 p-3"><p className="text-[11px] font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p><p className={`mt-1 font-black ${emphasis ? "text-xl text-primary" : "text-base"}`}>{value}</p></div>;
}

function Status({ value }: { value: string }) {
  const destructive = ["rejected", "voided"].includes(value);
  const good = ["open", "reopened", "posted", "approved", "confirmed", "received", "reviewed"].includes(value);
  return <Badge variant={destructive ? "destructive" : good ? "default" : "secondary"}>{titleCase(value)}</Badge>;
}

function EmptyRow({ columns, text }: { columns: number; text: string }) {
  return <TableRow><TableCell colSpan={columns} className="h-36 text-center text-muted-foreground">{text}</TableCell></TableRow>;
}

function methodLabel(methods: PaymentMethodOption[], value: PaymentMethod) {
  return methods.find((item) => item.value === value)?.label ?? titleCase(value);
}

function branchName(branches: Array<{ id: string; name: string }>, id: string) {
  return branches.find((item) => item.id === id)?.name ?? id.slice(0, 8);
}

function MethodSelect({ methods, value, onChange }: { methods: PaymentMethodOption[]; value: PaymentMethod; onChange: (value: PaymentMethod) => void }) {
  return <Select value={value} onValueChange={(next: PaymentMethod) => onChange(next)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{methods.map((method) => <SelectItem key={method.value} value={method.value}>{method.label}</SelectItem>)}</SelectContent></Select>;
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex items-center gap-2 text-sm font-semibold"><Checkbox checked={checked} onCheckedChange={(value) => onChange(value === true)} />{label}</label>;
}

function SwitchLine({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex items-center justify-between gap-3 text-sm font-semibold"><span>{label}</span><Switch checked={checked} onCheckedChange={onChange} /></label>;
}

function toggle<T>(values: T[], value: T, enabled: boolean): T[] {
  return enabled ? Array.from(new Set([...values, value])) : values.filter((item) => item !== value);
}
