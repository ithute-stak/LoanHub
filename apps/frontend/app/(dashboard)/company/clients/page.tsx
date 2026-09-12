"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  BadgeCheck,
  Banknote,
  BookOpenCheck,
  BriefcaseBusiness,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  CircleCheckBig,
  ClipboardCheck,
  ContactRound,
  FileText,
  IdCard,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  Maximize2,
  Landmark,
  PackagePlus,
  Plus,
  Phone,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  UserRound,
  UserRoundPlus,
  UsersRound,
} from "lucide-react";

import { branchApi } from "@/api/branch";
import { expenseManagementApi } from "@/api/expenseManagement";
import {
  checkCompanyClientExistingLoans,
  createInternalClientLoanRequest,
  getCompanyClientPortfolioInsights,
  listCompanyClients,
  openCompanyClientAccount,
  settleCompanyClientOpeningFee,
} from "@/api/companyClients";
import { listLoanProducts } from "@/api/loanProducts";
import { calculateLoan } from "@/api/loans";
import { MicroLoanPreview } from "@/components/loans/micro-loan-preview";
import { CompanyClientDirectoryWorkspace } from "@/components/clients/company-client-directory-workspace";
import { CompanyClientProfileDialog } from "@/components/clients/company-client-profile-dialog";
import { EmployerGroupRegistrationField } from "@/components/clients/employer-group-registration-field";
import {
  ExternalDebtRegistrationFields,
  activeExternalDebtBalance,
  blankExternalDebt,
  monthlyExternalDebtCommitment,
} from "@/components/clients/external-debt-registration-fields";
import { InstallmentDueDateFields, installmentDueDatesComplete, resizeInstallmentDueDates } from "@/components/loans/installment-due-date-fields";
import { DEFAULT_PAYMENT_METHOD_OPTIONS, EMPTY_PAYMENT_EVIDENCE, PaymentMethodFields, type PaymentEvidence } from "@/components/payments/payment-method-fields";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import type { Branch } from "@/types/branch";
import type {
  AssistedCompanyClientCreate,
  CompanyClient,
  CompanyClientCaseEntry,
  CompanyClientExistingLoanCheck,
  CompanyClientExternalDebtInput,
  CompanyClientPortfolioInsights,
  InternalClientLoanRequestCreate,
} from "@/types/companyClient";
import type { PaymentMethodOption } from "@/types/expenseManagement";
import type { MicroLoanCalculation } from "@/types/loan";
import type { LoanProduct } from "@/types/loanProduct";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";
import {
  GLOBAL_BORROWER_LOOKUP_EVENT,
  type GlobalBorrowerLookupDetail,
} from "@/utils/borrowerLookup";

const emptyClient: AssistedCompanyClientCreate = {
  branch_id: null,
  email: null,
  phone: "",
  temporary_password: "",
  first_name: "",
  middle_name: null,
  last_name: "",
  gender: "male",
  date_of_birth: "",
  national_id: null,
  passport_number: null,
  marital_status: null,
  nationality: "Mosotho",
  district: "",
  town_or_village: null,
  physical_address: null,
  employment_status: "employed",
  employer_name: null,
  employer_group_id: null,
  new_employer_group: null,
  income_day: null,
  job_title: null,
  monthly_income: null,
  salary_date: null,
  has_existing_loans: false,
  existing_loan_total: 0,
  consent_to_share_profile: false,
  consent_to_credit_checks: false,
  external_debts: [],
};

const emptyLoan: InternalClientLoanRequestCreate = {
  branch_id: null,
  product_id: null,
  requested_amount: 0,
  term_count: 3,
  repayment_type: "monthly",
  purpose: null,
  installment_due_dates: resizeInstallmentDueDates([], 3),
};

const CLIENT_STEPS = [
  {
    title: "Personal details",
    shortTitle: "Personal",
    description: "Name, contact and login access",
    icon: ContactRound,
  },
  {
    title: "Identity and address",
    shortTitle: "Identity",
    description: "Identity verification and residence",
    icon: IdCard,
  },
  {
    title: "Employment and loans",
    shortTitle: "Affordability",
    description: "Income, employment and existing debt",
    icon: BriefcaseBusiness,
  },
  {
    title: "Consent and review",
    shortTitle: "Review",
    description: "Confirm details and borrower consent",
    icon: ClipboardCheck,
  },
] as const;

type ClientStep = 0 | 1 | 2 | 3;

type DirectoryFilters = {
  loanStatus: string;
  employmentStatus: string;
  employer: string;
  branchId: string;
  openingFeeStatus: string;
  dueWindow: string;
  salaryWindow: string;
  bankState: string;
  loanState: string;
  bankLast4: string;
  overdueOnly: boolean;
  groupBy: "none" | "employment" | "employer";
};

const EMPTY_DIRECTORY_FILTERS: DirectoryFilters = {
  loanStatus: "all",
  employmentStatus: "all",
  employer: "all",
  branchId: "all",
  openingFeeStatus: "all",
  dueWindow: "all",
  salaryWindow: "all",
  bankState: "all",
  loanState: "all",
  bankLast4: "",
  overdueOnly: false,
  groupBy: "none",
};

const LAST_CLIENT_STEP = CLIENT_STEPS.length - 1;

function optional(value: string | null | undefined): string | null {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null;
  const target = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (Number.isNaN(target.getTime())) return null;
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

function withinWindow(value: string | null | undefined, windowValue: string): boolean {
  if (windowValue === "all") return true;
  const days = daysUntil(value);
  if (days === null) return false;
  const windowDays = Number(windowValue);
  return days >= 0 && days <= windowDays;
}

export default function CompanyClientsPage() {
  const router = useRouter();
  const [clients, setClients] = useState<CompanyClient[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [products, setProducts] = useState<LoanProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [directoryFilters, setDirectoryFilters] = useState<DirectoryFilters>(EMPTY_DIRECTORY_FILTERS);
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [directoryInitialSearch, setDirectoryInitialSearch] = useState("");
  const [directoryPage, setDirectoryPage] = useState(1);
  const [directoryPageSize, setDirectoryPageSize] = useState(15);
  const [portfolioInsights, setPortfolioInsights] = useState<CompanyClientPortfolioInsights | null>(null);
  const [clientDialog, setClientDialog] = useState(false);
  const [loanDialog, setLoanDialog] = useState(false);
  const [feeDialog, setFeeDialog] = useState(false);
  const [settlingFee, setSettlingFee] = useState(false);
  const [feeClient, setFeeClient] = useState<CompanyClient | null>(null);
  const [feeEvidence, setFeeEvidence] = useState<PaymentEvidence>(EMPTY_PAYMENT_EVIDENCE);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodOption[]>(DEFAULT_PAYMENT_METHOD_OPTIONS);
  const [selectedClient, setSelectedClient] = useState<CompanyClient | null>(null);
  const [profileClient, setProfileClient] = useState<CompanyClient | null>(null);
  const [clientForm, setClientForm] = useState<AssistedCompanyClientCreate>(emptyClient);
  const [loanForm, setLoanForm] = useState<InternalClientLoanRequestCreate>(emptyLoan);
  const [calculation, setCalculation] = useState<MicroLoanCalculation | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [existingLoanCheck, setExistingLoanCheck] = useState<CompanyClientExistingLoanCheck | null>(null);
  const [existingLoanCheckStatus, setExistingLoanCheckStatus] = useState<"idle" | "checking" | "ready" | "error">("idle");
  const [existingLoanCheckError, setExistingLoanCheckError] = useState<string | null>(null);
  const [existingLoanCheckNonce, setExistingLoanCheckNonce] = useState(0);
  const [clientStep, setClientStep] = useState<ClientStep>(0);
  const [clientStepErrors, setClientStepErrors] = useState<string[]>([]);

  const applyGlobalBorrowerLookup = useCallback((detail: GlobalBorrowerLookupDetail) => {
    const nationalId = detail.nationalId.trim();
    if (nationalId.length < 8) return;

    if (detail.action === "history") {
      setSearch(nationalId);
      setDirectoryInitialSearch(nationalId);
      setDirectoryPage(1);
      setDirectoryOpen(true);
      return;
    }

    setClientForm({ ...emptyClient, national_id: nationalId });
    setExistingLoanCheck(null);
    setExistingLoanCheckStatus("idle");
    setExistingLoanCheckError(null);
    setExistingLoanCheckNonce(0);
    setClientStep(0);
    setClientStepErrors([]);
    setClientDialog(true);
  }, []);

  useEffect(() => {
    function handleGlobalLookup(event: Event) {
      const detail = (event as CustomEvent<GlobalBorrowerLookupDetail>).detail;
      if (!detail) return;
      applyGlobalBorrowerLookup(detail);
      window.history.replaceState(null, "", window.location.pathname);
    }

    window.addEventListener(GLOBAL_BORROWER_LOOKUP_EVENT, handleGlobalLookup);

    const params = new URLSearchParams(window.location.search);
    const nationalId = params.get("national_id")?.trim() ?? "";
    const requestedAction = params.get("action");
    const action = requestedAction === "new" || requestedAction === "link" || requestedAction === "history"
      ? requestedAction
      : null;
    if (nationalId.length >= 8 && action) {
      const timer = window.setTimeout(() => {
        applyGlobalBorrowerLookup({ action, nationalId });
        window.history.replaceState(null, "", window.location.pathname);
      }, 0);
      return () => {
        window.removeEventListener(GLOBAL_BORROWER_LOOKUP_EVENT, handleGlobalLookup);
        window.clearTimeout(timer);
      };
    }

    return () => window.removeEventListener(GLOBAL_BORROWER_LOOKUP_EVENT, handleGlobalLookup);
  }, [applyGlobalBorrowerLookup]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [clientRows, branchResponse, productRows, methodRows, insightRows] = await Promise.all([
        listCompanyClients({ limit: 1000 }),
        branchApi.getAll(),
        listLoanProducts(),
        expenseManagementApi.paymentMethods().catch(() => DEFAULT_PAYMENT_METHOD_OPTIONS),
        getCompanyClientPortfolioInsights(14).catch(() => null),
      ]);
      setClients(clientRows);
      setPortfolioInsights(insightRows);
      setBranches(branchResponse.data.filter((item) => item.is_active));
      setProducts(productRows.filter((item) => item.is_active));
      setPaymentMethods(methodRows);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Company clients could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    const nationalId = String(clientForm.national_id ?? "").trim();
    if (!clientDialog || nationalId.length < 8) {
      setExistingLoanCheck(null);
      setExistingLoanCheckStatus("idle");
      setExistingLoanCheckError(null);
      return;
    }

    const controller = new AbortController();
    setExistingLoanCheck(null);
    setExistingLoanCheckStatus("checking");
    setExistingLoanCheckError(null);

    const timer = window.setTimeout(() => {
      void checkCompanyClientExistingLoans(nationalId, controller.signal)
        .then((result) => {
          if (controller.signal.aborted) return;
          setExistingLoanCheck(result);
          setExistingLoanCheckStatus("ready");
          setClientForm((current) => {
            if (String(current.national_id ?? "").trim() !== nationalId) return current;
            const trackedDebts: CompanyClientExternalDebtInput[] = result.external_debts.length > 0
              ? result.external_debts.map((row) => ({
                  creditor: row.creditor,
                  account_reference: row.account_reference,
                  debt_type: row.debt_type,
                  started_on: row.started_on,
                  original_amount: Number(row.original_amount || 0),
                  current_balance: Number(row.current_balance || 0),
                  installment_amount: Number(row.installment_amount || 0),
                  installment_frequency: row.installment_frequency,
                  total_installments: row.total_installments,
                  installments_paid: Number(row.installments_paid || 0),
                  remaining_installments: row.remaining_installments,
                  next_due_date: row.next_due_date,
                  status: row.status,
                  source: row.source,
                  is_verified: row.is_verified,
                  notes: row.notes,
                }))
              : Number(result.declared_existing_loan_total || 0) > 0
                ? [{
                    ...blankExternalDebt(),
                    creditor: "Borrower-declared external lender",
                    original_amount: Number(result.declared_existing_loan_total || 0),
                    current_balance: Number(result.declared_existing_loan_total || 0),
                    status: "unknown",
                    source: "legacy_registration",
                    notes: "Review this legacy balance and complete its start date and installment schedule.",
                  }]
                : current.external_debts;
            const externalBalance = activeExternalDebtBalance(trackedDebts);
            return {
              ...current,
              temporary_password: result.borrower_found ? null : current.temporary_password,
              external_debts: trackedDebts,
              has_existing_loans: result.active_loan_count > 0 || externalBalance > 0,
              existing_loan_total: externalBalance,
            };
          });
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          setExistingLoanCheck(null);
          setExistingLoanCheckStatus("error");
          setExistingLoanCheckError(
            getErrorMessage(error, "The existing-loan check could not be completed."),
          );
        });
    }, 500);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [clientDialog, clientForm.national_id, existingLoanCheckNonce]);

  const selectedProduct = useMemo(
    () => products.find((product) => product.id === loanForm.product_id) ?? null,
    [loanForm.product_id, products],
  );

  useEffect(() => {
    setLoanForm((current) => ({
      ...current,
      installment_due_dates: resizeInstallmentDueDates(current.installment_due_dates, Number(current.term_count || 0)),
    }));
  }, [loanForm.term_count]);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      const amount = Number(loanForm.requested_amount);
      const months = Number(loanForm.term_count);
      if (!selectedProduct || amount <= 0 || months <= 0 || !installmentDueDatesComplete(loanForm.installment_due_dates, months)) {
        setCalculation(null);
        setCalculating(false);
        return;
      }

      setCalculating(true);
      void calculateLoan({
        principal: amount,
        rate_percent: Number(selectedProduct.interest_rate_percent),
        months,
        processing_fee: Number(selectedProduct.processing_fee),
        interest_method: selectedProduct.interest_method,
        due_dates: loanForm.installment_due_dates,
      })
        .then((result) => {
          if (!cancelled) setCalculation(result);
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setCalculation(null);
            toast.error(getErrorMessage(error, "The loan calculation could not be completed."));
          }
        })
        .finally(() => {
          if (!cancelled) setCalculating(false);
        });
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [loanForm.installment_due_dates, loanForm.requested_amount, loanForm.term_count, selectedProduct]);

  const employerOptions = useMemo(
    () => Array.from(new Set(clients.map((item) => item.employer_name?.trim()).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b)),
    [clients],
  );

  const filtered = useMemo(() => {
    const value = search.trim().toLowerCase();
    const bankLast4 = directoryFilters.bankLast4.replace(/\D/g, "").slice(-4);
    const rows = clients.filter((client) => {
      if (value && ![
        client.full_name,
        client.account_reference,
        client.phone,
        client.email,
        client.national_id,
        client.passport_number,
        client.employer_name,
        client.bank_name,
        client.bank_account_last4,
        client.recent_loan_reference,
      ].filter(Boolean).some((item) => String(item).toLowerCase().includes(value))) return false;

      if (directoryFilters.loanStatus !== "all") {
        if (directoryFilters.loanStatus === "none" && client.loan_count !== 0) return false;
        if (directoryFilters.loanStatus !== "none" && !client.loan_statuses.includes(directoryFilters.loanStatus)) return false;
      }
      if (directoryFilters.employmentStatus !== "all" && client.employment_status !== directoryFilters.employmentStatus) return false;
      if (directoryFilters.employer !== "all" && client.employer_name !== directoryFilters.employer) return false;
      if (directoryFilters.branchId !== "all" && client.branch_id !== directoryFilters.branchId) return false;
      if (directoryFilters.openingFeeStatus !== "all" && client.opening_fee_status !== directoryFilters.openingFeeStatus) return false;
      if (!withinWindow(client.next_due_date, directoryFilters.dueWindow)) return false;
      if (!withinWindow(client.next_salary_pay_date, directoryFilters.salaryWindow)) return false;
      if (directoryFilters.bankState === "with" && !client.has_bank_account) return false;
      if (directoryFilters.bankState === "without" && client.has_bank_account) return false;
      if (directoryFilters.loanState === "with" && client.loan_count <= 0) return false;
      if (directoryFilters.loanState === "without" && client.loan_count > 0) return false;
      if (bankLast4 && !String(client.bank_account_last4 ?? "").endsWith(bankLast4)) return false;
      if (directoryFilters.overdueOnly && client.overdue_installment_count <= 0) return false;
      return true;
    });

    if (directoryFilters.groupBy === "employment") {
      return [...rows].sort((a, b) => `${a.employment_status}|${a.full_name}`.localeCompare(`${b.employment_status}|${b.full_name}`));
    }
    if (directoryFilters.groupBy === "employer") {
      return [...rows].sort((a, b) => `${a.employer_name || "~Unemployed / no employer"}|${a.full_name}`.localeCompare(`${b.employer_name || "~Unemployed / no employer"}|${b.full_name}`));
    }
    return rows;
  }, [clients, directoryFilters, search]);

  const activeFilterCount = useMemo(
    () => Object.entries(directoryFilters).filter(([key, value]) => {
      if (key === "groupBy") return value !== "none";
      if (key === "overdueOnly") return value === true;
      if (key === "bankLast4") return Boolean(value);
      return value !== "all";
    }).length,
    [directoryFilters],
  );

  const directoryPageCount = Math.max(1, Math.ceil(filtered.length / directoryPageSize));
  const paginatedClients = useMemo(() => {
    const start = (directoryPage - 1) * directoryPageSize;
    return filtered.slice(start, start + directoryPageSize);
  }, [directoryPage, directoryPageSize, filtered]);
  const directoryRangeStart = filtered.length === 0 ? 0 : ((directoryPage - 1) * directoryPageSize) + 1;
  const directoryRangeEnd = Math.min(directoryPage * directoryPageSize, filtered.length);

  useEffect(() => {
    setDirectoryPage(1);
  }, [directoryFilters, search, directoryPageSize]);

  useEffect(() => {
    setDirectoryPage((current) => Math.min(current, directoryPageCount));
  }, [directoryPageCount]);


  const activeCount = useMemo(
    () => clients.filter((item) => item.status === "active").length,
    [clients],
  );
  const accruedFees = useMemo(
    () => clients
      .filter((item) => item.opening_fee_status !== "paid" && item.opening_fee_status !== "not_required")
      .reduce((sum, item) => sum + Number(item.opening_fee_amount || 0), 0),
    [clients],
  );

  const existingBorrowerFound = existingLoanCheck?.borrower_found === true;
  const borrowerAlreadyLinked = existingLoanCheck?.already_company_client === true;
  const existingLoanFieldsLocked = existingLoanCheckStatus === "checking" || borrowerAlreadyLinked;
  const externalDebtBalanceTotal = activeExternalDebtBalance(clientForm.external_debts);
  const externalDebtMonthlyCommitment = monthlyExternalDebtCommitment(clientForm.external_debts);
  const loanHubOutstandingTotal = Number(existingLoanCheck?.loanhub_outstanding_total || 0);
  const combinedExistingExposure = externalDebtBalanceTotal + loanHubOutstandingTotal;
  const activeClientStep = CLIENT_STEPS[clientStep];
  const ActiveClientStepIcon = activeClientStep.icon;
  const clientProgress = ((clientStep + 1) / CLIENT_STEPS.length) * 100;

  function resetClientDialog() {
    setClientForm(emptyClient);
    setExistingLoanCheck(null);
    setExistingLoanCheckStatus("idle");
    setExistingLoanCheckError(null);
    setExistingLoanCheckNonce(0);
    setClientStep(0);
    setClientStepErrors([]);
  }

  function updateDirectoryFilter<K extends keyof DirectoryFilters>(key: K, value: DirectoryFilters[K]) {
    setDirectoryFilters((current) => ({ ...current, [key]: value }));
  }

  function clearDirectoryFilters() {
    setDirectoryFilters(EMPTY_DIRECTORY_FILTERS);
    setSearch("");
    setDirectoryPage(1);
  }

  function showUpcomingPaydayLoans(days = 7) {
    setDirectoryFilters((current) => ({
      ...current,
      bankState: "with",
      loanState: "with",
      salaryWindow: String(days),
    }));
    setDirectoryPage(1);
    setDirectoryOpen(true);
  }

  function updateClient<K extends keyof AssistedCompanyClientCreate>(
    key: K,
    value: AssistedCompanyClientCreate[K],
  ) {
    setClientStepErrors([]);
    setClientForm((current) => ({ ...current, [key]: value }));
  }

  function updateExternalDebts(debts: CompanyClientExternalDebtInput[]) {
    const balance = activeExternalDebtBalance(debts);
    setClientStepErrors([]);
    setClientForm((current) => ({
      ...current,
      external_debts: debts,
      existing_loan_total: balance,
      has_existing_loans: balance > 0 || Number(existingLoanCheck?.active_loan_count || 0) > 0,
    }));
  }

  function validateClientStep(step: ClientStep): string[] {
    const errors: string[] = [];
    const nationalId = String(clientForm.national_id ?? "").trim();
    const passport = String(clientForm.passport_number ?? "").trim();

    if (step === 0) {
      if (!clientForm.first_name.trim()) errors.push("Enter the borrower’s first name.");
      if (!clientForm.last_name.trim()) errors.push("Enter the borrower’s last name.");
      if (!clientForm.phone.trim()) errors.push("Enter a phone number the borrower can access.");
      if (!clientForm.date_of_birth) errors.push("Select the borrower’s date of birth.");
      if (clientForm.email && !String(clientForm.email).includes("@")) {
        errors.push("Enter a valid email address or leave the email field blank.");
      }
      if (!existingBorrowerFound && String(clientForm.temporary_password ?? "").length < 10) {
        errors.push("Create a temporary password with at least 10 characters.");
      }
    }

    if (step === 1) {
      if (!nationalId && !passport) errors.push("Enter either a national ID or passport number.");
      if (nationalId && nationalId.length < 8) errors.push("The national ID must contain at least 8 characters.");
      if (!clientForm.district.trim()) errors.push("Enter the borrower’s district.");
      if (existingLoanCheckStatus === "checking") errors.push("Wait for the national-ID loan check to finish.");
      if (nationalId && existingLoanCheckStatus === "error") {
        errors.push("Retry the national-ID loan check before continuing.");
      }
      if (borrowerAlreadyLinked) errors.push("This borrower is already linked to the active company.");
    }

    if (step === 2) {
      if (Number(clientForm.monthly_income ?? 0) < 0) errors.push("Monthly income cannot be negative.");
      const needsIncomeDay = ["employed", "self_employed", "pensioner"].includes(clientForm.employment_status);
      if (clientForm.employment_status === "employed" && !clientForm.employer_group_id && !clientForm.new_employer_group) {
        errors.push("Select the borrower’s employer/work group or add a new group.");
      }
      if (needsIncomeDay && !clientForm.income_day) {
        errors.push("Enter the borrower’s normal income/pay day (1–31).");
      }
      clientForm.external_debts.forEach((debt, index) => {
        const label = `Existing loan ${index + 1}`;
        if (!debt.creditor.trim()) errors.push(`${label}: enter the lender or creditor.`);
        if (!debt.started_on) errors.push(`${label}: enter when the loan started.`);
        if (debt.started_on && debt.started_on > new Date().toISOString().slice(0, 10)) errors.push(`${label}: the start date cannot be in the future.`);
        if (Number(debt.original_amount || 0) <= 0) errors.push(`${label}: enter the original loan amount.`);
        if (Number(debt.current_balance || 0) < 0) errors.push(`${label}: the balance cannot be negative.`);
        if (Number(debt.current_balance || 0) > 0 && Number(debt.installment_amount || 0) <= 0) errors.push(`${label}: enter the installment amount.`);
        if (Number(debt.current_balance || 0) > 0 && (debt.remaining_installments === null || debt.remaining_installments === undefined)) errors.push(`${label}: enter how many installments remain.`);
        if (debt.total_installments !== null && debt.total_installments !== undefined && Number(debt.installments_paid || 0) > Number(debt.total_installments)) errors.push(`${label}: paid installments cannot exceed total installments.`);
      });
    }

    if (step === 3) {
      if (!clientForm.consent_to_credit_checks) {
        errors.push("Confirm the borrower’s consent to permitted credit checks.");
      }
      if (!clientForm.consent_to_share_profile) {
        errors.push("Confirm the borrower’s consent to share the profile with this company.");
      }
      if (borrowerAlreadyLinked) errors.push("This borrower is already linked to the active company.");
    }

    return errors;
  }

  function moveToClientStep(target: ClientStep) {
    if (target <= clientStep) {
      setClientStepErrors([]);
      setClientStep(target);
      return;
    }

    const errors = validateClientStep(clientStep);
    if (errors.length > 0) {
      setClientStepErrors(errors);
      toast.warning("Complete this step before continuing.", {
        description: errors[0],
      });
      return;
    }

    setClientStepErrors([]);
    setClientStep(target);
  }

  function nextClientStep() {
    if (clientStep >= LAST_CLIENT_STEP) return;
    moveToClientStep((clientStep + 1) as ClientStep);
  }

  function previousClientStep() {
    if (clientStep <= 0) return;
    setClientStepErrors([]);
    setClientStep((clientStep - 1) as ClientStep);
  }

  function updateLoan<K extends keyof InternalClientLoanRequestCreate>(
    key: K,
    value: InternalClientLoanRequestCreate[K],
  ) {
    setLoanForm((current) => ({ ...current, [key]: value }));
  }

  async function submitClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (clientStep < LAST_CLIENT_STEP) {
      nextClientStep();
      return;
    }

    const firstInvalidStep = ([0, 1, 2, 3] as ClientStep[]).find(
      (step) => validateClientStep(step).length > 0,
    );
    if (firstInvalidStep !== undefined) {
      const errors = validateClientStep(firstInvalidStep);
      setClientStep(firstInvalidStep);
      setClientStepErrors(errors);
      toast.warning("Review the borrower registration details.", {
        description: errors[0],
      });
      return;
    }

    if (existingLoanCheckStatus === "checking") {
      toast.warning("Please wait for the existing-loan check to finish.");
      return;
    }
    if (borrowerAlreadyLinked) {
      toast.error("This borrower already belongs to the active company.");
      return;
    }
    setSaving(true);
    try {
      const normalizedDebts = clientForm.external_debts.map((debt) => ({
        ...debt,
        creditor: debt.creditor.trim(),
        account_reference: optional(debt.account_reference),
        debt_type: debt.debt_type || "other",
        started_on: optional(debt.started_on),
        original_amount: Number(debt.original_amount || 0),
        current_balance: Number(debt.current_balance || 0),
        installment_amount: Number(debt.installment_amount || 0),
        total_installments: debt.total_installments === null || debt.total_installments === undefined ? null : Number(debt.total_installments),
        installments_paid: Number(debt.installments_paid || 0),
        remaining_installments: debt.remaining_installments === null || debt.remaining_installments === undefined ? null : Number(debt.remaining_installments),
        next_due_date: optional(debt.next_due_date),
        notes: optional(debt.notes),
      }));
      const created = await openCompanyClientAccount({
        ...clientForm,
        external_debts: normalizedDebts,
        has_existing_loans: normalizedDebts.some((debt) => Number(debt.current_balance || 0) > 0) || Number(existingLoanCheck?.active_loan_count || 0) > 0,
        existing_loan_total: activeExternalDebtBalance(normalizedDebts),
        temporary_password: existingBorrowerFound ? null : optional(clientForm.temporary_password),
        email: optional(clientForm.email),
        middle_name: optional(clientForm.middle_name),
        national_id: optional(clientForm.national_id),
        passport_number: optional(clientForm.passport_number),
        nationality: optional(clientForm.nationality),
        town_or_village: optional(clientForm.town_or_village),
        physical_address: optional(clientForm.physical_address),
        employer_name: optional(clientForm.employer_name),
        job_title: optional(clientForm.job_title),
        salary_date: clientForm.income_day ? String(clientForm.income_day) : optional(clientForm.salary_date),
      });
      setClients((current) => [created, ...current]);
      resetClientDialog();
      setClientDialog(false);
      toast.success("Borrower account opened", {
        description: created.opening_fee_amount > 0
          ? `${formatMoney(created.opening_fee_amount)} was accrued to the company account.`
          : "The borrower is ready for an internal loan application.",
      });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The borrower account could not be opened."));
    } finally {
      setSaving(false);
    }
  }

  function startInternalLoan(client: CompanyClient) {
    const defaultProduct = products[0] ?? null;
    setSelectedClient(client);
    setLoanForm({
      ...emptyLoan,
      branch_id: client.branch_id,
      product_id: defaultProduct?.id ?? null,
      requested_amount: defaultProduct ? Number(defaultProduct.min_amount) : 0,
      term_count: defaultProduct?.min_term_months ?? 3,
      installment_due_dates: resizeInstallmentDueDates([], defaultProduct?.min_term_months ?? 3),
    });
    setCalculation(null);
    setLoanDialog(true);
  }

  async function submitInternalLoan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedClient || !selectedProduct || !calculation) return;
    setSaving(true);
    try {
      const created = await createInternalClientLoanRequest(selectedClient.id, {
        ...loanForm,
        product_id: selectedProduct.id,
        purpose: optional(loanForm.purpose),
      });
      setLoanDialog(false);
      setSelectedClient(null);
      toast.success("Private loan request created", {
        description: `${created.application_reference} is ready for review and is not broadcast to the marketplace.`,
      });
      router.push(`/company/marketplace?workspace=applications&application=${encodeURIComponent(created.id)}`);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The internal loan request could not be created."));
    } finally {
      setSaving(false);
    }
  }

  function startOpeningFeeSettlement(client: CompanyClient) {
    setFeeClient(client);
    setFeeEvidence(EMPTY_PAYMENT_EVIDENCE);
    setFeeDialog(true);
  }

  async function submitOpeningFeeSettlement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!feeClient) return;
    setSettlingFee(true);
    try {
      if (feeEvidence.payment_method !== "cash" && feeEvidence.payment_method !== "lelefapaygate" && !feeEvidence.proof_reference.trim() && !feeEvidence.proof_url.trim()) {
        toast.warning("Enter a proof reference or proof document location.");
        return;
      }
      const payment = await settleCompanyClientOpeningFee(feeClient.id, {
        payment_method: feeEvidence.payment_method,
        proof_reference: optional(feeEvidence.proof_reference),
        proof_url: optional(feeEvidence.proof_url),
        proof_notes: optional(feeEvidence.proof_notes),
        notes: optional(feeEvidence.proof_notes),
        idempotency_key: `opening-fee-${feeEvidence.payment_method}-${feeClient.id}-${feeClient.opening_fee_amount}`,
      });
      setClients((current) => current.map((item) => item.id === feeClient.id
        ? { ...item, opening_fee_status: "paid", opening_fee_payment_id: payment.id }
        : item));
      setFeeDialog(false);
      setFeeClient(null);
      toast.success("Opening charge settled", {
        description: `${formatMoney(payment.amount, payment.currency)} was recorded through ${paymentMethods.find((item) => item.value === payment.payment_method)?.label ?? titleCase(payment.payment_method)}.`,
      });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The assisted-opening charge could not be settled."));
    } finally {
      setSettlingFee(false);
    }
  }

  function handleCaseEntryCreated(accountId: string, entry: CompanyClientCaseEntry) {
    const closedLegalStatuses = new Set(["completed", "withdrawn", "closed", "resolved"]);
    setClients((current) => current.map((client) => {
      if (client.id !== accountId) return client;
      const legal = entry.entry_type === "legal_action";
      return {
        ...client,
        case_entry_count: client.case_entry_count + 1,
        comment_count: client.comment_count + (legal ? 0 : 1),
        legal_action_count: client.legal_action_count + (legal ? 1 : 0),
        open_legal_action_count: client.open_legal_action_count + (legal && !closedLegalStatuses.has(entry.status) ? 1 : 0),
        latest_case_entry_at: entry.created_at,
        latest_case_entry_kind: entry.entry_type,
      };
    }));
  }

  function handleCaseEntryStatusChanged(accountId: string, previousStatus: string, entry: CompanyClientCaseEntry) {
    const closedLegalStatuses = new Set(["completed", "withdrawn", "closed", "resolved"]);
    const wasOpen = !closedLegalStatuses.has(previousStatus);
    const isOpen = !closedLegalStatuses.has(entry.status);
    if (wasOpen === isOpen) return;
    setClients((current) => current.map((client) => client.id === accountId
      ? { ...client, open_legal_action_count: Math.max(0, client.open_legal_action_count + (isOpen ? 1 : -1)) }
      : client));
  }

  if (loading) return <PageLoader rows={7} />;

  return (
    <div className="loanhub-page space-y-6">
      <section className="loanhub-hero flex flex-col justify-between gap-5 p-6 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Company client book</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Borrower accounts and private lending</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
            Open verified borrower accounts and submit internal applications that remain private to this lending company.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh</Button>
          <Button variant="outline" asChild><Link href="/company/marketplace?workspace=applications"><BookOpenCheck className="h-4 w-4" />Process applications</Link></Button>
          <Button onClick={() => { resetClientDialog(); setClientDialog(true); }}><UserRoundPlus className="h-4 w-4" />Open borrower account</Button>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <Metric icon={UsersRound} label="Client book" value={String(clients.length)} hint="Borrowers opened by this company" />
        <Metric icon={BookOpenCheck} label="Active accounts" value={String(activeCount)} hint="Ready for internal applications" />
        <Metric icon={CircleDollarSign} label="Opening charges accrued" value={formatMoney(accruedFees)} hint="Company-to-platform opening charge" />
      </div>

      <Card className="overflow-visible rounded-3xl border-border/70 shadow-sm">
        <StickyFilterBar
          ariaLabel="Company client search and filters"
          className="rounded-t-3xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
        >
          <CardHeader className="rounded-[inherit] border-b bg-muted/20">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
                <div>
                  <CardTitle>Company clients</CardTitle>
                  <CardDescription>Search and filter by identity, employment, employer, loan status, due dates, salary pay dates and masked bank-account details.</CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" onClick={() => showUpcomingPaydayLoans(7)}>
                    <Landmark className="h-4 w-4" />Payday + loans
                  </Button>
                  <Button type="button" variant="outline" onClick={() => { setDirectoryPage(1); setDirectoryOpen(true); }}>
                    <Maximize2 className="h-4 w-4" />Open directory
                    {activeFilterCount > 0 ? <Badge variant="secondary">{activeFilterCount}</Badge> : null}
                  </Button>
                </div>
              </div>

              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
                <SuggestionSearch
                  value={search}
                  onValueChange={setSearch}
                  suggestions={clients.map((client) => ({
                    value: client.full_name || client.account_reference,
                    label: client.full_name || client.account_reference,
                    description: `${client.account_reference} · ${client.phone}`,
                    keywords: [
                      client.user_id,
                      client.borrower_id,
                      client.email ?? "",
                      client.national_id ?? "",
                      client.passport_number ?? "",
                      client.district ?? "",
                      client.employer_name ?? "",
                      client.bank_account_last4 ?? "",
                      client.recent_loan_reference ?? "",
                    ],
                  }))}
                  placeholder="Name, phone, ID, employer, loan ref..."
                  suggestionLabel="Company clients"
                  emptyMessage="No client matches that text."
                  wrapperClassName="md:col-span-2 xl:col-span-2"
                />
                <Select value={directoryFilters.loanStatus} onValueChange={(value) => updateDirectoryFilter("loanStatus", value)}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Loan status" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All loan statuses</SelectItem>
                    <SelectItem value="active">Active loans</SelectItem>
                    <SelectItem value="approved">Approved loans</SelectItem>
                    <SelectItem value="defaulted">Defaulted loans</SelectItem>
                    <SelectItem value="completed">Completed loans</SelectItem>
                    <SelectItem value="pending">Pending loans</SelectItem>
                    <SelectItem value="none">No loan history</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={directoryFilters.employmentStatus} onValueChange={(value) => updateDirectoryFilter("employmentStatus", value)}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Employment" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All employment</SelectItem>
                    <SelectItem value="employed">Employed</SelectItem>
                    <SelectItem value="self_employed">Self employed</SelectItem>
                    <SelectItem value="unemployed">Unemployed</SelectItem>
                    <SelectItem value="student">Student</SelectItem>
                    <SelectItem value="pensioner">Pensioner</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={directoryFilters.dueWindow} onValueChange={(value) => updateDirectoryFilter("dueWindow", value)}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Next due" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Any due date</SelectItem>
                    <SelectItem value="3">Due in 3 days</SelectItem>
                    <SelectItem value="7">Due in 7 days</SelectItem>
                    <SelectItem value="14">Due in 14 days</SelectItem>
                    <SelectItem value="30">Due in 30 days</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
        </StickyFilterBar>
        <CardContent className="overflow-hidden rounded-b-3xl p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader><TableRow><TableHead>Client</TableHead><TableHead>Employment</TableHead><TableHead>Loans</TableHead><TableHead>Next due</TableHead><TableHead>Bank</TableHead><TableHead>Opening charge</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow><TableCell colSpan={7} className="h-40 text-center text-muted-foreground">No company clients match the current filters.</TableCell></TableRow>
                ) : paginatedClients.map((client) => (
                  <TableRow key={client.id}>
                    <TableCell><p className="font-black">{client.full_name}</p><p className="text-xs text-muted-foreground">{client.account_reference} · {client.phone}</p></TableCell>
                    <TableCell><p className="font-semibold">{titleCase(client.employment_status)}</p><p className="text-xs text-muted-foreground">{client.employer_name || "No employer recorded"}</p></TableCell>
                    <TableCell><p className="font-black">{client.loan_count} loan{client.loan_count === 1 ? "" : "s"}</p><p className="text-xs text-muted-foreground">{formatMoney(client.outstanding_balance)} outstanding</p></TableCell>
                    <TableCell>
                      <p className="font-semibold">{client.next_due_date ? formatDate(client.next_due_date) : "—"}</p>
                      <p className="text-xs text-muted-foreground">{client.next_due_amount !== null ? formatMoney(client.next_due_amount) : client.overdue_installment_count > 0 ? `${client.overdue_installment_count} overdue` : "No upcoming installment"}</p>
                    </TableCell>
                    <TableCell><p className="font-semibold">{client.bank_name || "No bank"}</p><p className="font-mono text-xs text-muted-foreground">{client.masked_bank_account || "—"}</p></TableCell>
                    <TableCell><p className="font-black">{formatMoney(client.opening_fee_amount, client.opening_fee_currency)}</p><p className="text-xs text-muted-foreground">{titleCase(client.opening_fee_status)}</p></TableCell>
                    <TableCell className="text-right">
                      <div className="flex flex-wrap justify-end gap-2">
                        {client.opening_fee_amount > 0 && client.opening_fee_status !== "paid" ? (
                          <Button size="sm" variant="outline" onClick={() => startOpeningFeeSettlement(client)}><Banknote className="h-4 w-4" />Settle charge</Button>
                        ) : null}
                        <Button size="sm" variant="outline" onClick={() => setProfileClient(client)}><UserRound className="h-4 w-4" />Profile</Button>
                        <Button size="sm" variant="outline" asChild><Link href={`/company/calls?borrower=${encodeURIComponent(client.borrower_id)}`}><Phone className="h-4 w-4" />Call</Link></Button>
                        <Button size="sm" variant="outline" asChild><Link href={`/company/documents?client=${client.id}`}><FileText className="h-4 w-4" />Letters</Link></Button>
                        <Button size="sm" variant="outline" asChild disabled={client.status !== "active"}><Link href={`/company/origination/new?borrower=${client.borrower_id}`}><BookOpenCheck className="h-4 w-4" />Full assessment</Link></Button>
                        <Button size="sm" disabled={client.status !== "active"} onClick={() => startInternalLoan(client)}><Plus className="h-4 w-4" />Quick request</Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex flex-col gap-3 border-t bg-muted/15 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs font-medium text-muted-foreground">
              Showing <span className="font-bold text-foreground">{directoryRangeStart}-{directoryRangeEnd}</span> of{" "}
              <span className="font-bold text-foreground">{filtered.length}</span> clients
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Rows</span>
              <Select
                value={String(directoryPageSize)}
                onValueChange={(value) => {
                  setDirectoryPageSize(Number(value));
                  setDirectoryPage(1);
                }}
              >
                <SelectTrigger className="h-8 w-[76px]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">15</SelectItem>
                  <SelectItem value="30">30</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
              <Button type="button" size="sm" variant="outline" disabled={directoryPage <= 1} onClick={() => setDirectoryPage((page) => Math.max(1, page - 1))}>
                <ChevronLeft className="h-4 w-4" />Previous
              </Button>
              <Badge variant="outline" className="h-8 px-3">Page {directoryPage} of {directoryPageCount}</Badge>
              <Button type="button" size="sm" variant="outline" disabled={directoryPage >= directoryPageCount} onClick={() => setDirectoryPage((page) => Math.min(directoryPageCount, page + 1))}>
                Next<ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <CompanyClientDirectoryWorkspace
        open={directoryOpen}
        onOpenChange={setDirectoryOpen}
        clients={clients}
        branches={branches}
        portfolioInsights={portfolioInsights}
        initialSearch={directoryInitialSearch}
        onStartLoan={startInternalLoan}
        onSettleOpeningFee={startOpeningFeeSettlement}
        onViewProfile={setProfileClient}
        onCaseEntryCreated={handleCaseEntryCreated}
        onCaseEntryStatusChanged={handleCaseEntryStatusChanged}
      />

      <CompanyClientProfileDialog
        open={Boolean(profileClient)}
        client={profileClient}
        onOpenChange={(nextOpen) => { if (!nextOpen) setProfileClient(null); }}
        onStartLoan={startInternalLoan}
      />

      <CustomDialog
        open={clientDialog}
        onOpenChange={(open) => {
          if (saving) return;
          setClientDialog(open);
          if (!open) resetClientDialog();
        }}
        title="Open a borrower account"
        description="A guided four-step registration with automatic national-ID and existing-loan checks."
        banner="/loanhub-horizontal-logo.png"
        bannerAlt="LoanHub assisted borrower registration"
        contentClassName="w-[calc(100%-0.75rem)] sm:max-w-6xl"
        bodyClassName="flex min-h-0 flex-1 flex-col overflow-hidden"
      >
        <form onSubmit={submitClient} className="flex min-h-0 flex-1 flex-col">
          <div className="shrink-0 border-b bg-gradient-to-r from-primary/5 via-background to-emerald-500/5 px-4 py-4 sm:px-6 lg:px-7">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="bg-background/80">
                  <Sparkles className="h-3.5 w-3.5" />
                  Assisted registration
                </Badge>
                {existingLoanCheckStatus === "checking" && (
                  <Badge variant="secondary">
                    <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                    Checking national ID
                  </Badge>
                )}
                {existingBorrowerFound && (
                  <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
                    <UserRound className="h-3.5 w-3.5" />
                    Existing borrower profile
                  </Badge>
                )}
                {borrowerAlreadyLinked && (
                  <Badge variant="destructive">Already linked to this company</Badge>
                )}
              </div>
              <div className="min-w-48 sm:max-w-64 sm:flex-1">
                <div className="mb-1.5 flex items-center justify-between text-[11px] font-bold text-muted-foreground">
                  <span>Step {clientStep + 1} of {CLIENT_STEPS.length}</span>
                  <span>{Math.round(clientProgress)}%</span>
                </div>
                <Progress value={clientProgress} className="h-2" />
              </div>
            </div>
          </div>

          <div className="grid min-h-0 flex-1 lg:grid-cols-[250px_minmax(0,1fr)]">
            <aside className="hidden min-h-0 border-r bg-muted/15 p-4 lg:flex lg:flex-col">
              <div className="space-y-2">
                {CLIENT_STEPS.map((step, index) => {
                  const Icon = step.icon;
                  const completed = index < clientStep;
                  const active = index === clientStep;
                  const available = index <= clientStep + 1;
                  return (
                    <button
                      key={step.title}
                      type="button"
                      disabled={!available || saving}
                      onClick={() => moveToClientStep(index as ClientStep)}
                      className={`group flex w-full items-start gap-3 rounded-2xl border px-3 py-3 text-left transition ${
                        active
                          ? "border-primary/40 bg-primary/10 shadow-sm"
                          : completed
                            ? "border-emerald-500/25 bg-emerald-500/5 hover:bg-emerald-500/10"
                            : "border-transparent hover:border-border hover:bg-background"
                      } ${!available ? "cursor-not-allowed opacity-45" : ""}`}
                    >
                      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                        active
                          ? "bg-primary text-primary-foreground"
                          : completed
                            ? "bg-emerald-600 text-white"
                            : "bg-muted text-muted-foreground group-hover:text-foreground"
                      }`}>
                        {completed ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                      </span>
                      <span className="min-w-0 pt-0.5">
                        <span className="block text-xs font-black uppercase tracking-wide text-muted-foreground">
                          Step {index + 1}
                        </span>
                        <span className="mt-0.5 block text-sm font-bold">{step.shortTitle}</span>
                        <span className="mt-1 block text-[11px] leading-4 text-muted-foreground">
                          {step.description}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>

              <div className="mt-auto rounded-2xl border bg-background/80 p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                  Registration summary
                </p>
                <div className="mt-3 space-y-2 text-xs">
                  <SummaryLine label="Borrower" value={[clientForm.first_name, clientForm.last_name].filter(Boolean).join(" ") || "Not entered"} />
                  <SummaryLine label="Identity" value={clientForm.national_id || clientForm.passport_number || "Not entered"} />
                  <SummaryLine label="Income" value={clientForm.monthly_income !== null ? formatMoney(clientForm.monthly_income) : "Not supplied"} />
                  <SummaryLine label="Existing exposure" value={formatMoney(combinedExistingExposure)} />
                </div>
              </div>
            </aside>

            <div className="flex min-h-0 min-w-0 flex-col">
              <div className="shrink-0 border-b bg-muted/10 px-4 py-3 lg:hidden">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
                    <ActiveClientStepIcon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-black uppercase tracking-wider text-muted-foreground">
                      Step {clientStep + 1} of {CLIENT_STEPS.length}
                    </p>
                    <p className="truncate font-black">{activeClientStep.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{activeClientStep.description}</p>
                  </div>
                </div>
              </div>

              <ScrollArea className="min-h-0 flex-1">
                <div className="space-y-5 p-4 sm:p-6 lg:p-7">
                  {clientStepErrors.length > 0 && (
                    <Alert variant="destructive">
                      <TriangleAlert className="h-4 w-4" />
                      <AlertTitle>Complete the required information</AlertTitle>
                      <AlertDescription>
                        <ul className="mt-2 list-disc space-y-1 pl-5">
                          {clientStepErrors.map((error) => <li key={error}>{error}</li>)}
                        </ul>
                      </AlertDescription>
                    </Alert>
                  )}

                  {clientStep === 0 && (
                    <FormSection
                      icon={ContactRound}
                      title="Personal and contact details"
                      description="Capture the borrower’s legal name, contact channels and secure account access."
                    >
                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        <Field label="First name" required>
                          <Input className="h-11" required autoFocus autoComplete="given-name" value={clientForm.first_name} onChange={(event) => updateClient("first_name", event.target.value)} />
                        </Field>
                        <Field label="Middle name">
                          <Input className="h-11" autoComplete="additional-name" value={clientForm.middle_name ?? ""} onChange={(event) => updateClient("middle_name", event.target.value)} />
                        </Field>
                        <Field label="Last name" required>
                          <Input className="h-11" required autoComplete="family-name" value={clientForm.last_name} onChange={(event) => updateClient("last_name", event.target.value)} />
                        </Field>
                        <Field label="Phone" required description="Use a number the borrower can access for authentication and notices.">
                          <Input className="h-11" required inputMode="tel" autoComplete="tel" value={clientForm.phone} onChange={(event) => updateClient("phone", event.target.value)} />
                        </Field>
                        <Field label="Email" description="Optional, but recommended for statements and account recovery.">
                          <Input className="h-11" type="email" autoComplete="email" value={clientForm.email ?? ""} onChange={(event) => updateClient("email", event.target.value)} />
                        </Field>
                        <Field
                          label={existingBorrowerFound ? "Existing login account" : "Temporary password"}
                          required={!existingBorrowerFound}
                          description={existingBorrowerFound ? "The existing LoanHub login will be linked; no replacement password is created." : "At least 10 characters. The borrower should change it after signing in."}
                        >
                          <div className="relative">
                            <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <Input className="h-11 pl-9" required={!existingBorrowerFound} disabled={existingBorrowerFound} type="password" minLength={10} autoComplete="new-password" value={clientForm.temporary_password ?? ""} placeholder={existingBorrowerFound ? "Existing account will be linked" : "At least 10 characters"} onChange={(event) => updateClient("temporary_password", event.target.value)} />
                          </div>
                        </Field>
                        <Field label="Date of birth" required>
                          <Input className="h-11" required type="date" value={clientForm.date_of_birth} onChange={(event) => updateClient("date_of_birth", event.target.value)} />
                        </Field>
                        <Field label="Gender" required>
                          <Select value={clientForm.gender} onValueChange={(value) => updateClient("gender", value as AssistedCompanyClientCreate["gender"])}>
                            <SelectTrigger className="h-11 w-full"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="male">Male</SelectItem>
                              <SelectItem value="female">Female</SelectItem>
                              <SelectItem value="other">Other</SelectItem>
                            </SelectContent>
                          </Select>
                        </Field>
                        <Field label="Marital status">
                          <Select value={clientForm.marital_status ?? "none"} onValueChange={(value) => updateClient("marital_status", value === "none" ? null : value as AssistedCompanyClientCreate["marital_status"])}>
                            <SelectTrigger className="h-11 w-full"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">Not supplied</SelectItem>
                              <SelectItem value="single">Single</SelectItem>
                              <SelectItem value="married">Married</SelectItem>
                              <SelectItem value="divorced">Divorced</SelectItem>
                              <SelectItem value="widowed">Widowed</SelectItem>
                            </SelectContent>
                          </Select>
                        </Field>
                      </div>
                    </FormSection>
                  )}

                  {clientStep === 1 && (
                    <FormSection
                      icon={IdCard}
                      title="Identity and residence"
                      description="LoanHub verifies the identity and automatically checks current borrower and loan records."
                    >
                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        <Field label="National ID" description="The automatic loan check starts after 8 characters.">
                          <div className="relative">
                            <Input className="h-11 pr-10" autoFocus value={clientForm.national_id ?? ""} autoComplete="off" aria-describedby="national-id-loan-check" onChange={(event) => updateClient("national_id", event.target.value)} />
                            {existingLoanCheckStatus === "checking" ? <LoaderCircle className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-primary" /> : existingLoanCheckStatus === "ready" ? <CircleCheckBig className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-emerald-600" /> : null}
                          </div>
                        </Field>
                        <Field label="Passport number" description="Use this when the borrower has no national ID.">
                          <Input className="h-11" value={clientForm.passport_number ?? ""} onChange={(event) => updateClient("passport_number", event.target.value)} />
                        </Field>
                        <Field label="Branch">
                          <Select value={clientForm.branch_id ?? "none"} onValueChange={(value) => updateClient("branch_id", value === "none" ? null : value)}>
                            <SelectTrigger className="h-11 w-full"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">Use active staff branch</SelectItem>
                              {branches.map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </Field>
                        <Field label="District" required>
                          <Input className="h-11" required value={clientForm.district} onChange={(event) => updateClient("district", event.target.value)} />
                        </Field>
                        <Field label="Town or village">
                          <Input className="h-11" value={clientForm.town_or_village ?? ""} onChange={(event) => updateClient("town_or_village", event.target.value)} />
                        </Field>
                        <Field label="Physical address">
                          <Input className="h-11" value={clientForm.physical_address ?? ""} onChange={(event) => updateClient("physical_address", event.target.value)} />
                        </Field>
                      </div>

                      <ExistingLoanCheckPanel
                        id="national-id-loan-check"
                        status={existingLoanCheckStatus}
                        result={existingLoanCheck}
                        error={existingLoanCheckError}
                        onRetry={() => setExistingLoanCheckNonce((value) => value + 1)}
                      />
                    </FormSection>
                  )}

                  {clientStep === 2 && (
                    <FormSection
                      icon={BriefcaseBusiness}
                      title="Employment and affordability"
                      description="Record the borrower’s current work, income and declared or detected loan exposure."
                    >
                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        <Field label="Employment status" required>
                          <Select value={clientForm.employment_status} onValueChange={(value) => updateClient("employment_status", value as AssistedCompanyClientCreate["employment_status"])}>
                            <SelectTrigger className="h-11 w-full"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {["employed", "self_employed", "unemployed", "student", "pensioner"].map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </Field>
                        <div className="md:col-span-2">
                          <EmployerGroupRegistrationField
                            employerGroupId={clientForm.employer_group_id}
                            employerName={clientForm.employer_name}
                            newEmployerGroup={clientForm.new_employer_group}
                            required={clientForm.employment_status === "employed"}
                            onChange={(selection) => {
                              setClientStepErrors([]);
                              setClientForm((current) => ({ ...current, ...selection }));
                            }}
                          />
                        </div>
                        <Field label="Job title">
                          <Input className="h-11" value={clientForm.job_title ?? ""} onChange={(event) => updateClient("job_title", event.target.value)} />
                        </Field>
                        <Field label="Monthly income" description="Gross monthly income declared by the borrower.">
                          <Input className="h-11" type="number" min={0} step="0.01" inputMode="decimal" value={clientForm.monthly_income ?? ""} onChange={(event) => updateClient("monthly_income", event.target.value ? Number(event.target.value) : null)} />
                        </Field>
                        <Field label="Income / pay day" description="Day of the month the borrower normally receives income, for example 20 for the 20th.">
                          <Input className="h-11" type="number" min={1} max={31} inputMode="numeric" value={clientForm.income_day ?? ""} onChange={(event) => updateClient("income_day", event.target.value ? Number(event.target.value) : null)} placeholder="1–31" />
                        </Field>
                      </div>

                      <ExternalDebtRegistrationFields
                        debts={clientForm.external_debts}
                        onChange={updateExternalDebts}
                        disabled={existingLoanFieldsLocked}
                      />

                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <ReviewMetric label="Open LoanHub loans" value={String(existingLoanCheck?.active_loan_count ?? 0)} />
                        <ReviewMetric label="LoanHub outstanding" value={formatMoney(loanHubOutstandingTotal)} />
                        <ReviewMetric label="External monthly commitment" value={formatMoney(externalDebtMonthlyCommitment)} />
                        <ReviewMetric label="Total existing exposure" value={formatMoney(combinedExistingExposure)} />
                      </div>
                    </FormSection>
                  )}

                  {clientStep === 3 && (
                    <div className="space-y-5">
                      <FormSection
                        icon={ClipboardCheck}
                        title="Review borrower information"
                        description="Confirm the captured details before creating or linking the borrower account."
                      >
                        <div className="grid gap-4 md:grid-cols-2">
                          <ReviewCard icon={UserRound} title="Borrower">
                            <ReviewItem label="Full name" value={[clientForm.first_name, clientForm.middle_name, clientForm.last_name].filter(Boolean).join(" ") || "Not supplied"} />
                            <ReviewItem label="Phone" value={clientForm.phone || "Not supplied"} />
                            <ReviewItem label="Email" value={clientForm.email || "Not supplied"} />
                            <ReviewItem label="Date of birth" value={clientForm.date_of_birth ? formatDate(clientForm.date_of_birth) : "Not supplied"} />
                          </ReviewCard>
                          <ReviewCard icon={MapPin} title="Identity and residence">
                            <ReviewItem label="National ID" value={clientForm.national_id || "Not supplied"} />
                            <ReviewItem label="Passport" value={clientForm.passport_number || "Not supplied"} />
                            <ReviewItem label="District" value={clientForm.district || "Not supplied"} />
                            <ReviewItem label="Address" value={[clientForm.town_or_village, clientForm.physical_address].filter(Boolean).join(", ") || "Not supplied"} />
                          </ReviewCard>
                          <ReviewCard icon={BriefcaseBusiness} title="Employment and affordability">
                            <ReviewItem label="Employment" value={titleCase(clientForm.employment_status)} />
                            <ReviewItem label="Employer / work group" value={clientForm.new_employer_group ? `${clientForm.new_employer_group.code} — ${clientForm.new_employer_group.name}` : (clientForm.employer_name || "Not supplied")} />
                            <ReviewItem label="Income / pay day" value={clientForm.income_day ? `Day ${clientForm.income_day} of each month` : "Not supplied"} />
                            <ReviewItem label="Monthly income" value={clientForm.monthly_income !== null ? formatMoney(clientForm.monthly_income) : "Not supplied"} />
                            <ReviewItem label="External loans" value={clientForm.external_debts.length > 0 ? `${clientForm.external_debts.length} tracked · ${formatMoney(externalDebtBalanceTotal)}` : "None recorded"} />
                            <ReviewItem label="Monthly debt commitment" value={formatMoney(externalDebtMonthlyCommitment)} />
                            <ReviewItem label="Total exposure" value={formatMoney(combinedExistingExposure)} />
                          </ReviewCard>
                          <ReviewCard icon={BadgeCheck} title="Account outcome">
                            <ReviewItem label="Registration" value={existingBorrowerFound ? "Link existing LoanHub borrower" : "Create a new borrower account"} />
                            <ReviewItem label="Company status" value={borrowerAlreadyLinked ? "Already linked" : "Ready to continue"} />
                            <ReviewItem label="Branch" value={branches.find((branch) => branch.id === clientForm.branch_id)?.name || "Active staff branch"} />
                            <ReviewItem label="Loan check" value={existingLoanCheckStatus === "ready" ? "Completed" : clientForm.national_id ? titleCase(existingLoanCheckStatus) : "Not applicable"} />
                          </ReviewCard>
                        </div>
                      </FormSection>

                      <FormSection
                        icon={ShieldCheck}
                        title="Borrower declarations and consent"
                        description="Read each declaration to the borrower and record consent before submission."
                      >
                        <div className="grid gap-3 lg:grid-cols-3">
                          <ConsentChoice
                            disabled
                            label="Borrower has existing loans"
                            description="Derived automatically from LoanHub loans and tracked external obligations."
                            checked={combinedExistingExposure > 0}
                            onCheckedChange={() => undefined}
                          />
                          <ConsentChoice
                            label="Consent to credit checks"
                            description="Authorises affordability and permitted credit-information checks."
                            checked={clientForm.consent_to_credit_checks}
                            onCheckedChange={(value) => updateClient("consent_to_credit_checks", value)}
                          />
                          <ConsentChoice
                            label="Consent to share profile"
                            description="Allows this company to use the borrower profile for lending workflows."
                            checked={clientForm.consent_to_share_profile}
                            onCheckedChange={(value) => updateClient("consent_to_share_profile", value)}
                          />
                        </div>
                      </FormSection>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>

          <Separator />
          <div className="flex shrink-0 flex-col gap-3 bg-muted/30 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-7">
            <div className="min-w-0">
              <p className="text-sm font-bold">{activeClientStep.title}</p>
              <p className="text-xs leading-5 text-muted-foreground">
                {clientStep === LAST_CLIENT_STEP
                  ? "Confirm consent and submit the assisted borrower registration."
                  : "Complete the required fields, then continue to the next step."}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => { setClientDialog(false); resetClientDialog(); }} disabled={saving}>
                Cancel
              </Button>
              {clientStep > 0 && (
                <Button type="button" variant="outline" onClick={previousClientStep} disabled={saving}>
                  <ChevronLeft className="h-4 w-4" />
                  Back
                </Button>
              )}
              {clientStep < LAST_CLIENT_STEP ? (
                <Button type="button" onClick={nextClientStep} disabled={saving || borrowerAlreadyLinked || existingLoanCheckStatus === "checking"}>
                  Continue
                  <ChevronRight className="h-4 w-4" />
                </Button>
              ) : (
                <LoadingButton type="submit" loading={saving} loadingText="Opening account…" disabled={borrowerAlreadyLinked || existingLoanCheckStatus === "checking"}>
                  <BadgeCheck className="h-4 w-4" />
                  {existingBorrowerFound ? "Link borrower account" : "Open borrower account"}
                </LoadingButton>
              )}
            </div>
          </div>
        </form>
      </CustomDialog>

      <CustomDialog
        open={feeDialog}
        onOpenChange={(open) => {
          if (settlingFee) return;
          setFeeDialog(open);
          if (!open) setFeeClient(null);
        }}
        title="Settle assisted-opening charge"
        description={feeClient ? `Record how the company paid the opening charge for ${feeClient.full_name}.` : "Record the company payment settlement."}
        contentClassName="sm:max-w-lg"
      >
        <form onSubmit={submitOpeningFeeSettlement} className="space-y-5 p-6 sm:p-8">
          <div className="rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card to-emerald-500/10 p-5">
            <p className="text-xs font-black uppercase tracking-[0.18em] text-muted-foreground">Amount due</p>
            <p className="mt-2 text-3xl font-black">{formatMoney(feeClient?.opening_fee_amount ?? 0, feeClient?.opening_fee_currency ?? "LSL")}</p>
            <p className="mt-2 text-sm text-muted-foreground">Company money out → platform owner money in</p>
          </div>
          <PaymentMethodFields methods={paymentMethods} value={feeEvidence} onChange={setFeeEvidence} />
          <DialogFooter className="mx-0 mb-0"><Button type="button" variant="outline" onClick={() => setFeeDialog(false)} disabled={settlingFee}>Cancel</Button><LoadingButton type="submit" loading={settlingFee} loadingText="Recording payment…"><Banknote className="h-4 w-4" />Confirm payment</LoadingButton></DialogFooter>
        </form>
      </CustomDialog>

      <CustomDialog
        open={loanDialog}
        onOpenChange={(open) => !saving && setLoanDialog(open)}
        title={`Private loan request${selectedClient ? ` — ${selectedClient.full_name}` : ""}`}
        description="This application stays inside the active company and moves directly to the internal application processing queue."
        contentClassName="sm:max-w-3xl"
      >
        <form onSubmit={submitInternalLoan} className="space-y-6 p-6 sm:p-8">
          {products.length === 0 ? (
            <div className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-5">
              <p className="font-black">A loan product is required</p>
              <p className="mt-1 text-sm text-muted-foreground">A company owner or administrator must create an active product before this request can be submitted.</p>
              <Button asChild variant="outline" className="mt-4"><Link href="/company/products"><PackagePlus className="h-4 w-4" />Open loan products</Link></Button>
            </div>
          ) : (
            <>
              <Field label="Loan product"><Select value={loanForm.product_id ?? "none"} onValueChange={(value) => {
                const product = products.find((item) => item.id === value) ?? null;
                setLoanForm((current) => ({
                  ...current,
                  product_id: product?.id ?? null,
                  requested_amount: product
                    ? Math.min(
                        Math.max(current.requested_amount || Number(product.min_amount), Number(product.min_amount)),
                        Number(product.max_amount),
                      )
                    : current.requested_amount,
                  term_count: product ? Math.min(Math.max(current.term_count, product.min_term_months), product.max_term_months) : current.term_count,
                }));
              }}><SelectTrigger><SelectValue placeholder="Select a loan product" /></SelectTrigger><SelectContent>{products.map((product) => <SelectItem key={product.id} value={product.id}>{product.name} · {Number(product.interest_rate_percent)}%</SelectItem>)}</SelectContent></Select></Field>
              {selectedProduct ? <p className="-mt-3 text-xs text-muted-foreground">Allowed amount {formatMoney(selectedProduct.min_amount)}–{formatMoney(selectedProduct.max_amount)} · {selectedProduct.min_term_months}–{selectedProduct.max_term_months} months</p> : null}
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Requested amount"><Input required type="number" min={selectedProduct ? Number(selectedProduct.min_amount) : 1} max={selectedProduct ? Number(selectedProduct.max_amount) : undefined} step="0.01" value={loanForm.requested_amount || ""} onChange={(event) => updateLoan("requested_amount", Number(event.target.value || 0))} /></Field>
                <Field label="Months"><Input required type="number" min={selectedProduct?.min_term_months ?? 1} max={selectedProduct?.max_term_months ?? 120} value={loanForm.term_count} onChange={(event) => updateLoan("term_count", Number(event.target.value || 1))} /></Field>
              </div>
              <InstallmentDueDateFields
                count={Number(loanForm.term_count || 0)}
                value={loanForm.installment_due_dates}
                onChange={(dates) => updateLoan("installment_due_dates", dates)}
              />
              <Field label="Purpose"><Textarea value={loanForm.purpose ?? ""} onChange={(event) => updateLoan("purpose", optional(event.target.value))} placeholder="What the borrower needs the loan for" /></Field>
              <MicroLoanPreview calculation={calculation} calculating={calculating} />
            </>
          )}
          <DialogFooter className="mx-0 mb-0"><Button type="button" variant="outline" onClick={() => setLoanDialog(false)} disabled={saving}>Cancel</Button><LoadingButton type="submit" loading={saving} loadingText="Creating request…" disabled={!selectedProduct || !calculation || calculating}>Create and process request</LoadingButton></DialogFooter>
        </form>
      </CustomDialog>
    </div>
  );
}

function Field({
  label,
  children,
  description,
  required = false,
}: {
  label: string;
  children: ReactNode;
  description?: string;
  required?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="space-y-0.5">
        <Label className="text-sm font-bold">
          {label}{required ? <span className="ml-1 text-destructive">*</span> : null}
        </Label>
        {description ? <p className="text-[11px] leading-4 text-muted-foreground">{description}</p> : null}
      </div>
      {children}
    </div>
  );
}

function FormSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof UserRound;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Card className="overflow-hidden rounded-3xl border-border/70 shadow-none">
      <CardHeader className="border-b bg-muted/20 px-5 py-4 sm:px-6">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription className="mt-1">{description}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 p-5 sm:p-6">{children}</CardContent>
    </Card>
  );
}

function ConsentChoice({
  label,
  description,
  checked,
  disabled = false,
  onCheckedChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (value: boolean) => void;
}) {
  return (
    <label className={`group flex min-h-24 items-start gap-3 rounded-2xl border p-4 transition ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-primary/50 hover:bg-primary/5"} ${checked ? "border-primary/40 bg-primary/5" : "bg-background"}`}>
      <Checkbox className="mt-0.5" checked={checked} disabled={disabled} onCheckedChange={(value) => onCheckedChange(value === true)} />
      <span className="min-w-0">
        <span className="block text-sm font-bold">{label}</span>
        <span className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
      </span>
    </label>
  );
}

function SummaryLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="max-w-[130px] truncate text-right font-semibold" title={value}>{value}</span>
    </div>
  );
}

function ReviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border bg-muted/20 p-4">
      <p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-black">{value}</p>
    </div>
  );
}

function ReviewCard({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof UserRound;
  title: string;
  children: ReactNode;
}) {
  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 shadow-none">
      <CardHeader className="border-b bg-muted/20 px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Icon className="h-4 w-4 text-primary" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4">{children}</CardContent>
    </Card>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words font-semibold">{value}</span>
    </div>
  );
}

function ExistingLoanCheckPanel({
  id,
  status,
  result,
  error,
  onRetry,
}: {
  id: string;
  status: "idle" | "checking" | "ready" | "error";
  result: CompanyClientExistingLoanCheck | null;
  error: string | null;
  onRetry?: () => void;
}) {
  if (status === "idle") {
    return <p id={id} className="text-xs text-muted-foreground">Enter at least 8 national-ID characters to check existing LoanHub loans automatically. External credit-bureau information still requires borrower consent.</p>;
  }

  if (status === "checking") {
    return <div id={id} role="status" className="flex items-center gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-4 text-sm"><LoaderCircle className="h-5 w-5 animate-spin text-primary" /><div><p className="font-bold">Checking existing loans…</p><p className="text-xs text-muted-foreground">Searching LoanHub borrower and outstanding-loan records.</p></div></div>;
  }

  if (status === "error") {
    return (
      <div id={id} role="alert" className="flex flex-col gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm sm:flex-row sm:items-start">
        <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
        <div className="min-w-0 flex-1">
          <p className="font-bold text-destructive">Existing-loan check failed</p>
          <p className="mt-1 text-xs text-muted-foreground">{error}</p>
        </div>
        {onRetry ? (
          <Button type="button" size="sm" variant="outline" onClick={onRetry}>
            <RefreshCcw className="h-3.5 w-3.5" />
            Retry
          </Button>
        ) : null}
      </div>
    );
  }

  if (!result?.borrower_found) {
    return <div id={id} role="status" className="flex items-start gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm"><ShieldCheck className="mt-0.5 h-5 w-5 text-emerald-600" /><div><p className="font-bold">No existing LoanHub borrower record found</p><p className="text-xs text-muted-foreground">The loan fields remain editable so staff can record debts declared from outside LoanHub.</p></div></div>;
  }

  return (
    <div id={id} role="status" className={`rounded-2xl border p-4 ${result.already_company_client ? "border-destructive/30 bg-destructive/5" : result.has_existing_loans ? "border-amber-500/30 bg-amber-500/5" : "border-emerald-500/30 bg-emerald-500/5"}`}>
      <div className="flex items-start gap-3">
        <ShieldCheck className={`mt-0.5 h-5 w-5 ${result.already_company_client ? "text-destructive" : result.has_existing_loans ? "text-amber-600" : "text-emerald-600"}`} />
        <div className="min-w-0 flex-1">
          <p className="font-bold">{result.already_company_client ? "Borrower already belongs to this company" : result.has_existing_loans ? "Existing loan exposure detected" : "Existing borrower found with no outstanding loan"}</p>
          <p className="mt-1 text-xs text-muted-foreground">{result.already_company_client ? "Open the existing client record instead of creating another company account." : "The borrower identity and tracked obligations can be linked after the date of birth and surname are verified."}</p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border bg-background/70 p-3"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Open LoanHub loans</p><p className="mt-1 text-lg font-black">{result.active_loan_count}</p></div>
        <div className="rounded-xl border bg-background/70 p-3"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">LoanHub outstanding</p><p className="mt-1 text-lg font-black">{formatMoney(result.loanhub_outstanding_total)}</p></div>
        <div className="rounded-xl border bg-background/70 p-3"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">External monthly commitment</p><p className="mt-1 text-lg font-black">{formatMoney(result.external_debt_monthly_commitment)}</p></div>
        <div className="rounded-xl border bg-background/70 p-3"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Total existing exposure</p><p className="mt-1 text-lg font-black">{formatMoney(result.existing_loan_total)}</p></div>
      </div>
      {result.external_debts.length > 0 ? (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">Tracked external obligations</p>
          {result.external_debts.map((debt) => (
            <div key={debt.id} className="grid gap-2 rounded-xl border bg-background/70 p-3 text-xs sm:grid-cols-[minmax(0,1.2fr)_repeat(3,minmax(110px,0.7fr))]">
              <div><p className="font-black">{debt.creditor}</p><p className="text-muted-foreground">Since {debt.started_on ? formatDate(debt.started_on) : "not recorded"}</p></div>
              <div><p className="font-black">{formatMoney(debt.current_balance)}</p><p className="text-muted-foreground">balance</p></div>
              <div><p className="font-black">{formatMoney(debt.installment_amount)}</p><p className="text-muted-foreground">{titleCase(debt.installment_frequency)} installment</p></div>
              <div><p className="font-black">{debt.remaining_installments ?? "—"}</p><p className="text-muted-foreground">installments left</p></div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Metric({ icon: Icon, label, value, hint }: { icon: typeof UsersRound; label: string; value: string; hint: string }) {
  return <Card className="rounded-3xl border-border/70 bg-gradient-to-br from-card to-primary/5"><CardContent className="flex items-start gap-4 p-5"><div className="rounded-2xl bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5" /></div><div><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-black">{value}</p><p className="mt-1 text-xs text-muted-foreground">{hint}</p></div></CardContent></Card>;
}
