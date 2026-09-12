"use client";

import Link from "next/link";
import {
  Banknote,
  CalendarCheck2,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Download,
  FileWarning,
  FilterX,
  FolderOpen,
  Gavel,
  HandCoins,
  Maximize2,
  MessageSquareText,
  Minimize2,
  MapPin,
  PanelLeftClose,
  PanelLeftOpen,
  PhoneCall,
  Plus,
  RefreshCcw,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { branchApi } from "@/api/branch";
import { collectionsApi } from "@/api/collections";
import { downloadManagedFile } from "@/api/files";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { Branch } from "@/types/branch";
import type {
  CollectionAction,
  CollectionActionType,
  CollectionDailyReport,
  CollectionsWorkspace,
  CollectionWorkspaceCase,
} from "@/types/collections";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const PAGE_SIZES = [15, 30, 50, 100] as const;

type DpdBand = "all" | "current" | "1_7" | "8_30" | "31_60" | "61_90" | "91_plus";
type FollowUpFilter = "all" | "overdue" | "today" | "next_7" | "scheduled" | "none";
type ContactFilter = "all" | "has_phone" | "no_phone" | "has_address" | "no_address" | "has_kin" | "no_kin" | "has_email" | "no_email";
type BankFilter = "all" | "banked" | "unbanked" | "salary" | "non_salary";
type LegalFilter = "all" | "legal" | "pre_legal" | "handed_over" | "not_legal";
type ActivityFilter = "all" | "none" | CollectionActionType;
type PromiseFilter = "all" | "none" | "pending" | "kept" | "broken";
type SortOption = "dpd_high" | "dpd_low" | "overdue_high" | "overdue_low" | "balance_high" | "balance_low" | "next_action" | "latest" | "oldest" | "borrower";

type CollectionFilters = {
  status: string;
  stage: string;
  priority: string;
  branchId: string;
  loanStatus: string;
  dpdBand: DpdBand;
  followUp: FollowUpFilter;
  contact: ContactFilter;
  banking: BankFilter;
  legal: LegalFilter;
  activity: ActivityFilter;
  promise: PromiseFilter;
  overdueMin: string;
  overdueMax: string;
  balanceMin: string;
  balanceMax: string;
  createdFrom: string;
  createdTo: string;
  sortBy: SortOption;
};

const DEFAULT_FILTERS: CollectionFilters = {
  status: "all",
  stage: "all",
  priority: "all",
  branchId: "all",
  loanStatus: "all",
  dpdBand: "all",
  followUp: "all",
  contact: "all",
  banking: "all",
  legal: "all",
  activity: "all",
  promise: "all",
  overdueMin: "",
  overdueMax: "",
  balanceMin: "",
  balanceMax: "",
  createdFrom: "",
  createdTo: "",
  sortBy: "dpd_high",
};

const yesterday = () => {
  const value = new Date();
  value.setDate(value.getDate() - 1);
  return value.toISOString().slice(0, 10);
};

function uniqueStrings(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value?.trim()))))
    .sort((left, right) => left.localeCompare(right));
}

function isoDay(value: string | null | undefined) {
  return value ? value.slice(0, 10) : "";
}

function localDay(value = new Date()) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function parseDay(value: string) {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day);
}

function addDays(value: Date, days: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
}

function sameDay(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function numberRange(value: number, minimum: string, maximum: string) {
  const min = minimum.trim() ? Number(minimum) : null;
  const max = maximum.trim() ? Number(maximum) : null;
  if (min !== null && Number.isFinite(min) && value < min) return false;
  if (max !== null && Number.isFinite(max) && value > max) return false;
  return true;
}

function dateRange(value: string | null | undefined, from: string, to: string) {
  if (!from && !to) return true;
  if (!value) return false;
  const day = isoDay(value);
  if (from && day < from) return false;
  if (to && day > to) return false;
  return true;
}

function followUpMatches(value: string | null, filter: FollowUpFilter) {
  if (filter === "all") return true;
  if (filter === "none") return !value;
  if (!value) return false;
  const followUp = parseDay(value);
  const today = localDay();
  if (filter === "overdue") return followUp < today;
  if (filter === "today") return sameDay(followUp, today);
  if (filter === "next_7") return followUp >= today && followUp <= addDays(today, 7);
  return true;
}

function dpdMatches(days: number, filter: DpdBand) {
  if (filter === "all") return true;
  if (filter === "current") return days <= 0;
  if (filter === "1_7") return days >= 1 && days <= 7;
  if (filter === "8_30") return days >= 8 && days <= 30;
  if (filter === "31_60") return days >= 31 && days <= 60;
  if (filter === "61_90") return days >= 61 && days <= 90;
  return days >= 91;
}

function compareOptionalDate(left: string | null, right: string | null) {
  if (!left && !right) return 0;
  if (!left) return 1;
  if (!right) return -1;
  return left.localeCompare(right);
}

function sortCases(left: CollectionWorkspaceCase, right: CollectionWorkspaceCase, sortBy: SortOption) {
  switch (sortBy) {
    case "dpd_low": return left.days_past_due - right.days_past_due;
    case "overdue_high": return right.overdue_amount - left.overdue_amount;
    case "overdue_low": return left.overdue_amount - right.overdue_amount;
    case "balance_high": return right.outstanding_balance - left.outstanding_balance;
    case "balance_low": return left.outstanding_balance - right.outstanding_balance;
    case "next_action": return compareOptionalDate(left.next_action_at, right.next_action_at);
    case "latest": return compareOptionalDate(right.created_at, left.created_at);
    case "oldest": return compareOptionalDate(left.created_at, right.created_at);
    case "borrower": return left.borrower_name.localeCompare(right.borrower_name);
    case "dpd_high":
    default: return right.days_past_due - left.days_past_due || right.overdue_amount - left.overdue_amount;
  }
}

function metadataText(action: CollectionAction | null) {
  if (!action) return "";
  return Object.values(action.metadata_json ?? {}).filter(Boolean).join(" ");
}

export default function CollectionsPage() {
  const [workspace, setWorkspace] = useState<CollectionsWorkspace | null>(null);
  const [reports, setReports] = useState<CollectionDailyReport[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<CollectionFilters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(15);
  const [queueFullscreen, setQueueFullscreen] = useState(false);
  const [filtersCollapsed, setFiltersCollapsed] = useState(false);

  const [selectedCase, setSelectedCase] = useState<CollectionWorkspaceCase | null>(null);
  const [actions, setActions] = useState<CollectionAction[]>([]);
  const [caseOpen, setCaseOpen] = useState(false);
  const [actionOpen, setActionOpen] = useState(false);
  const [actionType, setActionType] = useState<CollectionActionType>("call");
  const [customActionTitle, setCustomActionTitle] = useState("");
  const [outcome, setOutcome] = useState("");
  const [notes, setNotes] = useState("");
  const [followUpAt, setFollowUpAt] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [visitedAddress, setVisitedAddress] = useState("");
  const [courtDate, setCourtDate] = useState("");
  const [courtName, setCourtName] = useState("");
  const [courtCaseNumber, setCourtCaseNumber] = useState("");
  const [promiseAmount, setPromiseAmount] = useState("");
  const [promiseDate, setPromiseDate] = useState("");
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([]);

  const load = useCallback(async (showToast = false) => {
    setLoading(true);
    try {
      const syncResult = await collectionsApi.sync();
      const [workspaceData, reportData, branchResponse] = await Promise.all([
        collectionsApi.workspace(),
        collectionsApi.listDailyReports(),
        branchApi.getAll(),
      ]);
      setWorkspace(workspaceData);
      setReports(reportData);
      setBranches(branchResponse.data);
      if (showToast) toast.success(syncResult.message);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Collections workspace could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 50);
    return () => window.clearTimeout(timer);
  }, [load]);

  const branchById = useMemo(() => new Map(branches.map((branch) => [branch.id, branch])), [branches]);
  const cases = workspace?.cases ?? [];

  const optionSets = useMemo(() => ({
    statuses: uniqueStrings(cases.map((item) => item.status)),
    stages: uniqueStrings(cases.map((item) => item.stage)),
    priorities: uniqueStrings(cases.map((item) => item.priority)),
    loanStatuses: uniqueStrings(cases.map((item) => item.loan_status)),
    branchIds: uniqueStrings(cases.map((item) => item.branch_id)),
  }), [cases]);

  const filteredCases = useMemo(() => {
    const query = search.trim().toLowerCase();
    return cases
      .filter((item) => {
        if (query) {
          const haystack = [
            item.borrower_name,
            item.loan_reference,
            item.case_reference,
            item.borrower_id,
            item.loan_id,
            item.phone,
            item.email,
            item.physical_address,
            ...item.next_of_kin_phones,
            ...item.emergency_contact_phones,
            item.bank_name,
            item.bank_account_holder,
            item.bank_account_last4,
            item.masked_bank_account,
            item.status,
            item.stage,
            item.priority,
            item.loan_status,
            item.promise_status,
            item.notes,
            item.last_action?.activity_type,
            item.last_action?.outcome,
            item.last_action?.notes,
            metadataText(item.last_action),
            item.branch_id ? branchById.get(item.branch_id)?.name : null,
            item.branch_id ? branchById.get(item.branch_id)?.district : null,
          ].filter(Boolean).join(" ").toLowerCase();
          if (!haystack.includes(query)) return false;
        }

        if (filters.status !== "all" && item.status !== filters.status) return false;
        if (filters.stage !== "all" && item.stage !== filters.stage) return false;
        if (filters.priority !== "all" && item.priority !== filters.priority) return false;
        if (filters.branchId !== "all" && (item.branch_id ?? "") !== filters.branchId) return false;
        if (filters.loanStatus !== "all" && item.loan_status !== filters.loanStatus) return false;
        if (!dpdMatches(item.days_past_due, filters.dpdBand)) return false;
        if (!followUpMatches(item.next_action_at, filters.followUp)) return false;

        if (filters.contact === "has_phone" && !item.phone) return false;
        if (filters.contact === "no_phone" && item.phone) return false;
        if (filters.contact === "has_address" && !item.physical_address) return false;
        if (filters.contact === "no_address" && item.physical_address) return false;
        if (filters.contact === "has_kin" && !item.next_of_kin_phones.length && !item.emergency_contact_phones.length) return false;
        if (filters.contact === "no_kin" && (item.next_of_kin_phones.length > 0 || item.emergency_contact_phones.length > 0)) return false;
        if (filters.contact === "has_email" && !item.email) return false;
        if (filters.contact === "no_email" && item.email) return false;

        if (filters.banking === "banked" && !item.bank_name && !item.bank_account_last4) return false;
        if (filters.banking === "unbanked" && (item.bank_name || item.bank_account_last4)) return false;
        if (filters.banking === "salary" && !item.salary_account) return false;
        if (filters.banking === "non_salary" && item.salary_account) return false;

        if (filters.legal === "legal" && item.stage !== "legal" && item.status !== "legal") return false;
        if (filters.legal === "pre_legal" && item.stage !== "pre_legal") return false;
        if (filters.legal === "handed_over" && !item.legal_handover_at) return false;
        if (filters.legal === "not_legal" && (item.stage === "legal" || item.status === "legal" || item.legal_handover_at)) return false;

        if (filters.activity === "none" && item.last_action) return false;
        if (filters.activity !== "all" && filters.activity !== "none" && item.last_action?.activity_type !== filters.activity) return false;
        if (filters.promise === "none" && item.promise_status) return false;
        if (filters.promise !== "all" && filters.promise !== "none" && item.promise_status !== filters.promise) return false;

        if (!numberRange(item.overdue_amount, filters.overdueMin, filters.overdueMax)) return false;
        if (!numberRange(item.outstanding_balance, filters.balanceMin, filters.balanceMax)) return false;
        if (!dateRange(item.created_at, filters.createdFrom, filters.createdTo)) return false;
        return true;
      })
      .sort((left, right) => sortCases(left, right, filters.sortBy));
  }, [branchById, cases, filters, search]);

  const totalPages = Math.max(1, Math.ceil(filteredCases.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const visibleCases = filteredCases.slice(pageStart, pageStart + pageSize);
  const pageEnd = Math.min(pageStart + pageSize, filteredCases.length);

  const filteredOverdue = useMemo(() => filteredCases.reduce((sum, item) => sum + Number(item.overdue_amount || 0), 0), [filteredCases]);
  const filteredBalance = useMemo(() => filteredCases.reduce((sum, item) => sum + Number(item.outstanding_balance || 0), 0), [filteredCases]);
  const legalCount = useMemo(() => filteredCases.filter((item) => item.stage === "legal" || item.status === "legal").length, [filteredCases]);
  const promiseCount = useMemo(() => filteredCases.filter((item) => item.promise_status === "pending").length, [filteredCases]);
  const followUpDueCount = useMemo(() => filteredCases.filter((item) => followUpMatches(item.next_action_at, "overdue") || followUpMatches(item.next_action_at, "today")).length, [filteredCases]);

  const activeFilterCount = useMemo(() => {
    let count = search.trim() ? 1 : 0;
    (Object.keys(DEFAULT_FILTERS) as Array<keyof CollectionFilters>).forEach((key) => {
      if (filters[key] !== DEFAULT_FILTERS[key]) count += 1;
    });
    return count;
  }, [filters, search]);

  function updateFilter<K extends keyof CollectionFilters>(key: K, value: CollectionFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function changeSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function changePageSize(value: number) {
    setPageSize(value);
    setPage(1);
  }

  function clearFilters() {
    setSearch("");
    setFilters(DEFAULT_FILTERS);
    setPage(1);
  }

  function quickFilter(kind: "open" | "urgent" | "legal" | "follow_up" | "promise" | "no_action") {
    setFilters({ ...DEFAULT_FILTERS });
    setSearch("");
    if (kind === "open") setFilters((current) => ({ ...current, status: "open" }));
    if (kind === "urgent") setFilters((current) => ({ ...current, priority: "urgent" }));
    if (kind === "legal") setFilters((current) => ({ ...current, legal: "legal" }));
    if (kind === "follow_up") setFilters((current) => ({ ...current, followUp: "overdue" }));
    if (kind === "promise") setFilters((current) => ({ ...current, promise: "pending" }));
    if (kind === "no_action") setFilters((current) => ({ ...current, activity: "none" }));
    setPage(1);
  }

  async function openCase(item: CollectionWorkspaceCase) {
    setSelectedCase(item);
    setCaseOpen(true);
    try {
      setActions(await collectionsApi.listActions(item.id));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Collection actions could not be loaded."));
    }
  }

  async function startAction(type: CollectionActionType) {
    if (!selectedCase) return;
    setWorking(true);
    try {
      await collectionsApi.claimCase(selectedCase.id);
      setActionType(type);
      setCustomActionTitle("");
      setOutcome("");
      setNotes("");
      setFollowUpAt("");
      setContactPhone(selectedCase.phone ?? "");
      setVisitedAddress(selectedCase.physical_address ?? "");
      setCourtDate("");
      setCourtName("");
      setCourtCaseNumber("");
      setPromiseAmount(selectedCase.overdue_amount > 0 ? String(selectedCase.overdue_amount) : "");
      setPromiseDate("");
      setEvidenceFiles([]);
      setActionOpen(true);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "This recovery case could not be claimed for action."));
    } finally {
      setWorking(false);
    }
  }

  async function closeActionDialog() {
    setActionOpen(false);
    if (!selectedCase) return;
    try { await collectionsApi.releaseCase(selectedCase.id); } catch { /* claim expires automatically */ }
  }

  async function saveAction() {
    if (!selectedCase) return;
    setWorking(true);
    try {
      const created = await collectionsApi.createAction(selectedCase.id, {
        actionType,
        customActionTitle,
        outcome,
        notes,
        followUpAt: followUpAt || null,
        contactPhone,
        visitedAddress,
        courtDate,
        courtName,
        courtCaseNumber,
        promiseAmount: promiseAmount.trim() ? Number(promiseAmount) : null,
        promiseDate: promiseDate || null,
        files: evidenceFiles,
      });
      setActions((current) => [created, ...current]);
      setActionOpen(false);
      toast.success("Collection action recorded");
      await load();
      const refreshed = (await collectionsApi.workspace()).cases.find((item) => item.id === selectedCase.id);
      if (refreshed) setSelectedCase(refreshed);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The collection action could not be recorded."));
    } finally {
      setWorking(false);
    }
  }

  async function runYesterdayReport() {
    setWorking(true);
    try {
      const result = await collectionsApi.runDailyReport(yesterday());
      toast.success(result.message);
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The missed-payment report could not be generated."));
    } finally {
      setWorking(false);
    }
  }

  const queueHeader = (
    <div className="border-b bg-background/95">
      <div className="flex flex-col gap-3 px-4 py-3 sm:px-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <ShieldAlert className="h-4 w-4" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-black">Recovery queue</p>
                <Badge variant="secondary" className="rounded-full">{filteredCases.length} matching</Badge>
                {activeFilterCount ? <Badge variant="outline" className="rounded-full">{activeFilterCount} active filter{activeFilterCount === 1 ? "" : "s"}</Badge> : null}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">Prioritise arrears, promises, follow-ups and legal escalation from one queue.</p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button size="sm" variant="outline" className="rounded-full" onClick={() => quickFilter("open")}>Open</Button>
          <Button size="sm" variant="outline" className="rounded-full" onClick={() => quickFilter("urgent")}>Urgent</Button>
          <Button size="sm" variant="outline" className="rounded-full" onClick={() => quickFilter("follow_up")}>Follow-up due</Button>
          <Button size="sm" variant="outline" className="rounded-full" onClick={() => quickFilter("promise")}>Promises</Button>
          <Button size="sm" variant="outline" className="rounded-full" onClick={() => quickFilter("legal")}>Legal</Button>
          <Button size="sm" variant="outline" className="rounded-full" onClick={() => quickFilter("no_action")}>No action</Button>
        </div>
      </div>

      <div className="grid gap-2 border-t bg-muted/10 px-4 py-3 sm:px-5 lg:grid-cols-[minmax(0,1fr)_180px_180px_auto]">
        <div className="relative min-w-0">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => changeSearch(event.target.value)}
            placeholder="Search borrower, loan, case, phone, address, bank or branch..."
            className="h-10 rounded-xl bg-background pl-9"
          />
        </div>
        <NativeSelect value={filters.status} onChange={(event) => updateFilter("status", event.target.value)} className="h-10 rounded-xl bg-background">
          <option value="all">All statuses</option>
          {optionSets.statuses.map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
        </NativeSelect>
        <NativeSelect value={filters.stage} onChange={(event) => updateFilter("stage", event.target.value)} className="h-10 rounded-xl bg-background">
          <option value="all">All stages</option>
          {optionSets.stages.map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
        </NativeSelect>
        <div className="flex items-center gap-2">
          {activeFilterCount ? <Button size="sm" variant="ghost" className="h-10 rounded-xl" onClick={clearFilters}><FilterX className="h-4 w-4" />Clear</Button> : null}
          <Button size="sm" className="h-10 rounded-xl" onClick={() => setQueueFullscreen(true)}><Maximize2 className="h-4 w-4" />Full queue</Button>
        </div>
      </div>
    </div>
  );

  return (
    <main className="flex min-h-[calc(100dvh-1.5rem)] flex-col gap-4 rounded-[1.75rem] border bg-gradient-to-b from-background via-background to-muted/10 p-4 shadow-sm sm:p-5">
      <section className="overflow-hidden rounded-[1.5rem] border bg-[radial-gradient(circle_at_top_right,hsl(var(--primary)/0.12),transparent_32%),linear-gradient(135deg,hsl(var(--background)),hsl(var(--muted)/0.24))] shadow-sm">
        <div className="flex flex-col gap-5 p-5 xl:flex-row xl:items-start xl:justify-between xl:p-6">
          <div className="min-w-0 max-w-4xl">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="rounded-full bg-background/80 px-3 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                Collections & legal control
              </Badge>
              <Badge variant="secondary" className="rounded-full">Live arrears workspace</Badge>
            </div>
            <h1 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl xl:text-[2rem]">Collections recovery centre</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              See who needs attention, what is overdue, which promise is at risk, and the next recovery step. Every action stays attached to the case as evidence.
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button asChild variant="outline" className="rounded-xl bg-background/80"><Link href="/company/collections/maturity"><CalendarClock className="h-4 w-4" />Maturity renewals</Link></Button>
            <Button variant="outline" className="rounded-xl bg-background/80" onClick={() => void load(true)} disabled={loading || working}>
              <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Sync arrears
            </Button>
            <Button className="rounded-xl" onClick={() => void runYesterdayReport()} disabled={working}>
              <FileWarning className="h-4 w-4" />Yesterday report
            </Button>
          </div>
        </div>

        <div className="grid border-t bg-background/65 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard icon={ShieldAlert} label="Cases in view" value={String(filteredCases.length)} note={`${workspace?.summary.open_cases ?? 0} open in portfolio`} tone="primary" />
          <MetricCard icon={HandCoins} label="Overdue exposure" value={formatMoney(filteredOverdue)} note={`${formatMoney(filteredBalance)} outstanding`} tone="danger" />
          <MetricCard icon={CalendarClock} label="Follow-up due" value={String(followUpDueCount)} note="Overdue or due today" tone="warning" />
          <MetricCard icon={CalendarCheck2} label="Promises pending" value={String(promiseCount)} note="Commitments still open" tone="success" />
          <MetricCard icon={Gavel} label="Legal cases" value={String(legalCount)} note="Pre-legal and court control" tone="neutral" />
        </div>
      </section>

      <Tabs defaultValue="cases" className="flex min-h-0 flex-1 flex-col gap-3">
        <div className="flex flex-col gap-2 rounded-2xl border bg-background p-2 shadow-sm md:flex-row md:items-center md:justify-between">
          <TabsList className="h-10 justify-start rounded-xl bg-muted/60 p-1">
            <TabsTrigger value="cases" className="rounded-lg px-4">Recovery queue</TabsTrigger>
            <TabsTrigger value="reports" className="rounded-lg px-4">Daily reports</TabsTrigger>
            <TabsTrigger value="court" className="rounded-lg px-4">Court diary</TabsTrigger>
          </TabsList>
          <div className="flex flex-wrap items-center gap-2 px-1 text-xs text-muted-foreground">
            <span>Filtered exposure</span>
            <span className="font-black text-foreground">{formatMoney(filteredOverdue)}</span>
            <span className="hidden sm:inline">•</span>
            <span>{filteredCases.length} case{filteredCases.length === 1 ? "" : "s"}</span>
          </div>
        </div>

        <TabsContent value="cases" className="mt-0 min-h-0 flex-1">
          <Card className="flex min-h-[420px] h-full flex-col overflow-visible rounded-[1.5rem] border shadow-sm">
            <StickyFilterBar
              ariaLabel="Collections recovery queue search and filters"
              className="rounded-t-[1.5rem] data-[floating=true]:rounded-2xl data-[floating=true]:border"
            >
              {queueHeader}
            </StickyFilterBar>
            <CardContent className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-b-[1.5rem] p-0">
              <div className="min-h-0 flex-1 overflow-auto">
                <RecoveryTable rows={visibleCases} loading={loading} branchById={branchById} onOpenCase={openCase} sticky />
              </div>
              <PaginationFooter
                total={filteredCases.length}
                start={filteredCases.length ? pageStart + 1 : 0}
                end={pageEnd}
                currentPage={safePage}
                totalPages={totalPages}
                pageSize={pageSize}
                onPageSizeChange={changePageSize}
                onPrevious={() => setPage((current) => Math.max(1, current - 1))}
                onNext={() => setPage((current) => Math.min(totalPages, current + 1))}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reports" className="mt-0 min-h-0 flex-1 overflow-auto">
          <Card className="rounded-[1.5rem] shadow-sm">
            <CardHeader className="border-b bg-muted/10">
              <CardTitle className="flex items-center gap-2"><FileWarning className="h-5 w-5 text-primary" />Daily missed-payment reports</CardTitle>
              <CardDescription>
                Confidential snapshots of missed instalments. The scheduled cycle synchronises arrears, produces PDFs and posts the result to the restricted collections conversation.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 p-4 lg:grid-cols-2 2xl:grid-cols-3">
              {reports.map((report) => (
                <div key={report.id} className="rounded-2xl border bg-background p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-bold">{report.title}</p>
                      <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{report.reference}</p>
                    </div>
                    <Badge variant="outline" className="rounded-full">{report.scope_type}</Badge>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                    <Info label="Due date" value={formatDate(report.period_end)} />
                    <Info label="Borrowers" value={String(report.metrics.row_count ?? 0)} />
                    <Info label="Shortfall" value={formatMoney(Number(report.metrics.total_shortfall ?? 0))} />
                    <Info label="Recipients" value={String(report.metrics.recipient_count ?? 0)} />
                  </div>
                  {report.file ? (
                    <Button className="mt-4 w-full rounded-xl" variant="outline" onClick={() => void downloadManagedFile(report.file!)}>
                      <Download className="h-4 w-4" />Download confidential PDF
                    </Button>
                  ) : null}
                </div>
              ))}
              {!reports.length ? <EmptyState icon={FileWarning} title="No reports yet" description="Scheduled or manual report generation will place confidential missed-payment reports here." /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="court" className="mt-0 min-h-0 flex-1 overflow-auto">
          <Card className="rounded-[1.5rem] shadow-sm">
            <CardHeader className="border-b bg-muted/10">
              <CardTitle className="flex items-center gap-2"><Gavel className="h-5 w-5 text-primary" />Court diary</CardTitle>
              <CardDescription>Upcoming hearings recorded against recovery cases, including court and case references.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {(workspace?.upcoming_court ?? []).map((item) => (
                <div key={item.activity_id} className="rounded-2xl border bg-background p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-bold">{item.borrower_name ?? "Borrower"}</p>
                      <p className="truncate font-mono text-xs text-primary">{item.loan_reference}</p>
                    </div>
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><Gavel className="h-4 w-4" /></div>
                  </div>
                  <p className="mt-4 text-lg font-black">{formatDate(item.court_date)}</p>
                  <p className="mt-1 text-sm">{item.court_name ?? "Court not recorded"}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Case: {item.court_case_number ?? "Not recorded"}</p>
                </div>
              ))}
              {!(workspace?.upcoming_court ?? []).length ? <EmptyState icon={Gavel} title="No upcoming court dates" description="Future court actions will appear here automatically when a hearing date is recorded." /> : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={queueFullscreen} onOpenChange={setQueueFullscreen}>
        <DialogContent className="flex h-[98dvh] max-h-[98dvh] w-[99vw] max-w-[99vw] flex-col gap-0 overflow-hidden rounded-2xl p-0 sm:max-w-[99vw]">
          <DialogHeader className="shrink-0 border-b bg-background/95 px-5 py-4 pr-14">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <DialogTitle className="flex items-center gap-2"><ShieldAlert className="h-5 w-5 text-primary" />Collections recovery control centre</DialogTitle>
                <DialogDescription className="mt-1">Filter the entire recovery portfolio, then open any case to record evidence and next actions.</DialogDescription>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant="outline">{filteredCases.length} matching</Badge>
                  <Badge variant="outline">Overdue {formatMoney(filteredOverdue)}</Badge>
                  <Badge variant="outline">Legal {legalCount}</Badge>
                  <Badge variant="outline">Follow-up due {followUpDueCount}</Badge>
                  <Badge variant="outline">Promises {promiseCount}</Badge>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => quickFilter("urgent")}>Urgent</Button>
                <Button size="sm" variant="outline" onClick={() => quickFilter("legal")}>Legal</Button>
                <Button size="sm" variant="outline" onClick={() => quickFilter("follow_up")}>Follow-up due</Button>
                <Button size="sm" variant="outline" onClick={() => quickFilter("promise")}>Promises</Button>
                <Button size="sm" variant="outline" onClick={clearFilters}><FilterX className="h-3.5 w-3.5" />Clear</Button>
                <Button size="sm" onClick={() => setQueueFullscreen(false)}><Minimize2 className="h-4 w-4" />Return</Button>
              </div>
            </div>
          </DialogHeader>

          <div className={`grid min-h-0 flex-1 transition-[grid-template-columns] duration-300 ${filtersCollapsed ? "lg:grid-cols-[66px_minmax(0,1fr)]" : "lg:grid-cols-[320px_minmax(0,1fr)]"}`}>
            <aside className="hidden min-h-0 border-r bg-muted/15 lg:flex lg:flex-col">
              <div className={`flex h-14 shrink-0 items-center border-b ${filtersCollapsed ? "justify-center px-2" : "justify-between px-3"}`}>
                {!filtersCollapsed ? <div className="flex items-center gap-2"><SlidersHorizontal className="h-4 w-4 text-primary" /><span className="text-sm font-black">All filters</span>{activeFilterCount ? <Badge className="rounded-full">{activeFilterCount}</Badge> : null}</div> : null}
                <Button size="icon" variant="ghost" className="h-9 w-9 rounded-xl" onClick={() => setFiltersCollapsed((current) => !current)}>
                  {filtersCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
                </Button>
              </div>
              {filtersCollapsed ? (
                <div className="flex flex-1 flex-col items-center gap-2 py-3">
                  <Button size="icon" variant="ghost" className="relative rounded-xl" onClick={() => setFiltersCollapsed(false)}><SlidersHorizontal className="h-5 w-5" />{activeFilterCount ? <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-black text-primary-foreground">{activeFilterCount}</span> : null}</Button>
                  <Button size="icon" variant="ghost" className="rounded-xl" onClick={clearFilters}><FilterX className="h-4 w-4" /></Button>
                </div>
              ) : (
                <div className="min-h-0 flex-1 overflow-y-auto p-3">
                  <CollectionFilterSidebar filters={filters} optionSets={optionSets} branchById={branchById} onChange={updateFilter} />
                </div>
              )}
            </aside>

            <section className="flex min-h-0 min-w-0 flex-col bg-background">
              <div className="shrink-0 border-b p-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input value={search} onChange={(event) => changeSearch(event.target.value)} placeholder="Search borrower, case, loan, phone, email, address, bank, action, branch..." className="pl-9 pr-4" />
                </div>
              </div>
              <div className="min-h-0 min-w-0 flex-1 overflow-auto">
                <RecoveryTable rows={visibleCases} loading={loading} branchById={branchById} onOpenCase={openCase} sticky />
              </div>
              <PaginationFooter
                total={filteredCases.length}
                start={filteredCases.length ? pageStart + 1 : 0}
                end={pageEnd}
                currentPage={safePage}
                totalPages={totalPages}
                pageSize={pageSize}
                onPageSizeChange={changePageSize}
                onPrevious={() => setPage((current) => Math.max(1, current - 1))}
                onNext={() => setPage((current) => Math.min(totalPages, current + 1))}
              />
            </section>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={caseOpen} onOpenChange={setCaseOpen}>
        <DialogContent className="flex max-h-[95dvh] w-[96vw] max-w-[96vw] flex-col gap-0 overflow-hidden p-0 sm:max-w-[96vw] lg:max-w-6xl">
          {selectedCase ? (
            <>
              <DialogHeader className="shrink-0 border-b bg-muted/20 px-5 py-4 pr-14">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <DialogTitle>{selectedCase.borrower_name}</DialogTitle>
                    <DialogDescription>{selectedCase.case_reference} · {selectedCase.loan_reference}</DialogDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={selectedCase.priority === "urgent" ? "destructive" : "outline"}>{titleCase(selectedCase.priority)} priority</Badge>
                    <Badge variant="outline">{titleCase(selectedCase.stage)}</Badge>
                    <Badge variant="secondary">{titleCase(selectedCase.status)}</Badge>
                    {selectedCase.promise_status ? <Badge variant="outline">Promise {titleCase(selectedCase.promise_status)}</Badge> : null}
                  </div>
                </div>
              </DialogHeader>

              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
                  <Card>
                    <CardHeader className="pb-3"><CardTitle className="text-base">Borrower contact</CardTitle></CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <ContactRow icon={PhoneCall} label="Phone" value={selectedCase.phone ?? "Not recorded"} />
                      <ContactRow icon={MapPin} label="Physical address" value={selectedCase.physical_address ?? "Not recorded"} />
                      <ContactRow icon={UserRound} label="Next of kin" value={selectedCase.next_of_kin_phones.join(", ") || "Not recorded"} />
                      <ContactRow icon={Banknote} label="Bank" value={[selectedCase.bank_name, selectedCase.masked_bank_account].filter(Boolean).join(" · ") || "Not recorded"} />
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-3"><CardTitle className="text-base">Recovery position</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-2 gap-3 text-sm">
                      <Info label="Overdue" value={formatMoney(selectedCase.overdue_amount)} />
                      <Info label="Loan balance" value={formatMoney(selectedCase.outstanding_balance)} />
                      <Info label="Days past due" value={String(selectedCase.days_past_due)} />
                      <Info label="Stage" value={titleCase(selectedCase.stage)} />
                      <Info label="Next action" value={selectedCase.next_action_at ? formatDateTime(selectedCase.next_action_at) : "Not scheduled"} />
                      <Info label="Last contact" value={selectedCase.last_contact_at ? formatDateTime(selectedCase.last_contact_at) : "No contact yet"} />
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="pb-3"><CardTitle className="text-base">Promise / legal position</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-2 gap-3 text-sm">
                      <Info label="Promise" value={selectedCase.promise_amount ? formatMoney(selectedCase.promise_amount) : "None"} />
                      <Info label="Promise date" value={selectedCase.promise_date ? formatDate(selectedCase.promise_date) : "None"} />
                      <Info label="Promise status" value={titleCase(selectedCase.promise_status ?? "none")} />
                      <Info label="Legal handover" value={selectedCase.legal_handover_at ? formatDateTime(selectedCase.legal_handover_at) : "No"} />
                    </CardContent>
                  </Card>
                </div>

                <div className="my-4 flex flex-wrap gap-2 rounded-2xl border bg-muted/15 p-3">
                  <Button size="sm" onClick={() => void startAction("call")}><PhoneCall className="h-4 w-4" />Call</Button>
                  <Button size="sm" variant="outline" onClick={() => void startAction("promise_to_pay")}><CalendarCheck2 className="h-4 w-4" />Promise to pay</Button>
                  <Button size="sm" variant="outline" onClick={() => void startAction("visit")}><MapPin className="h-4 w-4" />Visited</Button>
                  <Button size="sm" variant="outline" onClick={() => void startAction("default_notice")}><FileWarning className="h-4 w-4" />Default notice</Button>
                  <Button size="sm" variant="outline" onClick={() => void startAction("court")}><Gavel className="h-4 w-4" />Court</Button>
                  <Button size="sm" variant="outline" onClick={() => void startAction("other")}><Plus className="h-4 w-4" />Custom action</Button>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-3"><h3 className="font-black">Action history</h3><Badge variant="outline">{actions.length} action(s)</Badge></div>
                  {actions.map((action) => (
                    <div key={action.id} className="rounded-2xl border bg-muted/10 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="font-bold">{titleCase(action.activity_type)}</p>
                          <p className="text-xs text-muted-foreground">{action.performed_at ? formatDateTime(action.performed_at) : ""}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {action.amount ? <Badge variant="outline">{formatMoney(action.amount)}</Badge> : null}
                          <Badge variant="outline">{titleCase(action.outcome ?? "recorded")}</Badge>
                        </div>
                      </div>
                      {action.notes ? <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{action.notes}</p> : null}
                      {action.follow_up_at ? <p className="mt-2 text-xs font-semibold text-primary">Follow-up: {formatDateTime(action.follow_up_at)}</p> : null}
                      {action.documents.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {action.documents.map((file) => (
                            <Button key={file.id} size="sm" variant="secondary" onClick={() => void downloadManagedFile(file)}>
                              <Download className="h-3.5 w-3.5" />{file.original_name}
                            </Button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                  {!actions.length ? <EmptyState icon={MessageSquareText} title="No action recorded" description="Record the first call, promise, visit, notice or court step. Every action remains linked to this recovery case." /> : null}
                </div>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog open={actionOpen} onOpenChange={(open) => { if (!open) void closeActionDialog(); }}>
        <DialogContent className="max-h-[94dvh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Record {titleCase(actionType)}</DialogTitle>
            <DialogDescription>Preserve what happened, the result, the next follow-up and supporting evidence.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Action">
              <NativeSelect value={actionType} onChange={(event) => setActionType(event.target.value as CollectionActionType)}>
                <option value="call">Call</option>
                <option value="promise_to_pay">Promise to pay</option>
                <option value="visit">Visited address</option>
                <option value="default_notice">Written default notice</option>
                <option value="court">Court</option>
                <option value="other">Other</option>
              </NativeSelect>
            </Field>
            <Field label="Outcome"><Input value={outcome} onChange={(event) => setOutcome(event.target.value)} placeholder="Reached borrower, no answer, served..." /></Field>

            {actionType === "other" ? <div className="sm:col-span-2"><Field label="Custom action title"><Input value={customActionTitle} onChange={(event) => setCustomActionTitle(event.target.value)} placeholder="Employer visit, guarantor meeting, sheriff follow-up..." /></Field></div> : null}

            {actionType === "call" ? <Field label="Phone contacted"><Input value={contactPhone} onChange={(event) => setContactPhone(event.target.value)} /></Field> : null}

            {actionType === "promise_to_pay" ? (
              <>
                <Field label="Promised amount"><Input type="number" min="0" step="0.01" value={promiseAmount} onChange={(event) => setPromiseAmount(event.target.value)} /></Field>
                <Field label="Promised payment date"><Input type="date" value={promiseDate} onChange={(event) => setPromiseDate(event.target.value)} /></Field>
              </>
            ) : null}

            {actionType === "visit" ? <div className="sm:col-span-2"><Field label="Address visited"><Input value={visitedAddress} onChange={(event) => setVisitedAddress(event.target.value)} /></Field></div> : null}

            {actionType === "court" ? (
              <>
                <Field label="Court / tribunal"><Input value={courtName} onChange={(event) => setCourtName(event.target.value)} /></Field>
                <Field label="Court case number"><Input value={courtCaseNumber} onChange={(event) => setCourtCaseNumber(event.target.value)} /></Field>
                <Field label="Court / hearing date"><Input type="date" value={courtDate} onChange={(event) => setCourtDate(event.target.value)} /></Field>
              </>
            ) : null}

            <Field label={actionType === "promise_to_pay" ? "Next follow-up (optional; promise date is used if blank)" : "Next follow-up (required)"}><Input type="datetime-local" required={actionType !== "promise_to_pay"} value={followUpAt} onChange={(event) => setFollowUpAt(event.target.value)} /></Field>

            <div className="sm:col-span-2"><Field label="Detailed report"><Textarea rows={5} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Record what was said or observed, commitments made, people present and next steps." /></Field></div>

            <div className="sm:col-span-2">
              <Field label={actionType === "court" ? "Court papers (required)" : actionType === "default_notice" ? "Default notice / proof of service (required)" : "Supporting documents (optional)"}>
                <Input type="file" multiple onChange={(event) => setEvidenceFiles(Array.from(event.target.files ?? []))} />
              </Field>
              {evidenceFiles.length ? <p className="mt-1 text-xs text-muted-foreground">{evidenceFiles.length} file(s) selected.</p> : null}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => void closeActionDialog()} disabled={working}>Cancel</Button>
            <Button onClick={() => void saveAction()} disabled={working}>{working ? "Saving..." : "Save action"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function CollectionFilterSidebar({
  filters,
  optionSets,
  branchById,
  onChange,
}: {
  filters: CollectionFilters;
  optionSets: { statuses: string[]; stages: string[]; priorities: string[]; loanStatuses: string[]; branchIds: string[] };
  branchById: Map<string, Branch>;
  onChange: <K extends keyof CollectionFilters>(key: K, value: CollectionFilters[K]) => void;
}) {
  return (
    <div className="space-y-3">
      <FilterSection title="Case lifecycle">
        <SelectField label="Status" value={filters.status} onChange={(value) => onChange("status", value)} options={optionSets.statuses} allLabel="All statuses" />
        <SelectField label="Recovery stage" value={filters.stage} onChange={(value) => onChange("stage", value)} options={optionSets.stages} allLabel="All stages" />
        <SelectField label="Priority" value={filters.priority} onChange={(value) => onChange("priority", value)} options={optionSets.priorities} allLabel="All priorities" />
        <SelectField label="Loan status" value={filters.loanStatus} onChange={(value) => onChange("loanStatus", value)} options={optionSets.loanStatuses} allLabel="All loan states" />
        <FilterField label="Branch">
          <NativeSelect value={filters.branchId} onChange={(event) => onChange("branchId", event.target.value)}>
            <option value="all">All branches</option>
            {optionSets.branchIds.map((id) => <option key={id} value={id}>{branchById.get(id)?.name ?? id}</option>)}
          </NativeSelect>
        </FilterField>
      </FilterSection>

      <FilterSection title="Arrears & exposure">
        <FilterField label="Days past due">
          <NativeSelect value={filters.dpdBand} onChange={(event) => onChange("dpdBand", event.target.value as DpdBand)}>
            <option value="all">Any days past due</option><option value="current">0 / recovered</option><option value="1_7">1–7 days</option><option value="8_30">8–30 days</option><option value="31_60">31–60 days</option><option value="61_90">61–90 days</option><option value="91_plus">91+ days</option>
          </NativeSelect>
        </FilterField>
        <RangeField label="Overdue amount" minimum={filters.overdueMin} maximum={filters.overdueMax} onMin={(value) => onChange("overdueMin", value)} onMax={(value) => onChange("overdueMax", value)} />
        <RangeField label="Outstanding balance" minimum={filters.balanceMin} maximum={filters.balanceMax} onMin={(value) => onChange("balanceMin", value)} onMax={(value) => onChange("balanceMax", value)} />
      </FilterSection>

      <FilterSection title="Follow-up & activity">
        <FilterField label="Next follow-up">
          <NativeSelect value={filters.followUp} onChange={(event) => onChange("followUp", event.target.value as FollowUpFilter)}>
            <option value="all">Any follow-up</option><option value="overdue">Follow-up overdue</option><option value="today">Due today</option><option value="next_7">Next 7 days</option><option value="scheduled">Any scheduled</option><option value="none">Not scheduled</option>
          </NativeSelect>
        </FilterField>
        <FilterField label="Last action">
          <NativeSelect value={filters.activity} onChange={(event) => onChange("activity", event.target.value as ActivityFilter)}>
            <option value="all">Any action</option><option value="none">No action yet</option><option value="call">Call</option><option value="promise_to_pay">Promise to pay</option><option value="visit">Visit</option><option value="default_notice">Default notice</option><option value="court">Court</option><option value="other">Other</option>
          </NativeSelect>
        </FilterField>
        <FilterField label="Promise state">
          <NativeSelect value={filters.promise} onChange={(event) => onChange("promise", event.target.value as PromiseFilter)}>
            <option value="all">Any promise state</option><option value="pending">Pending promise</option><option value="kept">Promise kept</option><option value="broken">Promise broken</option><option value="none">No promise</option>
          </NativeSelect>
        </FilterField>
      </FilterSection>

      <FilterSection title="Contact & banking">
        <FilterField label="Contact data">
          <NativeSelect value={filters.contact} onChange={(event) => onChange("contact", event.target.value as ContactFilter)}>
            <option value="all">Any contact state</option><option value="has_phone">Has phone</option><option value="no_phone">No phone</option><option value="has_email">Has email</option><option value="no_email">No email</option><option value="has_address">Has address</option><option value="no_address">No address</option><option value="has_kin">Has next of kin / emergency</option><option value="no_kin">No next of kin / emergency</option>
          </NativeSelect>
        </FilterField>
        <FilterField label="Bank / salary account">
          <NativeSelect value={filters.banking} onChange={(event) => onChange("banking", event.target.value as BankFilter)}>
            <option value="all">Any banking state</option><option value="banked">Bank recorded</option><option value="unbanked">No bank recorded</option><option value="salary">Salary account</option><option value="non_salary">Not salary account</option>
          </NativeSelect>
        </FilterField>
      </FilterSection>

      <FilterSection title="Legal control">
        <FilterField label="Legal position">
          <NativeSelect value={filters.legal} onChange={(event) => onChange("legal", event.target.value as LegalFilter)}>
            <option value="all">Any legal state</option><option value="pre_legal">Pre-legal</option><option value="legal">Legal / court</option><option value="handed_over">Legal handover recorded</option><option value="not_legal">Not legal</option>
          </NativeSelect>
        </FilterField>
        <RangeField label="Case created" type="date" minimum={filters.createdFrom} maximum={filters.createdTo} onMin={(value) => onChange("createdFrom", value)} onMax={(value) => onChange("createdTo", value)} />
      </FilterSection>

      <FilterSection title="Sort">
        <FilterField label="Order by">
          <NativeSelect value={filters.sortBy} onChange={(event) => onChange("sortBy", event.target.value as SortOption)}>
            <option value="dpd_high">Most days past due</option><option value="dpd_low">Least days past due</option><option value="overdue_high">Highest overdue amount</option><option value="overdue_low">Lowest overdue amount</option><option value="balance_high">Highest balance</option><option value="balance_low">Lowest balance</option><option value="next_action">Next action soonest</option><option value="latest">Newest case</option><option value="oldest">Oldest case</option><option value="borrower">Borrower A–Z</option>
          </NativeSelect>
        </FilterField>
      </FilterSection>
    </div>
  );
}

function RecoveryTable({
  rows,
  loading,
  branchById,
  onOpenCase,
  sticky = false,
}: {
  rows: CollectionWorkspaceCase[];
  loading: boolean;
  branchById: Map<string, Branch>;
  onOpenCase: (item: CollectionWorkspaceCase) => void | Promise<void>;
  sticky?: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1320px] text-sm">
        <thead className={`${sticky ? "sticky top-0 z-20" : ""} bg-muted/70 text-left text-[10px] font-black uppercase tracking-[0.08em] text-muted-foreground backdrop-blur`}>
          <tr>
            <th className="px-4 py-3">Borrower</th>
            <th className="px-4 py-3">Case / loan</th>
            <th className="px-4 py-3 text-right">Arrears</th>
            <th className="px-4 py-3 text-right">Balance</th>
            <th className="px-4 py-3">Contact</th>
            <th className="px-4 py-3">Bank</th>
            <th className="px-4 py-3">Follow-up</th>
            <th className="px-4 py-3">Stage</th>
            <th className="px-4 py-3">Last action</th>
            <th className="px-4 py-3 text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((item) => {
            const branch = item.branch_id ? branchById.get(item.branch_id) : undefined;
            const followUpDue = item.next_action_at && parseDay(item.next_action_at) < localDay();
            return (
              <tr key={item.id} className="align-middle transition hover:bg-muted/30">
                <td className="px-4 py-3">
                  <p className="max-w-[220px] truncate font-bold" title={item.borrower_name}>{item.borrower_name}</p>
                  <p className="mt-0.5 max-w-[220px] truncate text-[11px] text-muted-foreground">{branch?.name ?? "Unassigned branch"}</p>
                  <div className="mt-1 flex gap-1"><Badge variant={item.priority === "urgent" ? "destructive" : "outline"} className="rounded-full text-[9px]">{titleCase(item.priority)}</Badge>{item.promise_status ? <Badge variant="outline" className="rounded-full text-[9px]">Promise {titleCase(item.promise_status)}</Badge> : null}</div>
                </td>
                <td className="px-4 py-3">
                  <p className="font-mono text-[11px] font-black text-primary">{item.case_reference}</p>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">{item.loan_reference}</p>
                  <p className="mt-1 text-[10px] text-muted-foreground">Loan {titleCase(item.loan_status)}</p>
                </td>
                <td className="px-4 py-3 text-right">
                  <p className="font-black text-destructive">{formatMoney(item.overdue_amount)}</p>
                  <p className="mt-1 text-[10px] font-semibold text-muted-foreground">{item.days_past_due} day(s) past due</p>
                  {item.earliest_overdue_date ? <p className="text-[10px] text-muted-foreground">From {formatDate(item.earliest_overdue_date)}</p> : null}
                </td>
                <td className="px-4 py-3 text-right"><p className="font-black">{formatMoney(item.outstanding_balance)}</p><p className="mt-1 text-[10px] text-muted-foreground">Due now {formatMoney(item.earliest_overdue_amount)}</p></td>
                <td className="px-4 py-3"><p className="font-medium">{item.phone ?? "No phone"}</p><p className="mt-1 max-w-[190px] truncate text-[10px] text-muted-foreground" title={item.physical_address ?? undefined}>{item.physical_address ?? "No address"}</p></td>
                <td className="px-4 py-3"><p className="font-medium">{item.bank_name ?? "Not recorded"}</p><p className="mt-1 font-mono text-[10px] text-muted-foreground">{item.masked_bank_account ?? "—"}</p>{item.salary_account ? <Badge variant="outline" className="mt-1 rounded-full text-[9px]">Salary</Badge> : null}</td>
                <td className="px-4 py-3">{item.next_action_at ? <><p className={followUpDue ? "font-bold text-destructive" : "font-semibold"}>{formatDateTime(item.next_action_at)}</p><p className="mt-1 text-[10px] text-muted-foreground">{followUpDue ? "Follow-up overdue" : "Scheduled"}</p></> : <span className="text-xs text-muted-foreground">Not scheduled</span>}</td>
                <td className="px-4 py-3"><div className="flex flex-col items-start gap-1"><Badge variant={item.stage === "legal" ? "destructive" : "outline"} className="rounded-full">{titleCase(item.stage)}</Badge><Badge variant="secondary" className="rounded-full text-[9px]">{titleCase(item.status)}</Badge></div></td>
                <td className="px-4 py-3">{item.last_action ? <><p className="font-semibold">{titleCase(item.last_action.activity_type)}</p><p className="mt-1 max-w-[190px] truncate text-[10px] text-muted-foreground">{item.last_action.outcome ?? "Recorded"}</p><p className="text-[10px] text-muted-foreground">{item.last_action.performed_at ? formatDateTime(item.last_action.performed_at) : ""}</p></> : <span className="text-xs text-muted-foreground">No action yet</span>}</td>
                <td className="px-4 py-3 text-right"><Button size="sm" onClick={() => void onOpenCase(item)}><FolderOpen className="h-4 w-4" />Open case</Button></td>
              </tr>
            );
          })}
          {!loading && !rows.length ? <tr><td colSpan={10} className="h-44"><EmptyState icon={ShieldAlert} title="No matching collection cases" description="There are no cases matching the current search and filters. Clear filters or synchronise arrears again." /></td></tr> : null}
          {loading ? <tr><td colSpan={10} className="h-40 text-center text-sm text-muted-foreground"><RefreshCcw className="mx-auto mb-2 h-5 w-5 animate-spin" />Synchronising the recovery queue...</td></tr> : null}
        </tbody>
      </table>
    </div>
  );
}

function PaginationFooter({ total, start, end, currentPage, totalPages, pageSize, onPageSizeChange, onPrevious, onNext }: {
  total: number; start: number; end: number; currentPage: number; totalPages: number; pageSize: number; onPageSizeChange: (value: number) => void; onPrevious: () => void; onNext: () => void;
}) {
  return (
    <div className="flex shrink-0 flex-col gap-3 border-t bg-background/95 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-xs text-muted-foreground">Showing <span className="font-bold text-foreground">{start}–{end}</span> of <span className="font-bold text-foreground">{total}</span></p>
      <div className="flex flex-wrap items-center gap-2">
        <Label className="text-xs text-muted-foreground">Rows</Label>
        <NativeSelect value={String(pageSize)} onChange={(event) => onPageSizeChange(Number(event.target.value))} className="h-9 w-20">{PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}</NativeSelect>
        <Button size="sm" variant="outline" disabled={currentPage <= 1} onClick={onPrevious}><ChevronLeft className="h-4 w-4" />Previous</Button>
        <Badge variant="outline" className="h-9 rounded-xl px-3">Page {currentPage} of {totalPages}</Badge>
        <Button size="sm" variant="outline" disabled={currentPage >= totalPages} onClick={onNext}>Next<ChevronRight className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}

type MetricTone = "primary" | "danger" | "warning" | "success" | "neutral";

function MetricCard({ icon: Icon, label, value, note, tone }: { icon: LucideIcon; label: string; value: string; note: string; tone: MetricTone }) {
  const toneClasses: Record<MetricTone, { icon: string; value: string }> = {
    primary: { icon: "bg-primary/10 text-primary", value: "text-foreground" },
    danger: { icon: "bg-destructive/10 text-destructive", value: "text-destructive" },
    warning: { icon: "bg-amber-500/10 text-amber-700 dark:text-amber-400", value: "text-foreground" },
    success: { icon: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400", value: "text-foreground" },
    neutral: { icon: "bg-muted text-foreground", value: "text-foreground" },
  };
  const currentTone = toneClasses[tone];

  return (
    <div className="flex min-w-0 items-center gap-3 border-b p-4 last:border-b-0 sm:odd:border-r xl:border-b-0 xl:border-r xl:last:border-r-0">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${currentTone.icon}`}><Icon className="h-5 w-5" /></div>
      <div className="min-w-0">
        <p className="text-[10px] font-black uppercase tracking-[0.1em] text-muted-foreground">{label}</p>
        <p className={`mt-0.5 truncate text-xl font-black ${currentTone.value}`}>{value}</p>
        <p className="mt-0.5 truncate text-[10px] text-muted-foreground">{note}</p>
      </div>
    </div>
  );
}

function FilterSection({ title, children }: { title: string; children: ReactNode }) {
  return <section className="overflow-hidden rounded-xl border bg-background"><div className="border-b bg-muted/30 px-3 py-2"><p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">{title}</p></div><div className="space-y-3 p-3">{children}</div></section>;
}

function FilterField({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-1.5"><Label className="text-[11px] font-bold">{label}</Label>{children}</div>;
}

function SelectField({ label, value, onChange, options, allLabel }: { label: string; value: string; onChange: (value: string) => void; options: string[]; allLabel: string }) {
  return <FilterField label={label}><NativeSelect value={value} onChange={(event) => onChange(event.target.value)}><option value="all">{allLabel}</option>{options.map((option) => <option key={option} value={option}>{titleCase(option)}</option>)}</NativeSelect></FilterField>;
}

function RangeField({ label, minimum, maximum, onMin, onMax, type = "number" }: { label: string; minimum: string; maximum: string; onMin: (value: string) => void; onMax: (value: string) => void; type?: "number" | "date" }) {
  return <FilterField label={label}><div className="grid grid-cols-2 gap-2"><Input type={type} value={minimum} placeholder={type === "date" ? "From" : "Min"} onChange={(event) => onMin(event.target.value)} /><Input type={type} value={maximum} placeholder={type === "date" ? "To" : "Max"} onChange={(event) => onMax(event.target.value)} /></div></FilterField>;
}

function Info({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-muted/40 p-3"><p className="text-[10px] font-black uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 break-words font-bold">{value}</p></div>;
}

function ContactRow({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return <div className="flex items-start gap-3"><Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" /><div><p className="text-[10px] font-black uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-0.5 break-words font-medium">{value}</p></div></div>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function EmptyState({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  return <div className="col-span-full flex min-h-32 flex-col items-center justify-center rounded-2xl border border-dashed bg-muted/10 p-5 text-center"><div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div><p className="font-black">{title}</p><p className="mt-1 max-w-lg text-xs leading-5 text-muted-foreground">{description}</p></div>;
}
