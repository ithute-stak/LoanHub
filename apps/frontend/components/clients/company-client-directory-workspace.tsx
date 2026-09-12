"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  BadgeAlert,
  Banknote,
  BookOpenCheck,
  CalendarClock,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  FileText,
  FilterX,
  Gavel,
  Landmark,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Scale,
  SlidersHorizontal,
  UserRound,
  UsersRound,
} from "lucide-react";

import {
  createCompanyClientCaseEntry,
  listCompanyClientCaseEntries,
  listCompanyClientCaseRecords,
  updateCompanyClientCaseEntryStatus,
} from "@/api/companyClients";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { LoadingButton } from "@/components/ui/loading-button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import type { Branch } from "@/types/branch";
import type {
  CompanyClient,
  CompanyClientCaseEntry,
  CompanyClientCaseEntryCreate,
  CompanyClientCaseEntryType,
  CompanyClientCaseRecord,
  CompanyClientPortfolioInsights,
} from "@/types/companyClient";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const PAGE_SIZES = [15, 30, 50, 100] as const;

type YesNoAll = "all" | "yes" | "no";
type DueWindow = "all" | "overdue" | "today" | "3" | "7" | "14" | "30" | "later" | "none";
type SalaryWindow = "all" | "today" | "3" | "7" | "14" | "30" | "none";
type CaseState = "all" | "comments" | "legal" | "open_legal" | "none";
type WorkspaceTab = "directory" | "case_records";
type SortOption =
  | "name"
  | "newest"
  | "oldest"
  | "balance_high"
  | "balance_low"
  | "income_high"
  | "income_low"
  | "due_soonest"
  | "salary_soonest"
  | "case_latest";

type DirectoryFilters = {
  accountStatus: string;
  source: string;
  branchId: string;
  gender: string;
  maritalStatus: string;
  nationality: string;
  district: string;
  town: string;
  identityState: "all" | "national_id" | "passport" | "missing";
  loginState: YesNoAll;
  creditConsent: YesNoAll;
  birthFrom: string;
  birthTo: string;
  employmentStatus: string;
  employer: string;
  jobTitle: string;
  loanStatus: string;
  loanState: YesNoAll;
  activeLoanState: YesNoAll;
  overdueState: YesNoAll;
  dueWindow: DueWindow;
  salaryWindow: SalaryWindow;
  salaryRecorded: YesNoAll;
  bankState: YesNoAll;
  bankName: string;
  bankAccountType: string;
  salaryAccount: YesNoAll;
  bankLast4: string;
  openingFeeStatus: string;
  existingLoans: YesNoAll;
  caseState: CaseState;
  createdFrom: string;
  createdTo: string;
  incomeMin: string;
  incomeMax: string;
  externalDebtMin: string;
  externalDebtMax: string;
  outstandingMin: string;
  outstandingMax: string;
  loanCountMin: string;
  loanCountMax: string;
  overdueCountMin: string;
  overdueCountMax: string;
  nextDueAmountMin: string;
  nextDueAmountMax: string;
  openingFeeMin: string;
  openingFeeMax: string;
  sortBy: SortOption;
};

const DEFAULT_FILTERS: DirectoryFilters = {
  accountStatus: "all",
  source: "all",
  branchId: "all",
  gender: "all",
  maritalStatus: "all",
  nationality: "all",
  district: "all",
  town: "all",
  identityState: "all",
  loginState: "all",
  creditConsent: "all",
  birthFrom: "",
  birthTo: "",
  employmentStatus: "all",
  employer: "all",
  jobTitle: "all",
  loanStatus: "all",
  loanState: "all",
  activeLoanState: "all",
  overdueState: "all",
  dueWindow: "all",
  salaryWindow: "all",
  salaryRecorded: "all",
  bankState: "all",
  bankName: "all",
  bankAccountType: "all",
  salaryAccount: "all",
  bankLast4: "",
  openingFeeStatus: "all",
  existingLoans: "all",
  caseState: "all",
  createdFrom: "",
  createdTo: "",
  incomeMin: "",
  incomeMax: "",
  externalDebtMin: "",
  externalDebtMax: "",
  outstandingMin: "",
  outstandingMax: "",
  loanCountMin: "",
  loanCountMax: "",
  overdueCountMin: "",
  overdueCountMax: "",
  nextDueAmountMin: "",
  nextDueAmountMax: "",
  openingFeeMin: "",
  openingFeeMax: "",
  sortBy: "name",
};

const COMMENT_CATEGORIES = [
  ["general", "General note"],
  ["customer_contact", "Customer contact"],
  ["collection", "Collection note"],
  ["repayment_promise", "Repayment promise"],
  ["risk", "Risk observation"],
  ["compliance", "Compliance"],
  ["document", "Document / evidence"],
  ["other", "Other"],
] as const;

const LEGAL_ACTION_TYPES = [
  ["demand_letter", "Demand letter"],
  ["final_notice", "Final notice"],
  ["handed_to_attorney", "Handed to attorney"],
  ["summons", "Summons"],
  ["court_filing", "Court filing"],
  ["judgment", "Judgment"],
  ["garnishment", "Garnishment"],
  ["attachment", "Attachment"],
  ["settlement", "Settlement"],
  ["other", "Other legal action"],
] as const;

const LEGAL_STATUSES = [
  ["open", "Open"],
  ["pending", "Pending"],
  ["completed", "Completed"],
  ["withdrawn", "Withdrawn"],
] as const;

function isoDay(value: string | null | undefined) {
  return value ? value.slice(0, 10) : "";
}

function todayStart() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function daysUntil(value: string | null | undefined) {
  if (!value) return null;
  const parsed = new Date(`${isoDay(value)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  return Math.round((parsed.getTime() - todayStart().getTime()) / 86_400_000);
}

function dueWindowMatches(value: string | null | undefined, filter: DueWindow) {
  if (filter === "all") return true;
  if (filter === "none") return !value;
  const days = daysUntil(value);
  if (days === null) return false;
  if (filter === "overdue") return days < 0;
  if (filter === "today") return days === 0;
  if (filter === "later") return days > 30;
  return days >= 0 && days <= Number(filter);
}

function salaryWindowMatches(value: string | null | undefined, filter: SalaryWindow) {
  if (filter === "all") return true;
  if (filter === "none") return !value;
  const days = daysUntil(value);
  if (days === null) return false;
  if (filter === "today") return days === 0;
  return days >= 0 && days <= Number(filter);
}

function numberRange(value: number | null | undefined, min: string, max: string) {
  const numeric = Number(value ?? 0);
  const minimum = min.trim() === "" ? null : Number(min);
  const maximum = max.trim() === "" ? null : Number(max);
  if (minimum !== null && Number.isFinite(minimum) && numeric < minimum) return false;
  if (maximum !== null && Number.isFinite(maximum) && numeric > maximum) return false;
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

function uniqueStrings(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value?.trim()))))
    .sort((left, right) => left.localeCompare(right));
}

function compareOptionalDate(left: string | null | undefined, right: string | null | undefined) {
  if (!left && !right) return 0;
  if (!left) return 1;
  if (!right) return -1;
  return left.localeCompare(right);
}

function sortClients(left: CompanyClient, right: CompanyClient, sortBy: SortOption) {
  switch (sortBy) {
    case "newest": return right.created_at.localeCompare(left.created_at);
    case "oldest": return left.created_at.localeCompare(right.created_at);
    case "balance_high": return Number(right.outstanding_balance) - Number(left.outstanding_balance);
    case "balance_low": return Number(left.outstanding_balance) - Number(right.outstanding_balance);
    case "income_high": return Number(right.monthly_income ?? 0) - Number(left.monthly_income ?? 0);
    case "income_low": return Number(left.monthly_income ?? 0) - Number(right.monthly_income ?? 0);
    case "due_soonest": return compareOptionalDate(left.next_due_date, right.next_due_date);
    case "salary_soonest": return compareOptionalDate(left.next_salary_pay_date, right.next_salary_pay_date);
    case "case_latest": return compareOptionalDate(right.latest_case_entry_at, left.latest_case_entry_at);
    case "name":
    default: return left.full_name.localeCompare(right.full_name);
  }
}

function FilterField({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-1.5"><Label className="text-[11px] font-bold text-foreground/80">{label}</Label>{children}</div>;
}

function FilterSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-xl border bg-background shadow-sm">
      <div className="border-b bg-muted/30 px-3 py-2.5">
        <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">{title}</p>
      </div>
      <div className="space-y-3 p-3">{children}</div>
    </section>
  );
}

function RangeInputs({
  label,
  minimum,
  maximum,
  onMinimumChange,
  onMaximumChange,
  type = "number",
}: {
  label: string;
  minimum: string;
  maximum: string;
  onMinimumChange: (value: string) => void;
  onMaximumChange: (value: string) => void;
  type?: "number" | "date";
}) {
  return (
    <FilterField label={label}>
      <div className="grid grid-cols-2 gap-2">
        <Input type={type} value={minimum} placeholder={type === "date" ? "From" : "Min"} onChange={(event) => onMinimumChange(event.target.value)} />
        <Input type={type} value={maximum} placeholder={type === "date" ? "To" : "Max"} onChange={(event) => onMaximumChange(event.target.value)} />
      </div>
    </FilterField>
  );
}

function YesNoSelect({ value, onChange, allLabel, yesLabel, noLabel }: {
  value: YesNoAll;
  onChange: (value: YesNoAll) => void;
  allLabel: string;
  yesLabel: string;
  noLabel: string;
}) {
  return (
    <Select value={value} onValueChange={(next) => onChange(next as YesNoAll)}>
      <SelectTrigger><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value="all">{allLabel}</SelectItem>
        <SelectItem value="yes">{yesLabel}</SelectItem>
        <SelectItem value="no">{noLabel}</SelectItem>
      </SelectContent>
    </Select>
  );
}

function displayEntryType(value: CompanyClientCaseEntryType) {
  return value === "legal_action" ? "Legal action" : "Comment";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function CompanyClientDirectoryWorkspace({
  open,
  onOpenChange,
  clients,
  branches,
  portfolioInsights,
  initialSearch = "",
  onStartLoan,
  onSettleOpeningFee,
  onViewProfile,
  onCaseEntryCreated,
  onCaseEntryStatusChanged,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clients: CompanyClient[];
  branches: Branch[];
  portfolioInsights: CompanyClientPortfolioInsights | null;
  initialSearch?: string;
  onStartLoan: (client: CompanyClient) => void;
  onSettleOpeningFee: (client: CompanyClient) => void;
  onViewProfile: (client: CompanyClient) => void;
  onCaseEntryCreated: (accountId: string, entry: CompanyClientCaseEntry) => void;
  onCaseEntryStatusChanged: (accountId: string, previousStatus: string, entry: CompanyClientCaseEntry) => void;
}) {
  const [tab, setTab] = useState<WorkspaceTab>("directory");
  const [filtersCollapsed, setFiltersCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<DirectoryFilters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(15);
  const [caseRecords, setCaseRecords] = useState<CompanyClientCaseRecord[]>([]);
  const [caseRecordsLoading, setCaseRecordsLoading] = useState(false);
  const [expandedAccountId, setExpandedAccountId] = useState<string | null>(null);
  const [entriesByAccount, setEntriesByAccount] = useState<Record<string, CompanyClientCaseEntry[]>>({});
  const [entriesLoadingAccountId, setEntriesLoadingAccountId] = useState<string | null>(null);
  const [entryDialogOpen, setEntryDialogOpen] = useState(false);
  const [entryMode, setEntryMode] = useState<CompanyClientCaseEntryType>("comment");
  const [entryClient, setEntryClient] = useState<CompanyClient | null>(null);
  const [entrySaving, setEntrySaving] = useState(false);
  const [caseStatusSavingId, setCaseStatusSavingId] = useState<string | null>(null);
  const [entryForm, setEntryForm] = useState<CompanyClientCaseEntryCreate>({
    entry_type: "comment",
    category: "general",
    title: "",
    body: "",
    status: "recorded",
    action_date: null,
    reference_number: "",
    amount: null,
    currency: "LSL",
  });

  const loadCaseRecords = useCallback(async () => {
    setCaseRecordsLoading(true);
    try {
      setCaseRecords(await listCompanyClientCaseRecords());
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Client comments and legal actions could not be loaded."));
    } finally {
      setCaseRecordsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => void loadCaseRecords(), 0);
    return () => window.clearTimeout(timer);
  }, [loadCaseRecords, open]);

  useEffect(() => {
    const normalized = initialSearch.trim();
    if (!open || !normalized) return;
    const timer = window.setTimeout(() => {
      setSearch(normalized);
      setFilters(DEFAULT_FILTERS);
      setPage(1);
      setTab("directory");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [initialSearch, open]);

  const branchById = useMemo(() => new Map(branches.map((branch) => [branch.id, branch])), [branches]);
  const clientById = useMemo(() => new Map(clients.map((client) => [client.id, client])), [clients]);

  const optionSets = useMemo(() => ({
    statuses: uniqueStrings(clients.map((client) => client.status)),
    sources: uniqueStrings(clients.map((client) => client.source)),
    genders: uniqueStrings(clients.map((client) => client.gender)),
    maritalStatuses: uniqueStrings(clients.map((client) => client.marital_status)),
    nationalities: uniqueStrings(clients.map((client) => client.nationality)),
    districts: uniqueStrings(clients.map((client) => client.district)),
    towns: uniqueStrings(clients.map((client) => client.town_or_village)),
    employmentStatuses: uniqueStrings(clients.map((client) => client.employment_status)),
    employers: uniqueStrings(clients.map((client) => client.employer_name)),
    jobTitles: uniqueStrings(clients.map((client) => client.job_title)),
    loanStatuses: uniqueStrings(clients.flatMap((client) => client.loan_statuses)),
    bankNames: uniqueStrings(clients.map((client) => client.bank_name)),
    bankAccountTypes: uniqueStrings(clients.map((client) => client.bank_account_type)),
    openingFeeStatuses: uniqueStrings(clients.map((client) => client.opening_fee_status)),
  }), [clients]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    const bankLast4 = filters.bankLast4.replace(/\D/g, "").slice(-4);
    return clients.filter((client) => {
      const branch = branchById.get(client.branch_id ?? "");
      if (query && ![
        client.full_name,
        client.account_reference,
        client.phone,
        client.email,
        client.national_id,
        client.passport_number,
        client.district,
        client.town_or_village,
        client.physical_address,
        client.employer_name,
        client.job_title,
        client.bank_name,
        client.bank_account_last4,
        client.recent_loan_reference,
        branch?.name,
      ].filter(Boolean).some((value) => String(value).toLowerCase().includes(query))) return false;

      if (filters.accountStatus !== "all" && client.status !== filters.accountStatus) return false;
      if (filters.source !== "all" && client.source !== filters.source) return false;
      if (filters.branchId !== "all" && client.branch_id !== filters.branchId) return false;
      if (filters.gender !== "all" && client.gender !== filters.gender) return false;
      if (filters.maritalStatus !== "all" && client.marital_status !== filters.maritalStatus) return false;
      if (filters.nationality !== "all" && client.nationality !== filters.nationality) return false;
      if (filters.district !== "all" && client.district !== filters.district) return false;
      if (filters.town !== "all" && client.town_or_village !== filters.town) return false;
      if (filters.identityState === "national_id" && !client.national_id) return false;
      if (filters.identityState === "passport" && !client.passport_number) return false;
      if (filters.identityState === "missing" && (client.national_id || client.passport_number)) return false;
      if (filters.loginState === "yes" && !client.is_login_active) return false;
      if (filters.loginState === "no" && client.is_login_active) return false;
      if (filters.creditConsent === "yes" && !client.consent_to_credit_checks) return false;
      if (filters.creditConsent === "no" && client.consent_to_credit_checks) return false;
      if (!dateRange(client.date_of_birth, filters.birthFrom, filters.birthTo)) return false;

      if (filters.employmentStatus !== "all" && client.employment_status !== filters.employmentStatus) return false;
      if (filters.employer !== "all" && client.employer_name !== filters.employer) return false;
      if (filters.jobTitle !== "all" && client.job_title !== filters.jobTitle) return false;
      if (filters.existingLoans === "yes" && !client.has_existing_loans) return false;
      if (filters.existingLoans === "no" && client.has_existing_loans) return false;
      if (!numberRange(client.monthly_income, filters.incomeMin, filters.incomeMax)) return false;
      if (!numberRange(client.existing_loan_total, filters.externalDebtMin, filters.externalDebtMax)) return false;

      if (filters.loanStatus !== "all" && !client.loan_statuses.includes(filters.loanStatus)) return false;
      if (filters.loanState === "yes" && client.loan_count <= 0) return false;
      if (filters.loanState === "no" && client.loan_count > 0) return false;
      if (filters.activeLoanState === "yes" && client.active_loan_count <= 0) return false;
      if (filters.activeLoanState === "no" && client.active_loan_count > 0) return false;
      if (filters.overdueState === "yes" && client.overdue_installment_count <= 0) return false;
      if (filters.overdueState === "no" && client.overdue_installment_count > 0) return false;
      if (!dueWindowMatches(client.next_due_date, filters.dueWindow)) return false;
      if (!numberRange(client.outstanding_balance, filters.outstandingMin, filters.outstandingMax)) return false;
      if (!numberRange(client.loan_count, filters.loanCountMin, filters.loanCountMax)) return false;
      if (!numberRange(client.overdue_installment_count, filters.overdueCountMin, filters.overdueCountMax)) return false;
      if (!numberRange(client.next_due_amount, filters.nextDueAmountMin, filters.nextDueAmountMax)) return false;

      if (!salaryWindowMatches(client.next_salary_pay_date, filters.salaryWindow)) return false;
      if (filters.salaryRecorded === "yes" && !client.salary_date) return false;
      if (filters.salaryRecorded === "no" && client.salary_date) return false;
      if (filters.bankState === "yes" && !client.has_bank_account) return false;
      if (filters.bankState === "no" && client.has_bank_account) return false;
      if (filters.bankName !== "all" && client.bank_name !== filters.bankName) return false;
      if (filters.bankAccountType !== "all" && client.bank_account_type !== filters.bankAccountType) return false;
      if (filters.salaryAccount === "yes" && !client.salary_account) return false;
      if (filters.salaryAccount === "no" && client.salary_account) return false;
      if (bankLast4 && !String(client.bank_account_last4 ?? "").endsWith(bankLast4)) return false;

      if (filters.openingFeeStatus !== "all" && client.opening_fee_status !== filters.openingFeeStatus) return false;
      if (!numberRange(client.opening_fee_amount, filters.openingFeeMin, filters.openingFeeMax)) return false;
      if (filters.caseState === "comments" && client.comment_count <= 0) return false;
      if (filters.caseState === "legal" && client.legal_action_count <= 0) return false;
      if (filters.caseState === "open_legal" && client.open_legal_action_count <= 0) return false;
      if (filters.caseState === "none" && client.case_entry_count > 0) return false;
      if (!dateRange(client.created_at, filters.createdFrom, filters.createdTo)) return false;

      return true;
    }).sort((left, right) => sortClients(left, right, filters.sortBy));
  }, [branchById, clients, filters, search]);

  const activeFilterCount = useMemo(() => (
    (Object.keys(DEFAULT_FILTERS) as Array<keyof DirectoryFilters>).reduce((count, key) => (
      filters[key] === DEFAULT_FILTERS[key] ? count : count + 1
    ), search.trim() ? 1 : 0)
  ), [filters, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const pageRows = filtered.slice(pageStart, pageStart + pageSize);

  const totalOutstanding = useMemo(() => filtered.reduce((sum, client) => sum + Number(client.outstanding_balance || 0), 0), [filtered]);
  const overdueClients = useMemo(() => filtered.filter((client) => client.overdue_installment_count > 0).length, [filtered]);
  const commentedClients = useMemo(() => clients.filter((client) => client.case_entry_count > 0).length, [clients]);

  function updateFilter<K extends keyof DirectoryFilters>(key: K, value: DirectoryFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function resetFilters() {
    setSearch("");
    setFilters(DEFAULT_FILTERS);
    setPage(1);
  }

  function quickFilter(kind: "overdue" | "payday" | "comments" | "legal" | "no_loans") {
    setFilters(DEFAULT_FILTERS);
    if (kind === "overdue") setFilters((current) => ({ ...current, overdueState: "yes" }));
    if (kind === "payday") setFilters((current) => ({ ...current, salaryWindow: "7", loanState: "yes" }));
    if (kind === "comments") setFilters((current) => ({ ...current, caseState: "comments" }));
    if (kind === "legal") setFilters((current) => ({ ...current, caseState: "open_legal" }));
    if (kind === "no_loans") setFilters((current) => ({ ...current, loanState: "no" }));
    setPage(1);
    setTab("directory");
  }

  function openEntryDialog(client: CompanyClient, mode: CompanyClientCaseEntryType) {
    setEntryClient(client);
    setEntryMode(mode);
    setEntryForm({
      entry_type: mode,
      category: mode === "comment" ? "general" : "demand_letter",
      title: "",
      body: "",
      status: mode === "comment" ? "recorded" : "open",
      action_date: mode === "legal_action" ? new Date().toISOString().slice(0, 16) : null,
      reference_number: "",
      amount: null,
      currency: "LSL",
    });
    setEntryDialogOpen(true);
  }

  async function submitCaseEntry() {
    if (!entryClient || !entryForm.body.trim()) {
      toast.warning("Enter the comment or legal-action details before saving.");
      return;
    }
    setEntrySaving(true);
    try {
      const created = await createCompanyClientCaseEntry(entryClient.id, {
        ...entryForm,
        entry_type: entryMode,
        title: entryForm.title?.trim() || null,
        body: entryForm.body.trim(),
        reference_number: entryForm.reference_number?.trim() || null,
        action_date: entryForm.action_date ? new Date(entryForm.action_date).toISOString() : null,
        amount: entryForm.amount === null || Number.isNaN(Number(entryForm.amount)) ? null : Number(entryForm.amount),
      });
      onCaseEntryCreated(entryClient.id, created);
      setEntriesByAccount((current) => ({
        ...current,
        [entryClient.id]: [created, ...(current[entryClient.id] ?? [])],
      }));
      await loadCaseRecords();
      setEntryDialogOpen(false);
      toast.success(entryMode === "comment" ? "Client comment recorded" : "Legal action recorded", {
        description: `${entryClient.full_name} now has an auditable case-history entry.`,
      });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The client case entry could not be saved."));
    } finally {
      setEntrySaving(false);
    }
  }

  async function markLegalActionCompleted(accountId: string, entry: CompanyClientCaseEntry) {
    setCaseStatusSavingId(entry.id);
    try {
      const updated = await updateCompanyClientCaseEntryStatus(accountId, entry.id, "completed");
      setEntriesByAccount((current) => ({
        ...current,
        [accountId]: (current[accountId] ?? []).map((item) => item.id === updated.id ? updated : item),
      }));
      onCaseEntryStatusChanged(accountId, entry.status, updated);
      await loadCaseRecords();
      toast.success("Legal action marked completed");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The legal-action status could not be updated."));
    } finally {
      setCaseStatusSavingId(null);
    }
  }

  async function toggleCaseRecord(record: CompanyClientCaseRecord) {
    if (expandedAccountId === record.client_account_id) {
      setExpandedAccountId(null);
      return;
    }
    setExpandedAccountId(record.client_account_id);
    if (entriesByAccount[record.client_account_id]) return;
    setEntriesLoadingAccountId(record.client_account_id);
    try {
      const entries = await listCompanyClientCaseEntries(record.client_account_id);
      setEntriesByAccount((current) => ({ ...current, [record.client_account_id]: entries }));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The client case history could not be loaded."));
    } finally {
      setEntriesLoadingAccountId(null);
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className="flex h-[98dvh] max-h-[98dvh] w-[99vw] max-w-[99vw] flex-col gap-0 overflow-hidden rounded-2xl border bg-background p-0 shadow-2xl sm:max-w-[99vw]"
          showCloseButton
        >
          <DialogHeader className="shrink-0 border-b bg-background/95 px-5 py-3.5 pr-14 backdrop-blur sm:px-6">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/15">
                  <UsersRound className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <DialogTitle className="text-xl font-black tracking-tight">Company client control centre</DialogTitle>
                    {activeFilterCount > 0 ? <Badge variant="secondary" className="rounded-full">{activeFilterCount} filters</Badge> : null}
                  </div>
                  <DialogDescription className="mt-0.5">
                    Full-screen borrower directory, portfolio filters, comments and legal-action history.
                  </DialogDescription>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="rounded-full px-3">{filtered.length} matching</Badge>
                <Badge variant="outline" className="rounded-full px-3">Outstanding {formatMoney(totalOutstanding)}</Badge>
                {overdueClients > 0 ? <Badge variant="destructive" className="rounded-full px-3">{overdueClients} overdue</Badge> : null}
                <Badge variant="outline" className="rounded-full px-3">{commentedClients} with case history</Badge>
              </div>
            </div>

            <div className="mt-3 flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <Tabs value={tab} onValueChange={(value) => setTab(value as WorkspaceTab)}>
                <TabsList className="h-9">
                  <TabsTrigger value="directory" className="px-3">Client directory</TabsTrigger>
                  <TabsTrigger value="case_records" className="px-3">
                    Comments & legal
                    {caseRecords.length > 0 ? <Badge variant="secondary" className="ml-1 h-5 rounded-full px-1.5 text-[10px]">{caseRecords.length}</Badge> : null}
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => quickFilter("overdue")}><CalendarClock className="h-3.5 w-3.5" />Overdue</Button>
                <Button size="sm" variant="outline" onClick={() => quickFilter("payday")}><Landmark className="h-3.5 w-3.5" />Payday + loans</Button>
                <Button size="sm" variant="outline" onClick={() => quickFilter("comments")}><MessageSquarePlus className="h-3.5 w-3.5" />Comments</Button>
                <Button size="sm" variant="outline" onClick={() => quickFilter("legal")}><Gavel className="h-3.5 w-3.5" />Open legal</Button>
                <Button size="sm" variant="ghost" onClick={resetFilters}><FilterX className="h-3.5 w-3.5" />Clear</Button>
              </div>
            </div>
          </DialogHeader>

          {tab === "directory" ? (
            <div className={`grid min-h-0 flex-1 transition-[grid-template-columns] duration-300 ${filtersCollapsed ? "lg:grid-cols-[66px_minmax(0,1fr)]" : "lg:grid-cols-[320px_minmax(0,1fr)]"}`}>
              <aside className="hidden min-h-0 border-r bg-muted/15 lg:flex lg:flex-col">
                <div className={`flex h-14 shrink-0 items-center border-b ${filtersCollapsed ? "justify-center px-2" : "justify-between px-4"}`}>
                  {!filtersCollapsed ? (
                    <div className="flex items-center gap-2">
                      <SlidersHorizontal className="h-4 w-4 text-primary" />
                      <span className="text-sm font-black">All client filters</span>
                      {activeFilterCount > 0 ? <Badge className="h-5 min-w-5 rounded-full px-1.5">{activeFilterCount}</Badge> : null}
                    </div>
                  ) : null}
                  <Button size="icon" variant="ghost" className="h-9 w-9 rounded-xl" onClick={() => setFiltersCollapsed((current) => !current)}>
                    {filtersCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
                  </Button>
                </div>

                {filtersCollapsed ? (
                  <div className="flex flex-1 flex-col items-center gap-2 py-3">
                    <Button size="icon" variant="ghost" className="relative rounded-xl" onClick={() => setFiltersCollapsed(false)}>
                      <SlidersHorizontal className="h-5 w-5" />
                      {activeFilterCount > 0 ? <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-black text-primary-foreground">{activeFilterCount}</span> : null}
                    </Button>
                    <Button size="icon" variant="ghost" className="rounded-xl" onClick={() => quickFilter("overdue")} title="Overdue clients"><BadgeAlert className="h-4 w-4" /></Button>
                    <Button size="icon" variant="ghost" className="rounded-xl" onClick={() => quickFilter("legal")} title="Open legal actions"><Gavel className="h-4 w-4" /></Button>
                    <Button size="icon" variant="ghost" className="rounded-xl" onClick={resetFilters} title="Reset filters"><FilterX className="h-4 w-4" /></Button>
                  </div>
                ) : (
                  <ScrollArea className="min-h-0 flex-1">
                    <div className="space-y-3 p-3">
                      <FilterSection title="Account & identity">
                        <FilterField label="Account status">
                          <Select value={filters.accountStatus} onValueChange={(value) => updateFilter("accountStatus", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All account states</SelectItem>{optionSets.statuses.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Registration source">
                          <Select value={filters.source} onValueChange={(value) => updateFilter("source", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All sources</SelectItem>{optionSets.sources.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Branch">
                          <Select value={filters.branchId} onValueChange={(value) => updateFilter("branchId", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All branches</SelectItem>{branches.map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Gender">
                          <Select value={filters.gender} onValueChange={(value) => updateFilter("gender", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All genders</SelectItem>{optionSets.genders.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Marital status">
                          <Select value={filters.maritalStatus} onValueChange={(value) => updateFilter("maritalStatus", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All marital states</SelectItem>{optionSets.maritalStatuses.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Nationality">
                          <Select value={filters.nationality} onValueChange={(value) => updateFilter("nationality", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All nationalities</SelectItem>{optionSets.nationalities.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="District">
                          <Select value={filters.district} onValueChange={(value) => updateFilter("district", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All districts</SelectItem>{optionSets.districts.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Town / village">
                          <Select value={filters.town} onValueChange={(value) => updateFilter("town", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All towns</SelectItem>{optionSets.towns.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Identity document">
                          <Select value={filters.identityState} onValueChange={(value) => updateFilter("identityState", value as DirectoryFilters["identityState"])}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Any identity</SelectItem><SelectItem value="national_id">National ID recorded</SelectItem><SelectItem value="passport">Passport recorded</SelectItem><SelectItem value="missing">No ID/passport</SelectItem></SelectContent></Select>
                        </FilterField>
                        <FilterField label="Borrower login">
                          <YesNoSelect value={filters.loginState} onChange={(value) => updateFilter("loginState", value)} allLabel="Any login state" yesLabel="Login active" noLabel="Login disabled" />
                        </FilterField>
                        <FilterField label="Credit-check consent">
                          <YesNoSelect value={filters.creditConsent} onChange={(value) => updateFilter("creditConsent", value)} allLabel="Any consent state" yesLabel="Consent recorded" noLabel="Consent missing" />
                        </FilterField>
                        <RangeInputs label="Date of birth" type="date" minimum={filters.birthFrom} maximum={filters.birthTo} onMinimumChange={(value) => updateFilter("birthFrom", value)} onMaximumChange={(value) => updateFilter("birthTo", value)} />
                        <RangeInputs label="Account opened" type="date" minimum={filters.createdFrom} maximum={filters.createdTo} onMinimumChange={(value) => updateFilter("createdFrom", value)} onMaximumChange={(value) => updateFilter("createdTo", value)} />
                      </FilterSection>

                      <FilterSection title="Employment & affordability">
                        <FilterField label="Employment status">
                          <Select value={filters.employmentStatus} onValueChange={(value) => updateFilter("employmentStatus", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All employment</SelectItem>{optionSets.employmentStatuses.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Employer">
                          <Select value={filters.employer} onValueChange={(value) => updateFilter("employer", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All employers</SelectItem>{optionSets.employers.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Job title">
                          <Select value={filters.jobTitle} onValueChange={(value) => updateFilter("jobTitle", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All job titles</SelectItem>{optionSets.jobTitles.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <RangeInputs label="Monthly income" minimum={filters.incomeMin} maximum={filters.incomeMax} onMinimumChange={(value) => updateFilter("incomeMin", value)} onMaximumChange={(value) => updateFilter("incomeMax", value)} />
                        <FilterField label="Declared external loans">
                          <YesNoSelect value={filters.existingLoans} onChange={(value) => updateFilter("existingLoans", value)} allLabel="Any external-loan state" yesLabel="Has declared loans" noLabel="No declared loans" />
                        </FilterField>
                        <RangeInputs label="Declared external debt" minimum={filters.externalDebtMin} maximum={filters.externalDebtMax} onMinimumChange={(value) => updateFilter("externalDebtMin", value)} onMaximumChange={(value) => updateFilter("externalDebtMax", value)} />
                      </FilterSection>

                      <FilterSection title="Loan portfolio & collections">
                        <FilterField label="Loan status">
                          <Select value={filters.loanStatus} onValueChange={(value) => updateFilter("loanStatus", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All loan statuses</SelectItem>{optionSets.loanStatuses.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Loan history"><YesNoSelect value={filters.loanState} onChange={(value) => updateFilter("loanState", value)} allLabel="Any loan history" yesLabel="Has loans" noLabel="No loans" /></FilterField>
                        <FilterField label="Current active exposure"><YesNoSelect value={filters.activeLoanState} onChange={(value) => updateFilter("activeLoanState", value)} allLabel="Any active exposure" yesLabel="Has active/defaulted loan" noLabel="No active loan" /></FilterField>
                        <FilterField label="Arrears"><YesNoSelect value={filters.overdueState} onChange={(value) => updateFilter("overdueState", value)} allLabel="Any arrears state" yesLabel="Has overdue installments" noLabel="No overdue installments" /></FilterField>
                        <FilterField label="Next installment due">
                          <Select value={filters.dueWindow} onValueChange={(value) => updateFilter("dueWindow", value as DueWindow)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Any due date</SelectItem><SelectItem value="overdue">Past due</SelectItem><SelectItem value="today">Due today</SelectItem><SelectItem value="3">Next 3 days</SelectItem><SelectItem value="7">Next 7 days</SelectItem><SelectItem value="14">Next 14 days</SelectItem><SelectItem value="30">Next 30 days</SelectItem><SelectItem value="later">After 30 days</SelectItem><SelectItem value="none">No upcoming installment</SelectItem></SelectContent></Select>
                        </FilterField>
                        <RangeInputs label="Outstanding balance" minimum={filters.outstandingMin} maximum={filters.outstandingMax} onMinimumChange={(value) => updateFilter("outstandingMin", value)} onMaximumChange={(value) => updateFilter("outstandingMax", value)} />
                        <RangeInputs label="Loan count" minimum={filters.loanCountMin} maximum={filters.loanCountMax} onMinimumChange={(value) => updateFilter("loanCountMin", value)} onMaximumChange={(value) => updateFilter("loanCountMax", value)} />
                        <RangeInputs label="Overdue installment count" minimum={filters.overdueCountMin} maximum={filters.overdueCountMax} onMinimumChange={(value) => updateFilter("overdueCountMin", value)} onMaximumChange={(value) => updateFilter("overdueCountMax", value)} />
                        <RangeInputs label="Next due amount" minimum={filters.nextDueAmountMin} maximum={filters.nextDueAmountMax} onMinimumChange={(value) => updateFilter("nextDueAmountMin", value)} onMaximumChange={(value) => updateFilter("nextDueAmountMax", value)} />
                      </FilterSection>

                      <FilterSection title="Banking & salary timing">
                        <FilterField label="Bank account"><YesNoSelect value={filters.bankState} onChange={(value) => updateFilter("bankState", value)} allLabel="Any bank state" yesLabel="Has bank account" noLabel="No bank account" /></FilterField>
                        <FilterField label="Bank name">
                          <Select value={filters.bankName} onValueChange={(value) => updateFilter("bankName", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All banks</SelectItem>{optionSets.bankNames.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Account type">
                          <Select value={filters.bankAccountType} onValueChange={(value) => updateFilter("bankAccountType", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All account types</SelectItem>{optionSets.bankAccountTypes.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <FilterField label="Salary account"><YesNoSelect value={filters.salaryAccount} onChange={(value) => updateFilter("salaryAccount", value)} allLabel="Any salary account" yesLabel="Salary account" noLabel="Not salary account" /></FilterField>
                        <FilterField label="Salary date captured"><YesNoSelect value={filters.salaryRecorded} onChange={(value) => updateFilter("salaryRecorded", value)} allLabel="Any salary-date state" yesLabel="Salary date recorded" noLabel="Salary date missing" /></FilterField>
                        <FilterField label="Next salary / payday">
                          <Select value={filters.salaryWindow} onValueChange={(value) => updateFilter("salaryWindow", value as SalaryWindow)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Any payday</SelectItem><SelectItem value="today">Payday today</SelectItem><SelectItem value="3">Next 3 days</SelectItem><SelectItem value="7">Next 7 days</SelectItem><SelectItem value="14">Next 14 days</SelectItem><SelectItem value="30">Next 30 days</SelectItem><SelectItem value="none">Not recorded</SelectItem></SelectContent></Select>
                        </FilterField>
                        <FilterField label="Bank last 4">
                          <Input value={filters.bankLast4} maxLength={4} inputMode="numeric" placeholder="e.g. 1234" onChange={(event) => updateFilter("bankLast4", event.target.value.replace(/\D/g, "").slice(0, 4))} />
                        </FilterField>
                      </FilterSection>

                      <FilterSection title="Opening charge & case history">
                        <FilterField label="Opening charge">
                          <Select value={filters.openingFeeStatus} onValueChange={(value) => updateFilter("openingFeeStatus", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Any opening charge</SelectItem>{optionSets.openingFeeStatuses.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                        </FilterField>
                        <RangeInputs label="Opening charge amount" minimum={filters.openingFeeMin} maximum={filters.openingFeeMax} onMinimumChange={(value) => updateFilter("openingFeeMin", value)} onMaximumChange={(value) => updateFilter("openingFeeMax", value)} />
                        <FilterField label="Comments / legal history">
                          <Select value={filters.caseState} onValueChange={(value) => updateFilter("caseState", value as CaseState)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Any case history</SelectItem><SelectItem value="comments">Has comments</SelectItem><SelectItem value="legal">Has legal actions</SelectItem><SelectItem value="open_legal">Has open legal action</SelectItem><SelectItem value="none">No comments/legal history</SelectItem></SelectContent></Select>
                        </FilterField>
                        <FilterField label="Sort">
                          <Select value={filters.sortBy} onValueChange={(value) => updateFilter("sortBy", value as SortOption)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="name">Client name</SelectItem><SelectItem value="newest">Newest account</SelectItem><SelectItem value="oldest">Oldest account</SelectItem><SelectItem value="balance_high">Highest balance</SelectItem><SelectItem value="balance_low">Lowest balance</SelectItem><SelectItem value="income_high">Highest income</SelectItem><SelectItem value="income_low">Lowest income</SelectItem><SelectItem value="due_soonest">Due soonest</SelectItem><SelectItem value="salary_soonest">Payday soonest</SelectItem><SelectItem value="case_latest">Latest case activity</SelectItem></SelectContent></Select>
                        </FilterField>
                      </FilterSection>
                    </div>
                  </ScrollArea>
                )}
              </aside>

              <section className="flex min-h-0 min-w-0 flex-col bg-background">
                <div className="shrink-0 border-b px-4 py-2.5 sm:px-5">
                  <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                    <Input
                      value={search}
                      onChange={(event) => { setSearch(event.target.value); setPage(1); }}
                      placeholder="Search name, phone, account, ID, employer, branch, loan ref, bank..."
                      className="h-9 xl:max-w-[680px]"
                    />
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-muted-foreground">{filtered.length} matching · {portfolioInsights?.soon_due?.length ?? 0} due soon</span>
                      <Select value={String(pageSize)} onValueChange={(value) => { setPageSize(Number(value)); setPage(1); }}>
                        <SelectTrigger className="h-9 w-[118px]"><SelectValue /></SelectTrigger>
                        <SelectContent>{PAGE_SIZES.map((size) => <SelectItem key={size} value={String(size)}>{size} per page</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>

                <div className="min-h-0 min-w-0 flex-1 overflow-auto">
                  <Table className="min-w-[1320px]">
                    <TableHeader className="sticky top-0 z-20 bg-background/95 shadow-[0_1px_0_hsl(var(--border))] backdrop-blur">
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="w-[220px] pl-4">Client</TableHead>
                        <TableHead className="w-[170px]">Employment</TableHead>
                        <TableHead className="w-[175px]">Loan position</TableHead>
                        <TableHead className="w-[130px]">Next due</TableHead>
                        <TableHead className="w-[130px]">Salary / bank</TableHead>
                        <TableHead className="w-[135px]">Case history</TableHead>
                        <TableHead className="w-[310px] pr-4 text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {pageRows.length === 0 ? (
                        <TableRow><TableCell colSpan={7} className="h-80 text-center text-muted-foreground">No clients match the current search and filters.</TableCell></TableRow>
                      ) : pageRows.map((client) => {
                        const branch = branchById.get(client.branch_id ?? "");
                        return (
                          <TableRow key={client.id} className="hover:bg-muted/30">
                            <TableCell className="pl-4 align-top">
                              <p className="font-black leading-tight">{client.full_name}</p>
                              <p className="mt-1 text-xs text-muted-foreground">{client.account_reference} · {client.phone}</p>
                              <p className="mt-0.5 text-[10px] text-muted-foreground">{client.national_id || client.passport_number || "No identity number"}</p>
                              <p className="mt-0.5 text-[10px] text-muted-foreground">{branch?.name ?? "Unassigned branch"} · {client.district || "No district"}</p>
                            </TableCell>
                            <TableCell className="align-top">
                              <p className="font-semibold">{titleCase(client.employment_status)}</p>
                              <p className="mt-1 text-xs text-muted-foreground">{client.employer_name || "No employer"}</p>
                              <p className="mt-0.5 text-[10px] text-muted-foreground">{client.job_title || "No job title"}</p>
                              <p className="mt-1 text-xs font-semibold">{client.monthly_income !== null ? formatMoney(client.monthly_income) : "Income not recorded"}</p>
                            </TableCell>
                            <TableCell className="align-top">
                              <div className="flex flex-wrap gap-1">{client.loan_statuses.length ? client.loan_statuses.map((status) => <Badge key={status} variant="outline" className="rounded-full text-[9px]">{titleCase(status)}</Badge>) : <Badge variant="secondary" className="rounded-full text-[9px]">No loans</Badge>}</div>
                              <p className="mt-1.5 text-xs font-black">{formatMoney(client.outstanding_balance)} outstanding</p>
                              <p className="mt-0.5 text-[10px] text-muted-foreground">{client.loan_count} total · {client.active_loan_count} current</p>
                              {client.overdue_installment_count > 0 ? <Badge variant="destructive" className="mt-1 rounded-full text-[9px]">{client.overdue_installment_count} overdue</Badge> : null}
                            </TableCell>
                            <TableCell className="align-top">
                              <p className="font-semibold">{client.next_due_date ? formatDate(client.next_due_date) : "—"}</p>
                              <p className="mt-1 text-xs text-muted-foreground">{client.next_due_amount !== null ? formatMoney(client.next_due_amount) : "No upcoming installment"}</p>
                            </TableCell>
                            <TableCell className="align-top">
                              <p className="font-semibold">{client.next_salary_pay_date ? formatDate(client.next_salary_pay_date) : "No payday"}</p>
                              <p className="mt-1 text-xs text-muted-foreground">{client.bank_name || "No bank account"}</p>
                              <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{client.masked_bank_account || "—"}</p>
                            </TableCell>
                            <TableCell className="align-top">
                              {client.case_entry_count > 0 ? (
                                <div className="space-y-1">
                                  <div className="flex flex-wrap gap-1"><Badge variant="secondary" className="rounded-full text-[9px]">{client.comment_count} comments</Badge>{client.legal_action_count > 0 ? <Badge variant={client.open_legal_action_count > 0 ? "destructive" : "outline"} className="rounded-full text-[9px]">{client.legal_action_count} legal</Badge> : null}</div>
                                  <p className="text-[10px] text-muted-foreground">Latest {client.latest_case_entry_at ? formatDateTime(client.latest_case_entry_at) : "—"}</p>
                                </div>
                              ) : <span className="text-xs text-muted-foreground">No case history</span>}
                            </TableCell>
                            <TableCell className="pr-4 align-top text-right">
                              <div className="flex flex-wrap justify-end gap-1.5">
                                <Button size="sm" variant="outline" className="h-8 px-2.5" onClick={() => onViewProfile(client)}><UserRound className="h-3.5 w-3.5" />Profile</Button>
                                <Button size="sm" variant="outline" className="h-8 px-2.5" onClick={() => openEntryDialog(client, "comment")}><MessageSquarePlus className="h-3.5 w-3.5" />Comment</Button>
                                <Button size="sm" variant="outline" className="h-8 px-2.5" onClick={() => openEntryDialog(client, "legal_action")}><Gavel className="h-3.5 w-3.5" />Legal</Button>
                                {client.opening_fee_amount > 0 && client.opening_fee_status !== "paid" ? <Button size="sm" variant="outline" className="h-8 px-2.5" onClick={() => onSettleOpeningFee(client)}><Banknote className="h-3.5 w-3.5" />Charge</Button> : null}
                                <Button size="sm" variant="outline" className="h-8 px-2.5" asChild><Link href={`/company/documents?client=${client.id}`}><FileText className="h-3.5 w-3.5" />Letters</Link></Button>
                                <Button size="sm" variant="outline" className="h-8 px-2.5" asChild disabled={client.status !== "active"}><Link href={`/company/origination/new?borrower=${client.borrower_id}`}><BookOpenCheck className="h-3.5 w-3.5" />Assess</Link></Button>
                                <Button size="sm" className="h-8 px-2.5" disabled={client.status !== "active"} onClick={() => onStartLoan(client)}><Plus className="h-3.5 w-3.5" />Loan</Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>

                <div className="flex min-h-14 shrink-0 flex-col justify-center gap-2 border-t bg-background/95 px-4 py-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-muted-foreground">Showing <span className="font-semibold text-foreground">{filtered.length === 0 ? 0 : pageStart + 1}</span>–<span className="font-semibold text-foreground">{Math.min(pageStart + pageSize, filtered.length)}</span> of <span className="font-semibold text-foreground">{filtered.length}</span></p>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" disabled={safePage <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}><ChevronLeft className="h-4 w-4" />Previous</Button>
                    <Badge variant="outline" className="h-8 px-3">{safePage} / {totalPages}</Badge>
                    <Button size="sm" variant="outline" disabled={safePage >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>Next<ChevronRight className="h-4 w-4" /></Button>
                  </div>
                </div>
              </section>
            </div>
          ) : (
            <section className="flex min-h-0 flex-1 flex-col bg-muted/10">
              <div className="shrink-0 border-b bg-background px-5 py-3">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p className="font-black">Clients with comments or legal action</p>
                    <p className="text-xs text-muted-foreground">One row per client. Expand a row to see the complete internal timeline.</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{caseRecords.length} clients</Badge>
                    <Button size="sm" variant="outline" disabled={caseRecordsLoading} onClick={() => void loadCaseRecords()}>{caseRecordsLoading ? "Refreshing..." : "Refresh records"}</Button>
                  </div>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-auto p-4">
                <div className="overflow-hidden rounded-2xl border bg-background shadow-sm">
                  <Table className="min-w-[980px]">
                    <TableHeader className="sticky top-0 z-10 bg-background/95 backdrop-blur">
                      <TableRow><TableHead className="w-12" /><TableHead>Client</TableHead><TableHead>Activity</TableHead><TableHead>Latest entry</TableHead><TableHead>Legal state</TableHead><TableHead className="text-right">Actions</TableHead></TableRow>
                    </TableHeader>
                    <TableBody>
                      {caseRecordsLoading && caseRecords.length === 0 ? <TableRow><TableCell colSpan={6} className="h-52 text-center text-muted-foreground">Loading client case records...</TableCell></TableRow> : null}
                      {!caseRecordsLoading && caseRecords.length === 0 ? <TableRow><TableCell colSpan={6} className="h-52 text-center text-muted-foreground">No client comments or legal actions have been recorded yet.</TableCell></TableRow> : null}
                      {caseRecords.map((record) => {
                        const client = clientById.get(record.client_account_id);
                        const expanded = expandedAccountId === record.client_account_id;
                        const entries = entriesByAccount[record.client_account_id] ?? [];
                        return (
                          <Fragment key={record.client_account_id}>
                            <TableRow key={record.client_account_id} className="hover:bg-muted/30">
                              <TableCell><Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => void toggleCaseRecord(record)}>{expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</Button></TableCell>
                              <TableCell><p className="font-black">{record.client_name}</p><p className="text-xs text-muted-foreground">{record.account_reference} · {record.phone}</p></TableCell>
                              <TableCell><div className="flex flex-wrap gap-1"><Badge variant="secondary" className="rounded-full">{record.comment_count} comments</Badge><Badge variant="outline" className="rounded-full">{record.legal_action_count} legal actions</Badge></div></TableCell>
                              <TableCell><p className="font-semibold">{displayEntryType(record.latest_entry_kind)}</p><p className="mt-1 text-xs text-muted-foreground">{formatDateTime(record.latest_entry_at)}</p><p className="mt-1 max-w-md truncate text-xs text-muted-foreground">{record.latest_entry_preview}</p></TableCell>
                              <TableCell>{record.open_legal_action_count > 0 ? <Badge variant="destructive">{record.open_legal_action_count} open</Badge> : record.legal_action_count > 0 ? <Badge variant="outline">No open action</Badge> : <span className="text-xs text-muted-foreground">No legal action</span>}</TableCell>
                              <TableCell className="text-right"><div className="flex justify-end gap-2">{client ? <><Button size="sm" variant="outline" onClick={() => onViewProfile(client)}><UserRound className="h-3.5 w-3.5" />Profile</Button><Button size="sm" variant="outline" onClick={() => openEntryDialog(client, "comment")}><MessageSquarePlus className="h-3.5 w-3.5" />Comment</Button><Button size="sm" variant="outline" onClick={() => openEntryDialog(client, "legal_action")}><Gavel className="h-3.5 w-3.5" />Legal action</Button></> : null}</div></TableCell>
                            </TableRow>
                            {expanded ? (
                              <TableRow key={`${record.client_account_id}-expanded`} className="bg-muted/15 hover:bg-muted/15">
                                <TableCell colSpan={6} className="p-0">
                                  <div className="border-y bg-background/80 px-6 py-5">
                                    <div className="mb-3 flex items-center justify-between gap-3"><div><p className="font-black">Complete comment & legal timeline</p><p className="text-xs text-muted-foreground">Newest entries appear first.</p></div><Badge variant="outline">{entries.length} entries</Badge></div>
                                    {entriesLoadingAccountId === record.client_account_id ? <p className="py-8 text-center text-sm text-muted-foreground">Loading timeline...</p> : (
                                      <div className="space-y-3">
                                        {entries.map((entry) => (
                                          <div key={entry.id} className="grid gap-3 rounded-xl border bg-background p-4 md:grid-cols-[150px_minmax(0,1fr)_180px]">
                                            <div><Badge variant={entry.entry_type === "legal_action" ? "destructive" : "secondary"}>{displayEntryType(entry.entry_type)}</Badge><p className="mt-2 text-xs font-semibold">{titleCase(entry.category)}</p><p className="mt-1 text-[10px] text-muted-foreground">{formatDateTime(entry.action_date || entry.created_at)}</p></div>
                                            <div><p className="font-bold">{entry.title || (entry.entry_type === "legal_action" ? "Legal action" : "Comment")}</p><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{entry.body}</p>{entry.reference_number ? <p className="mt-2 text-xs">Reference: <span className="font-mono font-semibold">{entry.reference_number}</span></p> : null}{entry.amount !== null ? <p className="mt-1 text-xs">Amount: <span className="font-bold">{formatMoney(entry.amount, entry.currency)}</span></p> : null}</div>
                                            <div className="md:text-right"><Badge variant="outline">{titleCase(entry.status)}</Badge><p className="mt-2 text-xs text-muted-foreground">Recorded by</p><p className="text-xs font-semibold">{entry.created_by_name || "Company user"}</p><p className="mt-1 text-[10px] text-muted-foreground">{formatDateTime(entry.created_at)}</p>{entry.entry_type === "legal_action" && !["completed", "withdrawn", "closed", "resolved"].includes(entry.status) ? <Button size="sm" variant="outline" className="mt-3 h-7" disabled={caseStatusSavingId === entry.id} onClick={() => void markLegalActionCompleted(record.client_account_id, entry)}>{caseStatusSavingId === entry.id ? "Updating..." : "Mark completed"}</Button> : null}</div>
                                          </div>
                                        ))}
                                        {entries.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">No entries are available.</p> : null}
                                      </div>
                                    )}
                                  </div>
                                </TableCell>
                              </TableRow>
                            ) : null}
                          </Fragment>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </section>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={entryDialogOpen} onOpenChange={setEntryDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <div className="flex items-start gap-3">
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${entryMode === "legal_action" ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary"}`}>
                {entryMode === "legal_action" ? <Scale className="h-5 w-5" /> : <MessageSquarePlus className="h-5 w-5" />}
              </div>
              <div>
                <DialogTitle>{entryMode === "legal_action" ? "Record legal action" : "Add client comment"}</DialogTitle>
                <DialogDescription className="mt-1">{entryClient ? `${entryClient.full_name} · ${entryClient.account_reference}` : "Client case history"}</DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="grid gap-4 py-2 sm:grid-cols-2">
            <FilterField label={entryMode === "legal_action" ? "Legal action type" : "Comment category"}>
              <Select value={entryForm.category ?? "general"} onValueChange={(value) => setEntryForm((current) => ({ ...current, category: value }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{(entryMode === "legal_action" ? LEGAL_ACTION_TYPES : COMMENT_CATEGORIES).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
              </Select>
            </FilterField>
            {entryMode === "legal_action" ? (
              <FilterField label="Action status">
                <Select value={entryForm.status ?? "open"} onValueChange={(value) => setEntryForm((current) => ({ ...current, status: value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{LEGAL_STATUSES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select>
              </FilterField>
            ) : <div />}

            <FilterField label="Title / subject"><Input value={entryForm.title ?? ""} onChange={(event) => setEntryForm((current) => ({ ...current, title: event.target.value }))} placeholder={entryMode === "legal_action" ? "e.g. Final demand issued" : "Optional subject"} /></FilterField>
            {entryMode === "legal_action" ? <FilterField label="Action date"><Input type="datetime-local" value={entryForm.action_date ?? ""} onChange={(event) => setEntryForm((current) => ({ ...current, action_date: event.target.value }))} /></FilterField> : <div />}

            {entryMode === "legal_action" ? <><FilterField label="Reference / case number"><Input value={entryForm.reference_number ?? ""} onChange={(event) => setEntryForm((current) => ({ ...current, reference_number: event.target.value }))} placeholder="Attorney, court or notice reference" /></FilterField><FilterField label="Amount involved"><Input type="number" min="0" step="0.01" value={entryForm.amount ?? ""} onChange={(event) => setEntryForm((current) => ({ ...current, amount: event.target.value === "" ? null : Number(event.target.value) }))} placeholder="Optional" /></FilterField></> : null}

            <div className="sm:col-span-2">
              <FilterField label={entryMode === "legal_action" ? "Action notes" : "Comment"}>
                <Textarea value={entryForm.body} onChange={(event) => setEntryForm((current) => ({ ...current, body: event.target.value }))} rows={7} placeholder={entryMode === "legal_action" ? "Record what legal action was taken, by whom, the current position, next step and any important dates." : "Record the client contact, repayment promise, collection note, risk observation or other internal comment."} />
              </FilterField>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEntryDialogOpen(false)} disabled={entrySaving}>Cancel</Button>
            <LoadingButton loading={entrySaving} loadingText="Saving..." onClick={() => void submitCaseEntry()}>{entryMode === "legal_action" ? <Gavel className="h-4 w-4" /> : <MessageSquarePlus className="h-4 w-4" />}{entryMode === "legal_action" ? "Save legal action" : "Save comment"}</LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
