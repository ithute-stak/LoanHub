"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  BriefcaseBusiness,
  Calculator,
  CheckCircle2,
  CircleAlert,
  FileCheck2,
  FileText,
  Landmark,
  Plus,
  ReceiptText,
  Save,
  ShieldCheck,
  Trash2,
  Upload,
  WalletCards,
} from "lucide-react";

import { listCompanyClients } from "@/api/companyClients";
import { listLoanProducts } from "@/api/loanProducts";
import { uploadManagedFile } from "@/api/files";
import { calculateLoan } from "@/api/loans";
import { originationApi } from "@/api/origination";
import { BankAccountsStep } from "@/components/clients/bank-accounts-step";
import { MicroLoanPreview } from "@/components/loans/micro-loan-preview";
import { InstallmentDueDateFields, installmentDueDatesComplete, resizeInstallmentDueDates } from "@/components/loans/installment-due-date-fields";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatMoney, titleCase } from "@/lib/format";
import { interestMethodLabel, interestMethodOption } from "@/lib/interest-methods";
import type { CompanyClient } from "@/types/companyClient";
import type { MicroLoanCalculation } from "@/types/loan";
import type { LoanProduct } from "@/types/loanProduct";
import type {
  AffordabilityAssessment,
  BankAccountInput,
  DebtObligationInput,
  EmploymentProfileInput,
  ExpenseInput,
  FinancialProfile,
  FinancialProfileUpdate,
  IncomeSourceInput,
  KYCProfileInput,
  OriginationApplication,
  TopUpEligibility,
} from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const steps = [
  { label: "Application", icon: ReceiptText },
  { label: "KYC", icon: ShieldCheck },
  { label: "Employment", icon: BriefcaseBusiness },
  { label: "Expenses & debt", icon: WalletCards },
  { label: "Banking", icon: Landmark },
  { label: "Affordability", icon: Calculator },
  { label: "Review & submit", icon: FileCheck2 },
] as const;

const emptyKyc: KYCProfileInput = {
  status: "not_started",
  identity_verified: false,
  address_verified: false,
  phone_verified: false,
  sanctions_hit: false,
  politically_exposed: false,
  adverse_media_hit: false,
  fraud_flag: false,
  source_of_funds: null,
  residence_status: null,
  years_at_address: null,
  dependants: 0,
  next_of_kin: { name: "", phone: "", relationship: "" },
  emergency_contact: { name: "", phone: "", relationship: "" },
  document_file_ids: [],
  verification_notes: null,
  expires_at: null,
};

const emptyEmployment: EmploymentProfileInput = {
  employment_status: "employed",
  employer_name: null,
  employer_registration: null,
  employer_phone: null,
  employer_address: null,
  employee_number: null,
  job_title: null,
  employment_start_date: null,
  contract_type: null,
  contract_expiry_date: null,
  salary_frequency: "monthly",
  gross_salary: 0,
  net_salary: 0,
  verified_net_income: 0,
  salary_day: null,
  verification_method: null,
  verification_status: "unverified",
  payslip_count: 0,
  bank_statement_months: 0,
  notes: null,
};

const emptyIncome = (): IncomeSourceInput => ({
  source_type: "other_income",
  description: null,
  declared_amount: 0,
  verified_amount: 0,
  frequency: "monthly",
  verification_method: null,
  is_verified: false,
});

const emptyExpense = (): ExpenseInput => ({
  category: "food",
  description: null,
  monthly_amount: 0,
  is_verified: false,
  verification_notes: null,
});

function normalizedDebtMonthly(amount: number, frequency: DebtObligationInput["installment_frequency"]) {
  const factor = frequency === "weekly" ? 52 / 12 : frequency === "fortnightly" ? 26 / 12 : frequency === "quarterly" ? 1 / 3 : 1;
  return Number((Number(amount || 0) * factor).toFixed(2));
}

const emptyDebt = (): DebtObligationInput => ({
  id: null,
  creditor: "",
  account_reference: null,
  debt_type: "microloan",
  started_on: null,
  original_amount: 0,
  current_balance: 0,
  installment_amount: 0,
  installment_frequency: "monthly",
  monthly_installment: 0,
  total_installments: null,
  installments_paid: 0,
  remaining_installments: null,
  next_due_date: null,
  settlement_amount: null,
  remaining_term_months: null,
  status: "active",
  source: "declared",
  is_verified: false,
  notes: null,
});


export default function NewOriginationPage() {
  return <Suspense fallback={<PageLoader rows={10} />}><OriginationWizard /></Suspense>;
}

function OriginationWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedBorrowerId = searchParams.get("borrower");
  const requestedApplicationId = searchParams.get("application");
  const requestedType = searchParams.get("type");
  const requestedLoanId = searchParams.get("loan");

  const [clients, setClients] = useState<CompanyClient[]>([]);
  const [products, setProducts] = useState<LoanProduct[]>([]);
  const [application, setApplication] = useState<OriginationApplication | null>(null);
  const [profile, setProfile] = useState<FinancialProfile | null>(null);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [uploadingKyc, setUploadingKyc] = useState(false);
  const [calculation, setCalculation] = useState<MicroLoanCalculation | null>(null);
  const [assessment, setAssessment] = useState<AffordabilityAssessment | null>(null);

  const [borrowerId, setBorrowerId] = useState(requestedBorrowerId ?? "");
  const [productId, setProductId] = useState("");
  const [applicationType, setApplicationType] = useState<"new_loan" | "top_up">(requestedType === "top_up" ? "top_up" : "new_loan");
  const [topUpEligibility, setTopUpEligibility] = useState<TopUpEligibility | null>(null);
  const [topUpCashRequested, setTopUpCashRequested] = useState(0);
  const [topUpExceptionReason, setTopUpExceptionReason] = useState("");
  const [requestedAmount, setRequestedAmount] = useState(0);
  const [termCount, setTermCount] = useState(3);
  const [purpose, setPurpose] = useState("");
  const [installmentDueDates, setInstallmentDueDates] = useState<string[]>(() => resizeInstallmentDueDates([], 3));
  const [rate, setRate] = useState(20);
  const [processingFee, setProcessingFee] = useState(0);

  const [kyc, setKyc] = useState<KYCProfileInput>(emptyKyc);
  const [employment, setEmployment] = useState<EmploymentProfileInput>(emptyEmployment);
  const [incomeSources, setIncomeSources] = useState<IncomeSourceInput[]>([]);
  const [expenses, setExpenses] = useState<ExpenseInput[]>([emptyExpense()]);
  const [debts, setDebts] = useState<DebtObligationInput[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccountInput[]>([]);

  const selectedClient = useMemo(() => clients.find((item) => item.borrower_id === borrowerId) ?? null, [borrowerId, clients]);
  const selectedProduct = useMemo(() => products.find((item) => item.id === productId) ?? null, [productId, products]);
  const topUpSettlement = Number(topUpEligibility?.loan?.balance ?? 0);
  const topUpTotal = topUpSettlement + Number(topUpCashRequested || 0);

  const applyProfile = useCallback((row: FinancialProfile) => {
    setProfile(row);
    setKyc(row.kyc ? {
      status: row.kyc.status,
      identity_verified: row.kyc.identity_verified,
      address_verified: row.kyc.address_verified,
      phone_verified: row.kyc.phone_verified,
      sanctions_hit: row.kyc.sanctions_hit,
      politically_exposed: row.kyc.politically_exposed,
      adverse_media_hit: row.kyc.adverse_media_hit,
      fraud_flag: row.kyc.fraud_flag,
      source_of_funds: row.kyc.source_of_funds,
      residence_status: row.kyc.residence_status,
      years_at_address: row.kyc.years_at_address,
      dependants: row.kyc.dependants,
      next_of_kin: row.kyc.next_of_kin,
      emergency_contact: row.kyc.emergency_contact,
      document_file_ids: row.kyc.document_file_ids,
      verification_notes: row.kyc.verification_notes,
      expires_at: row.kyc.expires_at,
    } : emptyKyc);
    setEmployment(row.employment ? {
      employment_status: row.employment.employment_status,
      employer_name: row.employment.employer_name,
      employer_registration: row.employment.employer_registration,
      employer_phone: row.employment.employer_phone,
      employer_address: row.employment.employer_address,
      employee_number: row.employment.employee_number,
      job_title: row.employment.job_title,
      employment_start_date: row.employment.employment_start_date,
      contract_type: row.employment.contract_type,
      contract_expiry_date: row.employment.contract_expiry_date,
      salary_frequency: row.employment.salary_frequency,
      gross_salary: Number(row.employment.gross_salary),
      net_salary: Number(row.employment.net_salary),
      verified_net_income: Number(row.employment.verified_net_income),
      salary_day: row.employment.salary_day,
      verification_method: row.employment.verification_method,
      verification_status: row.employment.verification_status,
      payslip_count: Number(row.employment.payslip_count),
      bank_statement_months: Number(row.employment.bank_statement_months),
      notes: row.employment.notes,
    } : emptyEmployment);
    setIncomeSources(row.income_sources.map(({ id: _id, ...item }) => ({ ...item, declared_amount: Number(item.declared_amount), verified_amount: Number(item.verified_amount) })));
    setExpenses(row.expenses.length ? row.expenses.map(({ id: _id, ...item }) => ({ ...item, monthly_amount: Number(item.monthly_amount) })) : [emptyExpense()]);
    setDebts(row.debts.map((item) => ({
      ...item,
      id: item.id,
      original_amount: Number(item.original_amount),
      current_balance: Number(item.current_balance),
      installment_amount: Number(item.installment_amount ?? item.monthly_installment ?? 0),
      installment_frequency: item.installment_frequency ?? "monthly",
      monthly_installment: Number(item.monthly_installment),
      total_installments: item.total_installments === null ? null : Number(item.total_installments),
      installments_paid: Number(item.installments_paid || 0),
      remaining_installments: item.remaining_installments === null ? null : Number(item.remaining_installments),
      settlement_amount: item.settlement_amount === null ? null : Number(item.settlement_amount),
      notes: item.notes ?? null,
    })));
    const sharedBanks = row.bank_accounts ?? (row.bank_account ? [row.bank_account] : []);
    setBankAccounts(sharedBanks.map((item) => ({
      id: item.id,
      account_holder: item.account_holder,
      bank_name: item.bank_name,
      branch_name: item.branch_name,
      branch_code: item.branch_code,
      account_type: item.account_type,
      currency: item.currency,
      account_number: null,
      salary_account: item.salary_account,
      verification_status: item.verification_status as BankAccountInput["verification_status"],
      verification_reference: item.verification_reference,
      tokenized_card_provider: null,
      tokenized_card_reference: null,
      masked_card_number: item.masked_card_number,
      card_brand: item.card_brand,
      card_expiry_month: item.card_expiry_month,
      card_expiry_year: item.card_expiry_year,
    })));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [clientRows, productRows] = await Promise.all([listCompanyClients(), listLoanProducts()]);
      setClients(clientRows.filter((item) => item.status === "active"));
      setProducts(productRows.filter((item) => item.is_active));

      if (requestedApplicationId) {
        const workspace = await originationApi.getWorkspace(requestedApplicationId);
        setApplication(workspace.application);
        setBorrowerId(workspace.application.borrower_id);
        setProductId(workspace.application.product_id ?? "");
        setApplicationType(workspace.application.application_type ?? "new_loan");
        setTopUpCashRequested(Number(workspace.application.top_up_cash_requested ?? 0));
        setTopUpExceptionReason(workspace.application.top_up_exception_reason ?? "");
        setRequestedAmount(Number(workspace.application.requested_amount));
        if (workspace.application.application_type === "top_up") {
          const eligibility = await originationApi.topUpEligibility(workspace.application.borrower_id, workspace.application.parent_loan_id);
          setTopUpEligibility(eligibility);
        }
        setTermCount(workspace.application.term_count);
        setPurpose(workspace.application.purpose ?? "");
        setInstallmentDueDates(
          resizeInstallmentDueDates(workspace.application.installment_due_dates ?? [], workspace.application.term_count),
        );
        setRate(Number(workspace.application.interest_rate ?? 20));
        setAssessment(workspace.assessments[0] ?? null);
        setStep(Math.min(Math.max((workspace.application.application_step ?? 1) - 1, 0), steps.length - 1));
        applyProfile(workspace.profile);
      } else if (requestedBorrowerId) {
        const [profileRow, eligibility] = await Promise.all([
          originationApi.getFinancialProfile(requestedBorrowerId),
          originationApi.topUpEligibility(requestedBorrowerId, requestedLoanId).catch(() => null),
        ]);
        applyProfile(profileRow);
        setTopUpEligibility(eligibility);
        if (requestedType === "top_up") {
          setApplicationType("top_up");
          setRequestedAmount(Number(eligibility?.loan?.balance ?? 0));
        }
      }
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The origination workspace could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [applyProfile, requestedApplicationId, requestedBorrowerId, requestedLoanId, requestedType]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (applicationType === "top_up") setRequestedAmount(topUpTotal);
  }, [applicationType, topUpTotal]);

  useEffect(() => {
    setInstallmentDueDates((current) => resizeInstallmentDueDates(current, termCount));
  }, [termCount]);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!selectedProduct || requestedAmount <= 0 || termCount <= 0 || !installmentDueDatesComplete(installmentDueDates, termCount)) {
        setCalculation(null);
        return;
      }
      setCalculating(true);
      void calculateLoan({ principal: requestedAmount, rate_percent: rate, months: termCount, processing_fee: processingFee, interest_method: selectedProduct.interest_method, due_dates: installmentDueDates })
        .then((row) => { if (!cancelled) setCalculation(row); })
        .catch((error: unknown) => { if (!cancelled) toast.error(getErrorMessage(error, "The loan calculation failed.")); })
        .finally(() => { if (!cancelled) setCalculating(false); });
    }, 300);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [installmentDueDates, processingFee, rate, requestedAmount, selectedProduct, termCount]);

  async function uploadKycDocuments(files: File[]) {
    if (!files.length || !borrowerId) return;
    setUploadingKyc(true);
    try {
      const uploadedIds: string[] = [];
      for (const file of files) {
        const uploaded = await uploadManagedFile({
          file,
          category: "borrower_identity",
          visibility: "private",
          description: `KYC evidence for borrower ${borrowerId}`,
          isConfidential: true,
          linkedEntityType: "borrower_evaluation",
          linkedEntityId: borrowerId,
        });
        uploadedIds.push(uploaded.id);
      }
      setKyc((current) => ({
        ...current,
        document_file_ids: Array.from(new Set([...current.document_file_ids, ...uploadedIds])),
        status: current.status === "not_started" ? "documents_pending" : current.status,
      }));
      toast.success(files.length === 1 ? "KYC document uploaded securely" : `${files.length} KYC documents uploaded securely`);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The KYC documents could not be uploaded."));
    } finally {
      setUploadingKyc(false);
    }
  }

  function chooseProduct(value: string) {
    const product = products.find((item) => item.id === value);
    setProductId(value);
    if (product) {
      setRate(Number(product.interest_rate_percent));
      setProcessingFee(Number(product.processing_fee));
      setRequestedAmount((current) => {
        const proposed = applicationType === "top_up" ? topUpTotal : current || Number(product.min_amount);
        return Math.min(Math.max(proposed, Number(product.min_amount)), Number(product.max_amount));
      });
      setTermCount((current) => Math.min(Math.max(current, product.min_term_months), product.max_term_months));
    }
  }

  async function ensureApplication(): Promise<OriginationApplication> {
    if (!borrowerId) throw new Error("Select a borrower first");
    if (!productId) throw new Error("Select a loan product");
    if (applicationType === "top_up") {
      if (!topUpEligibility?.loan) throw new Error("No active loan is available for a top-up");
      if (topUpCashRequested <= 0) throw new Error("Enter the additional cash requested for the top-up");
      if (!topUpEligibility.eligible && topUpEligibility.requires_owner_exception && topUpExceptionReason.trim().length < 10) {
        throw new Error("Explain why the company owner should approve this top-up exception");
      }
    }
    if (application) {
      const updated = await originationApi.updateApplication(application.id, {
        product_id: productId,
        requested_amount: applicationType === "top_up" ? topUpTotal : requestedAmount,
        top_up_cash_requested: applicationType === "top_up" ? topUpCashRequested : undefined,
        top_up_exception_reason: applicationType === "top_up" ? topUpExceptionReason.trim() || undefined : undefined,
        term_count: termCount,
        purpose: purpose.trim() || null,
        installment_due_dates: installmentDueDates,
        application_step: Math.max(application.application_step, step + 1),
      });
      setApplication(updated);
      return updated;
    }
    const created = await originationApi.createApplication({
      borrower_id: borrowerId,
      product_id: productId,
      application_type: applicationType,
      parent_loan_id: applicationType === "top_up" ? topUpEligibility?.loan?.id ?? null : null,
      requested_amount: applicationType === "top_up" ? topUpTotal : requestedAmount,
      top_up_cash_requested: applicationType === "top_up" ? topUpCashRequested : null,
      top_up_exception_reason: applicationType === "top_up" ? topUpExceptionReason.trim() || null : null,
      term_count: termCount,
      purpose: purpose.trim() || null,
      installment_due_dates: installmentDueDates,
    });
    setApplication(created);
    window.history.replaceState(null, "", `/company/origination/new?application=${created.id}`);
    return created;
  }

  function profilePayload(): FinancialProfileUpdate {
    return { kyc, employment, income_sources: incomeSources, expenses, debts, bank_accounts: bankAccounts };
  }

  async function saveCurrent() {
    setWorking(true);
    try {
      if (step === 0) {
        await ensureApplication();
      } else {
        const current = await ensureApplication();
        const saved = await originationApi.saveFinancialProfile(current.borrower_id, profilePayload());
        applyProfile(saved);
        await originationApi.updateApplication(current.id, { application_step: step + 1 });
      }
      toast.success("Progress saved");
    } finally {
      setWorking(false);
    }
  }

  async function goNext() {
    setWorking(true);
    try {
      if (step === 0) {
        await ensureApplication();
      } else if (step <= 4) {
        const current = await ensureApplication();
        const saved = await originationApi.saveFinancialProfile(current.borrower_id, profilePayload());
        applyProfile(saved);
        await originationApi.updateApplication(current.id, { application_step: step + 2 });
      } else if (step === 5) {
        const current = await ensureApplication();
        const saved = await originationApi.saveFinancialProfile(current.borrower_id, profilePayload());
        applyProfile(saved);
        const result = await originationApi.assess(current.id, {
          proposed_principal: applicationType === "top_up" ? topUpTotal : requestedAmount,
          proposed_rate_percent: rate,
          proposed_months: termCount,
          processing_fee: processingFee,
          interest_method: selectedProduct?.interest_method ?? "micro_loan",
        });
        setAssessment(result);
        setApplication((row) => row ? { ...row, affordability_assessment_id: result.id, affordability_decision: result.decision } : row);
        toast.success("Affordability calculated", { description: titleCase(result.decision) });
      }
      setStep((current) => Math.min(current + 1, steps.length - 1));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "This step could not be completed."));
    } finally {
      setWorking(false);
    }
  }

  async function submitApplication() {
    if (!application) return;
    setWorking(true);
    try {
      const submitted = await originationApi.submit(application.id);
      setApplication(submitted);
      toast.success("Application submitted for manager review", { description: submitted.application_reference });
      router.push(`/company/marketplace?workspace=applications&application=${encodeURIComponent(submitted.id)}`);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The application could not be submitted."));
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <PageLoader rows={10} />;

  const progress = ((step + 1) / steps.length) * 100;
  const totalExpenses = expenses.reduce((sum, item) => sum + Number(item.monthly_amount || 0), 0);
  const totalDebts = debts.reduce((sum, item) => sum + Number(item.monthly_installment || 0), 0);

  return (
    <main className="loanhub-page space-y-5">
      <section className="loanhub-hero p-6 sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Credit origination step form</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight">{application?.application_reference ?? "New credit application"}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{profile?.identity.full_name ?? selectedClient?.full_name ?? "Select an existing company client"} · Step {step + 1} of {steps.length}</p>
          </div>
          <div className="flex flex-wrap gap-2"><Button variant="outline" asChild><Link href="/company/origination"><ArrowLeft className="h-4 w-4" />Origination queue</Link></Button><LoadingButton variant="outline" loading={working} loadingText="Saving…" onClick={() => void saveCurrent()}><Save className="h-4 w-4" />Save progress</LoadingButton></div>
        </div>
        <Progress value={progress} className="mt-6 h-2" />
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
          {steps.map((item, index) => { const Icon = item.icon; return <button key={item.label} type="button" onClick={() => setStep(index)} className={`rounded-2xl border p-3 text-left transition ${index === step ? "border-primary bg-primary text-primary-foreground" : index < step ? "border-emerald-500/30 bg-emerald-500/10" : "bg-card"}`}><Icon className="h-4 w-4" /><span className="mt-2 block text-xs font-black">{item.label}</span></button>; })}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Card className="rounded-3xl border-border/70">
          <CardHeader><CardTitle>{steps[step].label}</CardTitle><CardDescription>{stepDescription(step)}</CardDescription></CardHeader>
          <CardContent className="space-y-6">
            {step === 0 ? (
              <div className="space-y-6">
                <div className="grid gap-3 sm:grid-cols-2">
                  <button type="button" disabled={Boolean(application)} onClick={() => setApplicationType("new_loan")} className={`rounded-3xl border p-5 text-left ${applicationType === "new_loan" ? "border-primary bg-primary/10" : "bg-card"}`}><p className="font-black">New loan</p><p className="mt-1 text-sm text-muted-foreground">Use when the borrower has no active loan with this company.</p></button>
                  <button type="button" disabled={Boolean(application) || !topUpEligibility?.loan} onClick={() => setApplicationType("top_up")} className={`rounded-3xl border p-5 text-left ${applicationType === "top_up" ? "border-primary bg-primary/10" : "bg-card"}`}><p className="font-black">Top-up existing loan</p><p className="mt-1 text-sm text-muted-foreground">Settle the old balance inside the new facility and pay only the extra cash to the borrower.</p></button>
                </div>
                {applicationType === "top_up" ? <TopUpPanel eligibility={topUpEligibility} cashRequested={topUpCashRequested} onCashRequested={setTopUpCashRequested} exceptionReason={topUpExceptionReason} onExceptionReason={setTopUpExceptionReason} /> : null}
                <div className="grid gap-5 sm:grid-cols-2">
                  <Field label="Borrower"><Select value={borrowerId} onValueChange={(value) => { setBorrowerId(value); setApplicationType("new_loan"); setTopUpCashRequested(0); setTopUpExceptionReason(""); void Promise.all([originationApi.getFinancialProfile(value), originationApi.topUpEligibility(value).catch(() => null)]).then(([profileRow, eligibility]) => { applyProfile(profileRow); setTopUpEligibility(eligibility); }); }} disabled={Boolean(application)}><SelectTrigger><SelectValue placeholder="Select company client" /></SelectTrigger><SelectContent>{clients.map((client) => <SelectItem key={client.id} value={client.borrower_id}>{client.full_name} · {client.account_reference}</SelectItem>)}</SelectContent></Select></Field>
                  <Field label="Loan product"><Select value={productId} onValueChange={chooseProduct}><SelectTrigger><SelectValue placeholder="Select product" /></SelectTrigger><SelectContent>{products.map((product) => <SelectItem key={product.id} value={product.id}>{product.name} · {interestMethodLabel(product.interest_method)} · {Number(product.interest_rate_percent)}%</SelectItem>)}</SelectContent></Select>{selectedProduct ? <p className="text-xs text-muted-foreground">Allowed {formatMoney(selectedProduct.min_amount)}–{formatMoney(selectedProduct.max_amount)} · {selectedProduct.min_term_months}–{selectedProduct.max_term_months} months</p> : null}</Field>
                  {applicationType === "new_loan" ? <NumberField label="Requested amount" value={requestedAmount} min={selectedProduct ? Number(selectedProduct.min_amount) : 1} max={selectedProduct ? Number(selectedProduct.max_amount) : undefined} onChange={setRequestedAmount} /> : <Field label="Total replacement facility"><Input value={formatMoney(topUpTotal)} disabled /><p className="text-xs text-muted-foreground">Old balance {formatMoney(topUpSettlement)} + extra cash {formatMoney(topUpCashRequested)}</p></Field>}
                  <NumberField label="Term in months" value={termCount} min={selectedProduct?.min_term_months ?? 1} max={selectedProduct?.max_term_months ?? 120} step="1" onChange={setTermCount} />
                  <NumberField label={interestMethodOption(selectedProduct?.interest_method ?? "micro_loan").rateLabel} value={rate} min={0} max={100} step="0.001" onChange={setRate} />
                  <NumberField label="Processing fee" value={processingFee} min={0} onChange={setProcessingFee} />
                  <InstallmentDueDateFields
                    count={termCount}
                    value={installmentDueDates}
                    onChange={setInstallmentDueDates}
                  />
                </div>
                <Field label="Loan purpose"><Textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} placeholder="Describe exactly what the borrower needs the loan for" /></Field>
                <MicroLoanPreview calculation={calculation} calculating={calculating} />
              </div>
            ) : null}

            {step === 1 ? <KycStep value={kyc} onChange={setKyc} uploading={uploadingKyc} onUpload={uploadKycDocuments} /> : null}
            {step === 2 ? <EmploymentStep employment={employment} onEmploymentChange={setEmployment} incomes={incomeSources} onIncomesChange={setIncomeSources} /> : null}
            {step === 3 ? <ExpensesStep expenses={expenses} onExpensesChange={setExpenses} debts={debts} onDebtsChange={setDebts} /> : null}
            {step === 4 ? <BankingStep values={bankAccounts} onChange={setBankAccounts} identityName={profile?.identity.full_name ?? selectedClient?.full_name ?? ""} /> : null}
            {step === 5 ? <AffordabilityStep calculation={calculation} assessment={assessment} totalExpenses={totalExpenses} totalDebts={totalDebts} verifiedIncome={employment.verified_net_income + incomeSources.filter((item) => item.is_verified).reduce((sum, item) => sum + item.verified_amount, 0)} /> : null}
            {step === 6 ? <ReviewStep application={application} profile={profile} assessment={assessment} calculation={calculation} product={selectedProduct} totalExpenses={totalExpenses} totalDebts={totalDebts} /> : null}

            <div className="flex flex-wrap justify-between gap-3 border-t pt-5">
              <Button type="button" variant="outline" disabled={step === 0 || working} onClick={() => setStep((current) => Math.max(current - 1, 0))}><ArrowLeft className="h-4 w-4" />Previous</Button>
              {step < steps.length - 1 ? <LoadingButton type="button" loading={working} loadingText="Saving step…" onClick={() => void goNext()}>Save and continue<ArrowRight className="h-4 w-4" /></LoadingButton> : <LoadingButton type="button" loading={working} loadingText="Submitting…" disabled={!assessment || !["eligible", "conditionally_eligible"].includes(assessment.overridden ? assessment.override_decision ?? "" : assessment.decision)} onClick={() => void submitApplication()}><CheckCircle2 className="h-4 w-4" />Submit for manager decision</LoadingButton>}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card className="rounded-3xl border-primary/20 bg-gradient-to-br from-primary/10 via-card to-emerald-500/10"><CardHeader><CardTitle className="flex items-center gap-2"><BadgeCheck className="h-5 w-5 text-primary" />Application health</CardTitle></CardHeader><CardContent className="space-y-3"><Health label="Client selected" ok={Boolean(borrowerId)} />{applicationType === "top_up" ? <Health label="Top-up rule or owner exception" ok={Boolean(topUpEligibility?.eligible || topUpEligibility?.requires_owner_exception)} /> : null}<Health label="Loan terms calculated" ok={Boolean(calculation)} /><Health label="KYC verified" ok={kyc.status === "verified"} /><Health label="Income verified" ok={employment.verification_status === "verified" && employment.verified_net_income > 0} /><Health label="Banking captured" ok={bankAccounts.length > 0} /><Health label="Positive affordability" ok={Boolean(assessment && ["eligible", "conditionally_eligible"].includes(assessment.overridden ? assessment.override_decision ?? "" : assessment.decision))} /></CardContent></Card>
          <Card className="rounded-3xl"><CardHeader><CardTitle>Financial snapshot</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><Line label="Verified income" value={formatMoney(employment.verified_net_income + incomeSources.filter((item) => item.is_verified).reduce((sum, item) => sum + item.verified_amount, 0))} /><Line label="Household expenses" value={formatMoney(totalExpenses)} /><Line label="Debt instalments" value={formatMoney(totalDebts)} /><Line label="Proposed instalment" value={formatMoney(calculation?.monthly_installment ?? 0)} /><Line label="Affordability limit" value={formatMoney(assessment?.maximum_affordable_installment ?? 0)} /></CardContent></Card>
          <Alert><CircleAlert className="h-4 w-4" /><AlertTitle>Payment-card security</AlertTitle><AlertDescription>LoanHub never captures or stores CVV/CVC, PIN or a full card number. Only provider tokens and masked card details are accepted.</AlertDescription></Alert>
        </div>
      </div>
    </main>
  );
}

function TopUpPanel({
  eligibility,
  cashRequested,
  onCashRequested,
  exceptionReason,
  onExceptionReason,
}: {
  eligibility: TopUpEligibility | null;
  cashRequested: number;
  onCashRequested: (value: number) => void;
  exceptionReason: string;
  onExceptionReason: (value: string) => void;
}) {
  if (!eligibility?.loan) {
    return <Alert variant="destructive"><CircleAlert className="h-4 w-4" /><AlertTitle>No active loan available</AlertTitle><AlertDescription>The borrower cannot start a top-up because there is no active company loan to replace.</AlertDescription></Alert>;
  }
  return <div className="space-y-4 rounded-3xl border border-primary/30 bg-gradient-to-br from-primary/10 via-card to-emerald-500/10 p-5">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">Existing loan</p><p className="mt-1 font-mono text-lg font-black">{eligibility.loan.reference}</p><p className="text-sm text-muted-foreground">Current settlement balance {formatMoney(eligibility.loan.balance)}</p></div>
      <Badge variant={eligibility.eligible ? "default" : eligibility.requires_owner_exception ? "secondary" : "destructive"}>{eligibility.eligible ? "Normal rule passed" : eligibility.requires_owner_exception ? "Owner exception required" : "Not eligible"}</Badge>
    </div>
    <div className="grid gap-4 sm:grid-cols-4"><Summary label="Paid" value={`${Number(eligibility.paid_percent).toFixed(1)}%`} /><Summary label="Required" value={`${Number(eligibility.required_paid_percent).toFixed(1)}%`} /><Summary label="Paid instalments" value={String(eligibility.paid_installments)} /><Summary label="Old balance" value={formatMoney(eligibility.loan.balance)} /></div>
    <NumberField label="Additional cash requested" value={cashRequested} min={1} onChange={onCashRequested} />
    {eligibility.requires_owner_exception && !eligibility.eligible ? <Field label="Reason for owner exception"><Textarea required minLength={10} value={exceptionReason} onChange={(event) => onExceptionReason(event.target.value)} placeholder="Explain the exceptional business and affordability reasons for granting the top-up before the normal repayment threshold." /><p className="text-xs text-muted-foreground">The Company Owner must approve this exception before the application can be approved.</p></Field> : null}
    <p className="text-sm text-muted-foreground">{eligibility.reason}</p>
  </div>;
}

function KycStep({
  value,
  onChange,
  uploading,
  onUpload,
}: {
  value: KYCProfileInput;
  onChange: (value: KYCProfileInput) => void;
  uploading: boolean;
  onUpload: (files: File[]) => Promise<void>;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="KYC status">
          <Select value={value.status} onValueChange={(status: KYCProfileInput["status"]) => onChange({ ...value, status })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {["not_started", "documents_pending", "under_review", "verified", "failed", "enhanced_due_diligence", "expired"].map((item) => (
                <SelectItem key={item} value={item}>{titleCase(item)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Source of funds"><Input value={value.source_of_funds ?? ""} onChange={(event) => onChange({ ...value, source_of_funds: event.target.value || null })} /></Field>
        <Field label="Residence status"><Input value={value.residence_status ?? ""} onChange={(event) => onChange({ ...value, residence_status: event.target.value || null })} /></Field>
        <NumberField label="Years at address" value={value.years_at_address ?? 0} min={0} onChange={(years_at_address) => onChange({ ...value, years_at_address })} />
        <NumberField label="Dependants" value={value.dependants} min={0} step="1" onChange={(dependants) => onChange({ ...value, dependants })} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Check label="Identity verified" checked={value.identity_verified} onChange={(identity_verified) => onChange({ ...value, identity_verified })} />
        <Check label="Address verified" checked={value.address_verified} onChange={(address_verified) => onChange({ ...value, address_verified })} />
        <Check label="Phone verified" checked={value.phone_verified} onChange={(phone_verified) => onChange({ ...value, phone_verified })} />
        <Check label="Politically exposed person" checked={value.politically_exposed} onChange={(politically_exposed) => onChange({ ...value, politically_exposed })} />
        <Check label="Sanctions hit" checked={value.sanctions_hit} onChange={(sanctions_hit) => onChange({ ...value, sanctions_hit })} />
        <Check label="Adverse media hit" checked={value.adverse_media_hit} onChange={(adverse_media_hit) => onChange({ ...value, adverse_media_hit })} />
        <Check label="Fraud flag" checked={value.fraud_flag} onChange={(fraud_flag) => onChange({ ...value, fraud_flag })} />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <ContactGroup title="Next of kin" value={value.next_of_kin} onChange={(next_of_kin) => onChange({ ...value, next_of_kin })} />
        <ContactGroup title="Emergency contact" value={value.emergency_contact} onChange={(emergency_contact) => onChange({ ...value, emergency_contact })} />
      </div>

      <div className="rounded-3xl border border-dashed bg-muted/15 p-5">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h3 className="flex items-center gap-2 font-black"><FileText className="h-4 w-4 text-primary" />KYC evidence</h3>
            <p className="mt-1 text-xs text-muted-foreground">Upload identity, proof of address, payslip or other lawful evidence. Files are encrypted by the managed-file service when file encryption is enabled.</p>
          </div>
          <Label htmlFor="kyc-document-upload" className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground hover:bg-primary/90">
            <Upload className="h-4 w-4" />{uploading ? "Uploading…" : "Upload document"}
          </Label>
          <Input
            id="kyc-document-upload"
            type="file"
            multiple
            className="sr-only"
            disabled={uploading}
            accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx"
            onChange={(event) => {
              const files = Array.from(event.target.files ?? []);
              if (files.length) void onUpload(files);
              event.currentTarget.value = "";
            }}
          />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {value.document_file_ids.length === 0 ? (
            <p className="text-sm text-muted-foreground">No KYC evidence attached yet.</p>
          ) : value.document_file_ids.map((fileId, index) => (
            <Badge key={fileId} variant="secondary" className="gap-2">
              Document {index + 1}
              <button type="button" aria-label={`Remove document ${index + 1}`} onClick={() => onChange({ ...value, document_file_ids: value.document_file_ids.filter((item) => item !== fileId) })}>×</button>
            </Badge>
          ))}
        </div>
      </div>

      <Field label="Verification notes">
        <Textarea
          value={value.verification_notes ?? ""}
          onChange={(event) => onChange({ ...value, verification_notes: event.target.value || null })}
          placeholder="Document checks, consent evidence, KYC exceptions and reviewer notes"
        />
      </Field>
    </div>
  );
}

function EmploymentStep({ employment, onEmploymentChange, incomes, onIncomesChange }: { employment: EmploymentProfileInput; onEmploymentChange: (value: EmploymentProfileInput) => void; incomes: IncomeSourceInput[]; onIncomesChange: (value: IncomeSourceInput[]) => void }) {
  return <div className="space-y-6"><div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"><Field label="Employment status"><Select value={employment.employment_status} onValueChange={(employment_status) => onEmploymentChange({ ...employment, employment_status })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["employed", "self_employed", "unemployed", "pensioner", "student"].map((item) => <SelectItem key={item} value={item}>{titleCase(item)}</SelectItem>)}</SelectContent></Select></Field><Field label="Employer"><Input value={employment.employer_name ?? ""} onChange={(event) => onEmploymentChange({ ...employment, employer_name: event.target.value || null })} /></Field><Field label="Employee number"><Input value={employment.employee_number ?? ""} onChange={(event) => onEmploymentChange({ ...employment, employee_number: event.target.value || null })} /></Field><Field label="Job title"><Input value={employment.job_title ?? ""} onChange={(event) => onEmploymentChange({ ...employment, job_title: event.target.value || null })} /></Field><Field label="Employment start date"><Input type="date" value={employment.employment_start_date ?? ""} onChange={(event) => onEmploymentChange({ ...employment, employment_start_date: event.target.value || null })} /></Field><Field label="Contract type"><Input value={employment.contract_type ?? ""} onChange={(event) => onEmploymentChange({ ...employment, contract_type: event.target.value || null })} /></Field><NumberField label="Gross salary" value={employment.gross_salary} min={0} onChange={(gross_salary) => onEmploymentChange({ ...employment, gross_salary })} /><NumberField label="Net salary" value={employment.net_salary} min={0} onChange={(net_salary) => onEmploymentChange({ ...employment, net_salary })} /><NumberField label="Verified net income" value={employment.verified_net_income} min={0} onChange={(verified_net_income) => onEmploymentChange({ ...employment, verified_net_income })} /><NumberField label="Salary day" value={employment.salary_day ?? 0} min={1} max={31} step="1" onChange={(salary_day) => onEmploymentChange({ ...employment, salary_day })} /><NumberField label="Payslips reviewed" value={employment.payslip_count} min={0} step="1" onChange={(payslip_count) => onEmploymentChange({ ...employment, payslip_count })} /><NumberField label="Bank statement months" value={employment.bank_statement_months} min={0} step="1" onChange={(bank_statement_months) => onEmploymentChange({ ...employment, bank_statement_months })} /><Field label="Verification status"><Select value={employment.verification_status} onValueChange={(verification_status: EmploymentProfileInput["verification_status"]) => onEmploymentChange({ ...employment, verification_status })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["unverified", "pending", "verified", "failed"].map((item) => <SelectItem key={item} value={item}>{titleCase(item)}</SelectItem>)}</SelectContent></Select></Field><Field label="Verification method"><Input value={employment.verification_method ?? ""} onChange={(event) => onEmploymentChange({ ...employment, verification_method: event.target.value || null })} placeholder="Payslip, employer call, bank statement" /></Field></div><ArrayHeader title="Additional income sources" onAdd={() => onIncomesChange([...incomes, emptyIncome()])} />{incomes.length === 0 ? <EmptyRows message="No additional income sources. Verified salary will still be used." /> : <div className="space-y-3">{incomes.map((item, index) => <div key={index} className="grid gap-3 rounded-3xl border p-4 sm:grid-cols-2 lg:grid-cols-6"><Input value={item.source_type} onChange={(event) => replaceAt(incomes, index, { ...item, source_type: event.target.value }, onIncomesChange)} placeholder="Source" /><Input value={item.description ?? ""} onChange={(event) => replaceAt(incomes, index, { ...item, description: event.target.value || null }, onIncomesChange)} placeholder="Description" /><Input type="number" min={0} step="0.01" value={item.declared_amount} onChange={(event) => replaceAt(incomes, index, { ...item, declared_amount: Number(event.target.value || 0) }, onIncomesChange)} placeholder="Declared" /><Input type="number" min={0} step="0.01" value={item.verified_amount} onChange={(event) => replaceAt(incomes, index, { ...item, verified_amount: Number(event.target.value || 0) }, onIncomesChange)} placeholder="Verified" /><Check label="Verified" checked={item.is_verified} onChange={(is_verified) => replaceAt(incomes, index, { ...item, is_verified }, onIncomesChange)} /><Button type="button" variant="ghost" onClick={() => onIncomesChange(incomes.filter((_, rowIndex) => rowIndex !== index))}><Trash2 className="h-4 w-4" /></Button></div>)}</div>}</div>;
}

function ExpensesStep({ expenses, onExpensesChange, debts, onDebtsChange }: { expenses: ExpenseInput[]; onExpensesChange: (value: ExpenseInput[]) => void; debts: DebtObligationInput[]; onDebtsChange: (value: DebtObligationInput[]) => void }) {
  function updateDebt(index: number, changes: Partial<DebtObligationInput>) {
    const current = debts[index];
    const next = { ...current, ...changes };
    if (changes.installment_amount !== undefined || changes.installment_frequency !== undefined) {
      next.monthly_installment = normalizedDebtMonthly(next.installment_amount, next.installment_frequency);
    }
    if ((changes.total_installments !== undefined || changes.installments_paid !== undefined) && next.total_installments !== null) {
      next.remaining_installments = Math.max(Number(next.total_installments) - Number(next.installments_paid || 0), 0);
      if (next.installment_frequency === "monthly") next.remaining_term_months = next.remaining_installments;
    }
    replaceAt(debts, index, next, onDebtsChange);
  }

  return (
    <div className="space-y-8">
      <div>
        <ArrayHeader title="Monthly household expenses" onAdd={() => onExpensesChange([...expenses, emptyExpense()])} />
        <div className="mt-3 space-y-3">
          {expenses.map((item, index) => (
            <div key={index} className="grid gap-3 rounded-3xl border p-4 sm:grid-cols-[1fr_1.4fr_160px_auto]">
              <Select value={item.category} onValueChange={(category) => replaceAt(expenses, index, { ...item, category }, onExpensesChange)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["rent", "electricity", "water", "food", "transport", "school_fees", "medical", "insurance", "airtime", "maintenance", "other"].map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
              <Input value={item.description ?? ""} onChange={(event) => replaceAt(expenses, index, { ...item, description: event.target.value || null }, onExpensesChange)} placeholder="Description" />
              <Input type="number" min={0} step="0.01" value={item.monthly_amount} onChange={(event) => replaceAt(expenses, index, { ...item, monthly_amount: Number(event.target.value || 0) }, onExpensesChange)} />
              <Button type="button" variant="ghost" onClick={() => onExpensesChange(expenses.filter((_, rowIndex) => rowIndex !== index))}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
        </div>
      </div>

      <div>
        <ArrayHeader title="Tracked existing debt obligations" onAdd={() => onDebtsChange([...debts, emptyDebt()])} />
        <p className="mt-1 text-sm text-muted-foreground">Each obligation keeps its start date, current balance, installment schedule and remaining installments for later affordability assessments.</p>
        {debts.length === 0 ? <EmptyRows message="No existing debts captured. Confirm this with the borrower and any available bureau report." /> : (
          <div className="mt-3 space-y-4">
            {debts.map((item, index) => (
              <div key={item.id ?? index} className="space-y-4 rounded-3xl border p-4">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Input value={item.creditor} onChange={(event) => updateDebt(index, { creditor: event.target.value })} placeholder="Creditor" />
                  <Input value={item.account_reference ?? ""} onChange={(event) => updateDebt(index, { account_reference: event.target.value || null })} placeholder="Account/reference" />
                  <Input type="date" max={new Date().toISOString().slice(0, 10)} value={item.started_on ?? ""} onChange={(event) => updateDebt(index, { started_on: event.target.value || null })} aria-label="Loan start date" />
                  <Input value={item.debt_type} onChange={(event) => updateDebt(index, { debt_type: event.target.value })} placeholder="Debt type" />
                  <Input type="number" min={0} step="0.01" value={item.original_amount} onChange={(event) => updateDebt(index, { original_amount: Number(event.target.value || 0) })} placeholder="Original amount" />
                  <Input type="number" min={0} step="0.01" value={item.current_balance} onChange={(event) => updateDebt(index, { current_balance: Number(event.target.value || 0) })} placeholder="Current balance" />
                  <Input type="number" min={0} step="0.01" value={item.installment_amount} onChange={(event) => updateDebt(index, { installment_amount: Number(event.target.value || 0) })} placeholder="Installment amount" />
                  <Select value={item.installment_frequency} onValueChange={(installment_frequency: DebtObligationInput["installment_frequency"]) => updateDebt(index, { installment_frequency })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["weekly", "fortnightly", "monthly", "quarterly", "custom"].map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                  <Input type="number" min={0} step="1" value={item.total_installments ?? ""} onChange={(event) => updateDebt(index, { total_installments: event.target.value === "" ? null : Number(event.target.value) })} placeholder="Total installments" />
                  <Input type="number" min={0} step="1" value={item.installments_paid} onChange={(event) => updateDebt(index, { installments_paid: Number(event.target.value || 0) })} placeholder="Installments paid" />
                  <Input type="number" min={0} step="1" value={item.remaining_installments ?? ""} onChange={(event) => updateDebt(index, { remaining_installments: event.target.value === "" ? null : Number(event.target.value) })} placeholder="Installments remaining" />
                  <Input type="date" value={item.next_due_date ?? ""} onChange={(event) => updateDebt(index, { next_due_date: event.target.value || null })} aria-label="Next installment due date" />
                  <Select value={item.status} onValueChange={(status: DebtObligationInput["status"]) => updateDebt(index, { status })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["active", "restructured", "defaulted", "settled", "written_off", "unknown"].map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select>
                  <Select value={item.source} onValueChange={(source) => updateDebt(index, { source })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="declared">Declared</SelectItem><SelectItem value="bank_statement">Bank statement</SelectItem><SelectItem value="bureau">Credit bureau</SelectItem><SelectItem value="document">Other document</SelectItem></SelectContent></Select>
                  <Check label="Verified" checked={item.is_verified} onChange={(is_verified) => updateDebt(index, { is_verified })} />
                  <Button type="button" variant="ghost" onClick={() => item.id ? updateDebt(index, { status: "settled", current_balance: 0, remaining_installments: 0, remaining_term_months: 0, next_due_date: null }) : onDebtsChange(debts.filter((_, rowIndex) => rowIndex !== index))}><Trash2 className="h-4 w-4" />{item.id ? "Mark settled" : "Remove"}</Button>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Summary label="Outstanding" value={formatMoney(item.current_balance)} />
                  <Summary label="Installment" value={`${formatMoney(item.installment_amount)} ${titleCase(item.installment_frequency)}`} />
                  <Summary label="Monthly equivalent" value={formatMoney(item.monthly_installment)} />
                </div>
                <Textarea rows={2} value={item.notes ?? ""} onChange={(event) => updateDebt(index, { notes: event.target.value || null })} placeholder="Debt review notes" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BankingStep({
  values,
  onChange,
  identityName,
}: {
  values: BankAccountInput[];
  onChange: (value: BankAccountInput[]) => void;
  identityName: string;
}) {
  return (
    <BankAccountsStep
      values={values}
      onChange={onChange}
      identityName={identityName}
      allowVerification
      allowTokenizedCard
      ownerLabel="Borrower"
    />
  );
}

function AffordabilityStep({ calculation, assessment, totalExpenses, totalDebts, verifiedIncome }: { calculation: MicroLoanCalculation | null; assessment: AffordabilityAssessment | null; totalExpenses: number; totalDebts: number; verifiedIncome: number }) {
  return <div className="space-y-6"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Summary label="Verified income" value={formatMoney(verifiedIncome)} /><Summary label="Household expenses" value={formatMoney(totalExpenses)} /><Summary label="Debt instalments" value={formatMoney(totalDebts)} /><Summary label="Proposed instalment" value={formatMoney(calculation?.monthly_installment ?? 0)} accent /></div>{assessment ? <div className={`rounded-3xl border p-6 ${assessment.decision === "eligible" ? "border-emerald-500/30 bg-emerald-500/10" : assessment.decision === "refer" ? "border-amber-500/30 bg-amber-500/10" : "border-red-500/30 bg-red-500/10"}`}><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">Decision</p><h3 className="mt-1 text-3xl font-black">{titleCase(assessment.overridden ? assessment.override_decision ?? assessment.decision : assessment.decision)}</h3></div><div className="text-right"><p className="text-xs text-muted-foreground">Maximum affordable instalment</p><p className="text-2xl font-black">{formatMoney(assessment.maximum_affordable_installment)}</p><p className="text-sm text-muted-foreground">Headroom {formatMoney(assessment.affordability_headroom)}</p></div></div><div className="mt-5 space-y-2">{assessment.result_reasons.map((reason) => <div key={reason.code} className="flex gap-3 rounded-2xl bg-background/70 p-3"><span>{reason.severity === "pass" ? "✓" : reason.severity === "warning" ? "⚠" : "✕"}</span><p className="text-sm">{reason.message}</p></div>)}</div></div> : <Alert><Calculator className="h-4 w-4" /><AlertTitle>Ready to calculate</AlertTitle><AlertDescription>Select Save and continue. FastAPI will calculate and permanently snapshot the policy, verified income, expenses, debts and the selected interest-method instalment.</AlertDescription></Alert>}</div>;
}

function ReviewStep({ application, profile, assessment, calculation, product, totalExpenses, totalDebts }: { application: OriginationApplication | null; profile: FinancialProfile | null; assessment: AffordabilityAssessment | null; calculation: MicroLoanCalculation | null; product: LoanProduct | null; totalExpenses: number; totalDebts: number }) {
  return <div className="space-y-6"><Alert><FileCheck2 className="h-4 w-4" /><AlertTitle>Submission creates a manager decision item</AlertTitle><AlertDescription>The loan is not created and no disbursement is recorded yet. A Branch Manager, Company Administrator or Company Owner must approve it. A signed contract is then required before Finance records money out.</AlertDescription></Alert><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Summary label="Applicant" value={profile?.identity.full_name ?? "Not selected"} /><Summary label="Product" value={product?.name ?? "Not selected"} /><Summary label="Application" value={application?.application_reference ?? "Draft not saved"} /><Summary label="KYC" value={titleCase(profile?.kyc?.status ?? "not started")} /><Summary label="Affordability" value={titleCase(assessment?.decision ?? "not calculated")} /><Summary label="Monthly instalment" value={formatMoney(calculation?.monthly_installment ?? 0)} accent /><Summary label="Total expenses" value={formatMoney(totalExpenses)} /><Summary label="Debt instalments" value={formatMoney(totalDebts)} /><Summary label="First pay date" value={application?.first_payment_date ?? "Not saved"} /></div></div>;
}

function stepDescription(step: number): string {
  return [
    "Choose the borrower and product, agree the payment date and calculate the selected interest method automatically.",
    "Verify identity, residence, contacts, consent and compliance warning indicators.",
    "Capture employment, salary evidence and all verified recurring income.",
    "Capture household living costs and every existing monthly debt obligation.",
    "Record protected bank-account details and optional provider-tokenized card information.",
    "Run the official versioned LoanHub affordability rules and review every decision reason.",
    "Confirm the complete application before it enters the manager decision queue.",
  ][step];
}

function Field({ label, children }: { label: string; children: ReactNode }) { return <div className="space-y-2"><Label>{label}</Label>{children}</div>; }
function NumberField({ label, value, onChange, min = 0, max, step = "0.01" }: { label: string; value: number; onChange: (value: number) => void; min?: number; max?: number; step?: string }) { return <Field label={label}><Input type="number" min={min} max={max} step={step} value={Number.isFinite(value) ? value : 0} onChange={(event) => onChange(Number(event.target.value || 0))} /></Field>; }
function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) { return <label className="flex cursor-pointer items-center gap-3 rounded-2xl border bg-card p-3 text-sm font-bold"><Checkbox checked={checked} onCheckedChange={(value) => onChange(value === true)} />{label}</label>; }
function ContactGroup({ title, value, onChange }: { title: string; value: Record<string, string>; onChange: (value: Record<string, string>) => void }) { return <div className="space-y-3 rounded-3xl border p-5"><h3 className="font-black">{title}</h3><Input value={value.name ?? ""} onChange={(event) => onChange({ ...value, name: event.target.value })} placeholder="Full name" /><Input value={value.phone ?? ""} onChange={(event) => onChange({ ...value, phone: event.target.value })} placeholder="Phone" /><Input value={value.relationship ?? ""} onChange={(event) => onChange({ ...value, relationship: event.target.value })} placeholder="Relationship" /></div>; }
function ArrayHeader({ title, onAdd }: { title: string; onAdd: () => void }) { return <div className="flex items-center justify-between gap-3"><h3 className="text-lg font-black">{title}</h3><Button type="button" size="sm" variant="outline" onClick={onAdd}><Plus className="h-4 w-4" />Add row</Button></div>; }
function EmptyRows({ message }: { message: string }) { return <div className="mt-3 rounded-3xl border border-dashed p-6 text-center text-sm text-muted-foreground">{message}</div>; }
function replaceAt<T>(items: T[], index: number, value: T, setter: (items: T[]) => void) { setter(items.map((item, rowIndex) => rowIndex === index ? value : item)); }
function Health({ label, ok }: { label: string; ok: boolean }) { return <div className="flex items-center justify-between gap-3 rounded-2xl border bg-background/70 p-3 text-sm"><span className="font-bold">{label}</span><Badge variant={ok ? "default" : "secondary"}>{ok ? "Ready" : "Pending"}</Badge></div>; }
function Line({ label, value }: { label: string; value: string }) { return <div className="flex items-center justify-between gap-3 border-b pb-2 last:border-0"><span className="text-muted-foreground">{label}</span><strong>{value}</strong></div>; }
function Summary({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) { return <div className={`rounded-3xl border p-5 ${accent ? "border-primary bg-primary text-primary-foreground" : "bg-muted/20"}`}><p className={`text-xs font-black uppercase tracking-wider ${accent ? "text-primary-foreground/70" : "text-muted-foreground"}`}>{label}</p><p className="mt-2 text-xl font-black">{value}</p></div>; }
