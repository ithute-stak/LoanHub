"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  BookOpenCheck,
  Calculator,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  LoaderCircle,
  Plus,
  RefreshCcw,
  Send,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { calculateLoan } from "@/api/loans";
import {
  createLegacyCashoutCapture,
  listLegacyCashoutCaptures,
  postLegacyCashoutCapture,
  reviewLegacyCashoutCapture,
  updateLegacyCashoutCapture,
} from "@/api/legacyCashout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import {
  BANK_NAMES,
  DEFAULT_BANK_BRANCH,
  bankAccountPrefixHint,
  bankAccountValidationMessage,
  bankDetails,
  isBankName,
  normalizeBankAccountNumber,
} from "@/lib/banking";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { INTEREST_METHOD_OPTIONS } from "@/lib/interest-methods";
import type { LegacyCashoutCapture, LegacyCashoutCaptureInput } from "@/types/legacyCashout";
import type { InterestMethod, LoanCalculation } from "@/types/loan";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type FormState = {
  folio_number: string;
  loan_date: string;
  first_names: string;
  surname: string;
  identity_number: string;
  passport_expiry_date: string;
  residential_address: string;
  postal_address: string;
  employer: string;
  occupation: string;
  net_salary: string;
  cell_phone: string;
  home_phone: string;
  work_phone: string;
  emergency_name: string;
  emergency_cell_phone: string;
  emergency_work_phone: string;
  emergency_relationship: string;
  bank_name: string;
  bank_account_holder: string;
  bank_account_number: string;
  bank_branch_name: string;
  bank_branch_code: string;
  bank_account_type: string;
  amount_taken: string;
  total_repayable: string;
  amount_paid: string;
  installment_count: string;
  installment_amount: string;
  repayment_type: "daily" | "weekly" | "monthly" | "custom";
  interest_rate_percent: string;
  processing_fee: string;
  calculator_method: InterestMethod;
  capture_notes: string;
};

type ViewMode = "capture" | "register";

type HistoricInstallmentAllocation = {
  installmentNumber: number;
  dueDate: string;
  dueAmount: number;
  paidAmount: number;
  balance: number;
  status: "paid" | "partial" | "unpaid";
};

const PAGE_SIZE = 10;

const FORM_STEPS: Array<{
  title: string;
  shortTitle: string;
  description: string;
  icon: LucideIcon;
}> = [
  {
    title: "Cash-out reference",
    shortTitle: "Reference",
    description: "Identify the paper record and original loan date.",
    icon: BookOpenCheck,
  },
  {
    title: "Borrower details",
    shortTitle: "Borrower",
    description: "Capture identity, contact details and addresses.",
    icon: ShieldCheck,
  },
  {
    title: "Employment & emergency",
    shortTitle: "Employment",
    description: "Record work details and an alternative contact.",
    icon: ClipboardCheck,
  },
  {
    title: "Banking details",
    shortTitle: "Banking",
    description: "Confirm the bank instruction securely.",
    icon: ShieldCheck,
  },
  {
    title: "Loan & review",
    shortTitle: "Loan & review",
    description: "Calculate the historic loan, allocate payments and save.",
    icon: Calculator,
  },
];

const emptyForm: FormState = {
  folio_number: "",
  loan_date: "",
  first_names: "",
  surname: "",
  identity_number: "",
  passport_expiry_date: "",
  residential_address: "",
  postal_address: "",
  employer: "",
  occupation: "",
  net_salary: "",
  cell_phone: "",
  home_phone: "",
  work_phone: "",
  emergency_name: "",
  emergency_cell_phone: "",
  emergency_work_phone: "",
  emergency_relationship: "",
  bank_name: "",
  bank_account_holder: "",
  bank_account_number: "",
  bank_branch_name: "",
  bank_branch_code: "",
  bank_account_type: "savings",
  amount_taken: "",
  total_repayable: "",
  amount_paid: "0",
  installment_count: "",
  installment_amount: "",
  repayment_type: "monthly",
  interest_rate_percent: "",
  processing_fee: "0",
  calculator_method: "micro_loan",
  capture_notes: "",
};

function optional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function numberValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function asNumber(value: string): number {
  return numberValue(value);
}

function snapshotNumber(snapshot: Record<string, unknown>, key: string): string {
  const value = snapshot[key];
  return typeof value === "number" || typeof value === "string" ? String(value) : "";
}

function normaliseLoanCalculation(result: LoanCalculation): LoanCalculation {
  return {
    ...result,
    principal: numberValue(result.principal),
    rate_percent: numberValue(result.rate_percent),
    months: numberValue(result.months),
    processing_fee: numberValue(result.processing_fee),
    total_interest: numberValue(result.total_interest),
    total_repayable: numberValue(result.total_repayable),
    monthly_installment: numberValue(result.monthly_installment),
    schedule_amounts: Array.isArray(result.schedule_amounts)
      ? result.schedule_amounts.map(numberValue)
      : [],
    schedule: Array.isArray(result.schedule)
      ? result.schedule.map((row) => ({
          ...row,
          installment_number: numberValue(row.installment_number),
          opening_balance: numberValue(row.opening_balance),
          principal_due: numberValue(row.principal_due),
          interest_due: numberValue(row.interest_due),
          fee_due: numberValue(row.fee_due),
          total_due: numberValue(row.total_due),
          closing_balance: numberValue(row.closing_balance),
          interest_segments: Array.isArray(row.interest_segments)
            ? row.interest_segments.map((segment) => ({
                ...segment,
                days: numberValue(segment.days),
                days_in_month: numberValue(segment.days_in_month),
                interest: numberValue(segment.interest),
              }))
            : [],
        }))
      : [],
    steps: Array.isArray(result.steps)
      ? result.steps.map((step) => ({
          ...step,
          month: numberValue(step.month),
          opening_balance: numberValue(step.opening_balance),
          amount_after_rate: numberValue(step.amount_after_rate),
          component_amount: numberValue(step.component_amount),
          carried_balance: numberValue(step.carried_balance),
        }))
      : [],
  };
}

function interestMethodFrom(value: string | null | undefined): InterestMethod {
  return INTEREST_METHOD_OPTIONS.some((option) => option.value === value)
    ? (value as InterestMethod)
    : "micro_loan";
}

function calculatorResultFrom(snapshot: Record<string, unknown>): LoanCalculation | null {
  return typeof snapshot.method === "string" && Array.isArray(snapshot.schedule)
    ? normaliseLoanCalculation(snapshot as unknown as LoanCalculation)
    : null;
}

function legacyCalculatorDueDates(loanDate: string, months: number): string[] {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(loanDate) || months < 1) return [];
  const start = new Date(`${loanDate}T00:00:00Z`);
  if (Number.isNaN(start.getTime())) return [];

  return Array.from({ length: months }, (_, index) => {
    const due = new Date(start);
    due.setUTCMonth(due.getUTCMonth() + index + 1);
    return due.toISOString().slice(0, 10);
  });
}

function allocateHistoricPayment(
  calculation: LoanCalculation | null,
  amountPaid: number,
): HistoricInstallmentAllocation[] {
  let remaining = Math.max(0, amountPaid);
  return (calculation?.schedule ?? []).map((row) => {
    const dueAmount = Math.max(0, row.total_due);
    const paidAmount = Math.min(dueAmount, remaining);
    remaining = Math.max(0, remaining - paidAmount);
    return {
      installmentNumber: row.installment_number,
      dueDate: row.due_date,
      dueAmount,
      paidAmount,
      balance: Math.max(0, dueAmount - paidAmount),
      status: paidAmount >= dueAmount ? "paid" : paidAmount > 0 ? "partial" : "unpaid",
    };
  });
}

function formFromRecord(record: LegacyCashoutCapture): FormState {
  return {
    folio_number: record.folio_number,
    loan_date: record.loan_date ?? "",
    first_names: record.first_names ?? "",
    surname: record.surname ?? "",
    identity_number: record.identity_number ?? "",
    passport_expiry_date: record.passport_expiry_date ?? "",
    residential_address: record.residential_address ?? "",
    postal_address: record.postal_address ?? "",
    employer: record.employer ?? "",
    occupation: record.occupation ?? "",
    net_salary: record.net_salary?.toString() ?? "",
    cell_phone: record.cell_phone ?? "",
    home_phone: record.home_phone ?? "",
    work_phone: record.work_phone ?? "",
    emergency_name: record.emergency_name ?? "",
    emergency_cell_phone: record.emergency_cell_phone ?? "",
    emergency_work_phone: record.emergency_work_phone ?? "",
    emergency_relationship: record.emergency_relationship ?? "",
    bank_name: record.bank_name ?? "",
    bank_account_holder: record.bank_account_holder ?? "",
    bank_account_number: "",
    bank_branch_name: record.bank_branch_name ?? "",
    bank_branch_code: record.bank_branch_code ?? "",
    bank_account_type: record.bank_account_type ?? "savings",
    amount_taken: record.amount_taken.toString(),
    total_repayable: record.total_repayable.toString(),
    amount_paid: record.amount_paid.toString(),
    installment_count: record.installment_count.toString(),
    installment_amount: record.installment_amount.toString(),
    repayment_type: record.repayment_type as FormState["repayment_type"],
    interest_rate_percent: snapshotNumber(record.calculator_snapshot, "rate_percent"),
    processing_fee: snapshotNumber(record.calculator_snapshot, "processing_fee") || "0",
    calculator_method: interestMethodFrom(record.calculator_method),
    capture_notes: record.capture_notes ?? "",
  };
}

function statusTone(status: LegacyCashoutCapture["status"]) {
  if (status === "posted") return "bg-emerald-500/10 text-emerald-700 border-emerald-500/25";
  if (status === "reviewed") return "bg-blue-500/10 text-blue-700 border-blue-500/25";
  if (status === "returned") return "bg-amber-500/10 text-amber-700 border-amber-500/25";
  return "bg-muted text-muted-foreground border-border";
}

export function LegacyCashoutRegister() {
  const [form, setForm] = useState<FormState>(emptyForm);
  const [records, setRecords] = useState<LegacyCashoutCapture[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actingId, setActingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [calculation, setCalculation] = useState<LoanCalculation | null>(null);
  const [calculatorSnapshot, setCalculatorSnapshot] = useState<Record<string, unknown>>({});
  const [activeView, setActiveView] = useState<ViewMode>("capture");
  const [currentStep, setCurrentStep] = useState(0);
  const [registerPage, setRegisterPage] = useState(1);

  const historicAllocation = useMemo(
    () => allocateHistoricPayment(calculation, asNumber(form.amount_paid)),
    [calculation, form.amount_paid],
  );
  const isNationalId = useMemo(
    () => /^\d+$/.test(form.identity_number.trim()),
    [form.identity_number],
  );
  const selectedBankDetails = useMemo(() => bankDetails(form.bank_name), [form.bank_name]);
  const bankAccountError = useMemo(
    () => bankAccountValidationMessage(form.bank_name, form.bank_account_number),
    [form.bank_name, form.bank_account_number],
  );
  const legacyBank = form.bank_name && !isBankName(form.bank_name) ? form.bank_name : null;
  const totalPages = Math.max(1, Math.ceil(records.length / PAGE_SIZE));
  const safePage = Math.min(registerPage, totalPages);
  const pageStart = (safePage - 1) * PAGE_SIZE;
  const pageRecords = records.slice(pageStart, pageStart + PAGE_SIZE);
  const visiblePageStart = Math.max(1, Math.min(safePage - 2, Math.max(1, totalPages - 4)));
  const visiblePages = Array.from(
    { length: Math.min(5, totalPages) },
    (_, index) => visiblePageStart + index,
  );
  const statusCounts = useMemo(
    () => ({
      draft: records.filter((record) => record.status === "draft" || record.status === "returned").length,
      reviewed: records.filter((record) => record.status === "reviewed").length,
      posted: records.filter((record) => record.status === "posted").length,
    }),
    [records],
  );

  useEffect(() => {
    setRegisterPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    const calculatorFields: Array<keyof FormState> = [
      "loan_date",
      "amount_taken",
      "installment_count",
      "repayment_type",
      "interest_rate_percent",
      "processing_fee",
      "calculator_method",
    ];
    if (calculatorFields.includes(key)) {
      setCalculation(null);
      setCalculatorSnapshot({});
    }
    setForm((current) => ({ ...current, [key]: value }));
  };

  const calculateLegacyTerms = async () => {
    const principal = asNumber(form.amount_taken);
    const installments = Math.trunc(asNumber(form.installment_count));
    const rate = asNumber(form.interest_rate_percent);
    const fee = asNumber(form.processing_fee);
    const dueDates = legacyCalculatorDueDates(form.loan_date, installments);

    if (principal <= 0 || installments <= 0 || !form.loan_date) {
      toast.error("Enter the loan date, amount taken and number of installments before calculating.");
      return;
    }
    if (dueDates.length !== installments) {
      toast.error("LoanHub could not generate monthly repayment dates from the loan date and term.");
      return;
    }

    setCalculating(true);
    try {
      const result = normaliseLoanCalculation(
        await calculateLoan({
          principal,
          rate_percent: rate,
          months: installments,
          processing_fee: fee,
          interest_method: form.calculator_method,
          interest_start_date: form.loan_date,
          due_dates: dueDates,
        }),
      );
      setCalculation(result);
      setCalculatorSnapshot(result as unknown as Record<string, unknown>);
      setForm((current) => ({
        ...current,
        total_repayable: result.total_repayable.toFixed(2),
        installment_amount: result.monthly_installment.toFixed(2),
        repayment_type: "monthly",
      }));
      toast.success("LoanHub calculation applied to this historic entry.");
    } catch (error) {
      toast.error(getErrorMessage(error, "The LoanHub calculation could not be completed."));
    } finally {
      setCalculating(false);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      setRecords(await listLegacyCashoutCaptures());
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not load the legacy cash-out register"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const validateStep = (step: number): boolean => {
    if (step === 0 && (!form.folio_number.trim() || !form.loan_date)) {
      toast.error("Enter the folio number and original loan date before continuing.");
      return false;
    }
    if (
      step === 1
      && form.identity_number.trim()
      && !isNationalId
      && !form.passport_expiry_date
    ) {
      toast.error("Enter the passport expiry date before continuing.");
      return false;
    }
    if (step === 3) {
      if (!isBankName(form.bank_name)) {
        toast.error("Select FNB, PB, STD or NB before continuing.");
        return false;
      }
      if (!form.bank_account_holder.trim()) {
        toast.error("Enter the bank account holder before continuing.");
        return false;
      }
      if (bankAccountError) {
        toast.error(bankAccountError);
        return false;
      }
    }
    return true;
  };

  const nextStep = () => {
    if (!validateStep(currentStep)) return;
    setCurrentStep((step) => Math.min(FORM_STEPS.length - 1, step + 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const resetEntry = () => {
    setForm(emptyForm);
    setEditingId(null);
    setCalculation(null);
    setCalculatorSnapshot({});
    setCurrentStep(0);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    try {
      if (!form.folio_number.trim() || !form.loan_date) {
        toast.error("The folio number and original loan date are required.");
        setCurrentStep(0);
        return;
      }
      if (form.identity_number.trim() && !isNationalId && !form.passport_expiry_date) {
        toast.error("The passport expiry date is required for a passport identity.");
        setCurrentStep(1);
        return;
      }
      if (Object.keys(calculatorSnapshot).length === 0) {
        toast.error("Calculate the original loan with LoanHub before saving this entry.");
        return;
      }
      if (!isBankName(form.bank_name)) {
        toast.error("Select FNB, PB, STD or NB before saving this entry.");
        setCurrentStep(3);
        return;
      }
      if (!form.bank_account_holder.trim()) {
        toast.error("Enter the bank account holder before saving this entry.");
        setCurrentStep(3);
        return;
      }
      if (bankAccountError) {
        toast.error(bankAccountError);
        setCurrentStep(3);
        return;
      }
      const banking = bankDetails(form.bank_name);
      if (!banking) {
        toast.error("Select a supported bank before saving this entry.");
        setCurrentStep(3);
        return;
      }
      if (asNumber(form.amount_taken) <= 0 || Math.trunc(asNumber(form.installment_count)) <= 0) {
        toast.error("Enter valid loan amount and installment details before saving.");
        return;
      }

      const payload: LegacyCashoutCaptureInput = {
        folio_number: form.folio_number,
        loan_date: form.loan_date,
        first_names: form.first_names,
        surname: form.surname,
        identity_number: form.identity_number,
        passport_expiry_date: optional(form.passport_expiry_date),
        residential_address: optional(form.residential_address),
        postal_address: optional(form.postal_address),
        employer: optional(form.employer),
        occupation: optional(form.occupation),
        net_salary: form.net_salary ? asNumber(form.net_salary) : null,
        cell_phone: form.cell_phone,
        home_phone: optional(form.home_phone),
        work_phone: optional(form.work_phone),
        emergency_name: optional(form.emergency_name),
        emergency_cell_phone: optional(form.emergency_cell_phone),
        emergency_work_phone: optional(form.emergency_work_phone),
        emergency_relationship: optional(form.emergency_relationship),
        bank_name: banking.name,
        bank_account_holder: form.bank_account_holder,
        bank_account_number: normalizeBankAccountNumber(form.bank_account_number),
        bank_branch_name: banking.branch,
        bank_branch_code: banking.code,
        bank_account_type: form.bank_account_type,
        amount_taken: asNumber(form.amount_taken),
        total_repayable: asNumber(form.total_repayable),
        amount_paid: asNumber(form.amount_paid),
        installment_count: Math.trunc(asNumber(form.installment_count)),
        installment_amount: asNumber(form.installment_amount),
        repayment_type: form.repayment_type,
        calculator_method: form.calculator_method,
        calculator_snapshot: calculatorSnapshot,
        capture_notes: optional(form.capture_notes),
      };
      const wasEditing = Boolean(editingId);
      const saved = editingId
        ? await updateLegacyCashoutCapture(editingId, payload)
        : await createLegacyCashoutCapture(payload);
      setRecords((current) =>
        editingId
          ? current.map((item) => (item.id === saved.id ? saved : item))
          : [saved, ...current],
      );
      resetEntry();
      setRegisterPage(1);
      setActiveView("register");
      toast.success(wasEditing ? "Cash-out draft updated" : "Cash-out entry saved for review");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not save the cash-out entry"));
    } finally {
      setSaving(false);
    }
  };

  const continueEntry = (record: LegacyCashoutCapture) => {
    setForm(formFromRecord(record));
    setEditingId(record.id);
    setCalculatorSnapshot(record.calculator_snapshot);
    setCalculation(calculatorResultFrom(record.calculator_snapshot));
    setCurrentStep(0);
    setActiveView("capture");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const replaceRecord = (record: LegacyCashoutCapture) => {
    setRecords((current) => current.map((item) => (item.id === record.id ? record : item)));
  };

  const approve = async (record: LegacyCashoutCapture) => {
    setActingId(record.id);
    try {
      replaceRecord(
        await reviewLegacyCashoutCapture(record.id, {
          approve_for_posting: true,
          verified_against_cashout_book: true,
        }),
      );
      toast.success("Entry approved for posting");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not approve this entry"));
    } finally {
      setActingId(null);
    }
  };

  const post = async (record: LegacyCashoutCapture) => {
    setActingId(record.id);
    try {
      replaceRecord(await postLegacyCashoutCapture(record.id));
      toast.success("Historic loan posted into the live LoanHub portfolio");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not post this entry"));
    } finally {
      setActingId(null);
    }
  };

  const startNewEntry = () => {
    resetEntry();
    setActiveView("capture");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-10">
      <section className="overflow-hidden rounded-[2rem] border bg-gradient-to-br from-primary/12 via-card to-emerald-500/10 shadow-sm">
        <div className="p-6 sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2 text-primary">
                <BookOpenCheck className="h-5 w-5" />
                <span className="text-xs font-black uppercase tracking-[0.18em]">Historical records</span>
                {editingId ? <Badge variant="outline">Editing existing draft</Badge> : null}
              </div>
              <h1 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">Legacy cash-out register</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
                Capture paper cash-out records through a guided workflow, verify them against the original book,
                then post approved records into the live LoanHub portfolio.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:min-w-[360px]">
              <StatPill label="Needs review" value={statusCounts.draft} />
              <StatPill label="Approved" value={statusCounts.reviewed} />
              <StatPill label="Posted" value={statusCounts.posted} />
            </div>
          </div>
        </div>

        <div className="border-t bg-background/70 p-2 backdrop-blur">
          <div className="grid gap-2 sm:grid-cols-2" role="tablist" aria-label="Legacy cash-out workspace">
            <button
              type="button"
              role="tab"
              aria-selected={activeView === "capture"}
              onClick={() => setActiveView("capture")}
              className={`flex items-center justify-center gap-3 rounded-2xl px-4 py-3 text-sm font-black transition ${
                activeView === "capture"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Plus className="h-4 w-4" />
              {editingId ? "Continue entry" : "Capture entry"}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeView === "register"}
              onClick={() => setActiveView("register")}
              className={`flex items-center justify-center gap-3 rounded-2xl px-4 py-3 text-sm font-black transition ${
                activeView === "register"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <BookOpenCheck className="h-4 w-4" />
              Register
              <span className={`rounded-full px-2 py-0.5 text-[11px] ${activeView === "register" ? "bg-primary-foreground/15" : "bg-muted"}`}>
                {records.length}
              </span>
            </button>
          </div>
        </div>
      </section>

      {activeView === "capture" ? (
        <form id="legacy-cashout-form" onSubmit={submit} className="space-y-5">
          <Card className="overflow-hidden border-primary/15 shadow-sm">
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <div className="grid min-w-[760px] grid-cols-5">
                  {FORM_STEPS.map((step, index) => {
                    const Icon = step.icon;
                    const active = index === currentStep;
                    const complete = index < currentStep;
                    return (
                      <button
                        key={step.shortTitle}
                        type="button"
                        onClick={() => {
                          if (index <= currentStep || validateStep(currentStep)) {
                            setCurrentStep(index);
                          }
                        }}
                        className={`relative flex min-h-24 items-start gap-3 border-r px-4 py-4 text-left transition last:border-r-0 ${
                          active ? "bg-primary/8" : "hover:bg-muted/50"
                        }`}
                      >
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-xs font-black ${
                          active
                            ? "border-primary bg-primary text-primary-foreground"
                            : complete
                              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
                              : "bg-background text-muted-foreground"
                        }`}>
                          {complete ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                        </span>
                        <span>
                          <span className="block text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">Step {index + 1}</span>
                          <span className={`mt-1 block text-sm font-black ${active ? "text-primary" : "text-foreground"}`}>{step.shortTitle}</span>
                        </span>
                        {active ? <span className="absolute inset-x-0 bottom-0 h-1 bg-primary" /> : null}
                      </button>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex items-start justify-between gap-4 rounded-2xl border bg-muted/25 px-5 py-4">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">Step {currentStep + 1} of {FORM_STEPS.length}</p>
              <h2 className="mt-1 text-xl font-black">{FORM_STEPS[currentStep].title}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{FORM_STEPS[currentStep].description}</p>
            </div>
            <span className="hidden rounded-full bg-primary/10 px-3 py-1 text-xs font-black text-primary sm:inline-flex">
              {Math.round(((currentStep + 1) / FORM_STEPS.length) * 100)}% complete
            </span>
          </div>

          {currentStep === 0 ? (
            <WizardSection icon={BookOpenCheck} title="Locate the original entry" description="Use the folio and original loan date so the paper source stays easy to trace during review.">
              <div className="grid gap-5 sm:grid-cols-2">
                <Field label="Folio number" required>
                  <Input autoFocus value={form.folio_number} onChange={(event) => update("folio_number", event.target.value)} placeholder="e.g. 00124" />
                </Field>
                <Field label="Original loan date" required>
                  <Input type="date" value={form.loan_date} onChange={(event) => update("loan_date", event.target.value)} />
                </Field>
              </div>
              <InfoPanel>
                The folio and date link this digital record back to the cash-out book. No live LoanHub cash transaction is created at this stage.
              </InfoPanel>
            </WizardSection>
          ) : null}

          {currentStep === 1 ? (
            <WizardSection icon={ShieldCheck} title="Borrower identity and contacts" description="Digits only are treated as a Lesotho national ID. An identity containing letters is treated as a passport and requires an expiry date.">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="First names"><Input value={form.first_names} onChange={(event) => update("first_names", event.target.value)} /></Field>
                <Field label="Surname"><Input value={form.surname} onChange={(event) => update("surname", event.target.value)} /></Field>
                <Field label="National ID or passport number">
                  <Input value={form.identity_number} onChange={(event) => {
                    const value = event.target.value;
                    setForm((current) => ({
                      ...current,
                      identity_number: value,
                      passport_expiry_date: !value.trim() || /^\d+$/.test(value.trim()) ? "" : current.passport_expiry_date,
                    }));
                  }} />
                </Field>
                {!isNationalId && form.identity_number.trim() ? (
                  <Field label="Passport expiry date" required><Input type="date" value={form.passport_expiry_date} onChange={(event) => update("passport_expiry_date", event.target.value)} /></Field>
                ) : null}
                <Field label="Cell number"><Input value={form.cell_phone} onChange={(event) => update("cell_phone", event.target.value)} /></Field>
                <Field label="Home number"><Input value={form.home_phone} onChange={(event) => update("home_phone", event.target.value)} /></Field>
                <Field label="Work number"><Input value={form.work_phone} onChange={(event) => update("work_phone", event.target.value)} /></Field>
              </div>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <Field label="Residential / physical address"><Textarea value={form.residential_address} onChange={(event) => update("residential_address", event.target.value)} /></Field>
                <Field label="Postal address"><Textarea value={form.postal_address} onChange={(event) => update("postal_address", event.target.value)} /></Field>
              </div>
            </WizardSection>
          ) : null}

          {currentStep === 2 ? (
            <WizardSection icon={ClipboardCheck} title="Employment and emergency contact" description="These details become part of the borrower profile and authorised alternative calling contacts.">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Employer"><Input value={form.employer} onChange={(event) => update("employer", event.target.value)} /></Field>
                <Field label="Occupation"><Input value={form.occupation} onChange={(event) => update("occupation", event.target.value)} /></Field>
                <Field label="Net salary"><Input type="number" min="0" step="0.01" value={form.net_salary} onChange={(event) => update("net_salary", event.target.value)} /></Field>
                <Field label="Emergency contact name"><Input value={form.emergency_name} onChange={(event) => update("emergency_name", event.target.value)} /></Field>
                <Field label="Emergency relationship"><Input value={form.emergency_relationship} onChange={(event) => update("emergency_relationship", event.target.value)} /></Field>
                <Field label="Emergency cell"><Input value={form.emergency_cell_phone} onChange={(event) => update("emergency_cell_phone", event.target.value)} /></Field>
                <Field label="Emergency work number"><Input value={form.emergency_work_phone} onChange={(event) => update("emergency_work_phone", event.target.value)} /></Field>
              </div>
            </WizardSection>
          ) : null}

          {currentStep === 3 ? (
            <WizardSection icon={ShieldCheck} title="Secure banking instruction" description={editingId ? "Re-enter the account number to confirm this update. LoanHub encrypts it and never displays it again." : "Banking details are required for every saved cash-out entry. LoanHub encrypts the account number and later shows only the last four digits."}>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Bank name" required>
                  <NativeSelect
                    value={form.bank_name}
                    onChange={(event) => {
                      const bankName = event.target.value;
                      const details = bankDetails(bankName);
                      setForm((current) => ({
                        ...current,
                        bank_name: bankName,
                        bank_branch_name: details?.branch ?? current.bank_branch_name,
                        bank_branch_code: details?.code ?? current.bank_branch_code,
                      }));
                    }}
                  >
                    <option value="">Select bank</option>
                    {legacyBank ? <option value={legacyBank}>Legacy — {legacyBank} (select a supported bank to save)</option> : null}
                    {BANK_NAMES.map((bankName) => <option key={bankName} value={bankName}>{bankName}</option>)}
                  </NativeSelect>
                </Field>
                <Field label="Account holder" required><Input value={form.bank_account_holder} onChange={(event) => update("bank_account_holder", event.target.value)} /></Field>
                <Field label={editingId ? "Account number (re-enter to update)" : "Account number"} required>
                  <div className="space-y-1.5">
                    <Input
                      type="text"
                      inputMode="numeric"
                      autoComplete="off"
                      aria-invalid={Boolean(bankAccountError)}
                      placeholder={editingId ? "Enter the account number again" : undefined}
                      value={form.bank_account_number}
                      onChange={(event) => update("bank_account_number", event.target.value)}
                    />
                    <p className={`text-xs ${bankAccountError ? "font-semibold text-destructive" : "text-muted-foreground"}`}>
                      {bankAccountError ?? bankAccountPrefixHint(form.bank_name)}
                    </p>
                  </div>
                </Field>
                <Field label="Branch name"><Input readOnly value={selectedBankDetails?.branch ?? (form.bank_branch_name || DEFAULT_BANK_BRANCH)} className="bg-muted/40" /></Field>
                <Field label="Branch code"><Input readOnly value={selectedBankDetails?.code ?? form.bank_branch_code} className="bg-muted/40" /></Field>
                <Field label="Account type"><Input value={form.bank_account_type} onChange={(event) => update("bank_account_type", event.target.value)} /></Field>
              </div>
              <InfoPanel>
                The full bank account number is not returned to the browser after saving. Editing a draft therefore requires the operator to confirm it again.
              </InfoPanel>
            </WizardSection>
          ) : null}

          {currentStep === 4 ? (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <ReviewTile label="Folio" value={form.folio_number || "Not entered"} />
                <ReviewTile label="Borrower" value={[form.first_names, form.surname].filter(Boolean).join(" ") || "Name not entered"} />
                <ReviewTile label="Bank" value={form.bank_name || "Not selected"} />
                <ReviewTile label="Historic paid" value={formatMoney(asNumber(form.amount_paid))} />
              </div>

              <WizardSection icon={Calculator} title="LoanHub loan calculator" description="Use the same calculator as normal LoanHub loans. The calculated repayment schedule becomes the basis for the historic opening balance.">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Field label="Amount taken" required><Input type="number" min="0.01" step="0.01" value={form.amount_taken} onChange={(event) => update("amount_taken", event.target.value)} /></Field>
                  <Field label="Interest rate (%)" required><Input type="number" min="0" step="0.0001" value={form.interest_rate_percent} onChange={(event) => update("interest_rate_percent", event.target.value)} /></Field>
                  <Field label="Number of months" required><Input type="number" min="1" max="120" value={form.installment_count} onChange={(event) => update("installment_count", event.target.value)} /></Field>
                  <Field label="Processing fee"><Input type="number" min="0" step="0.01" value={form.processing_fee} onChange={(event) => update("processing_fee", event.target.value)} /></Field>
                  <Field label="LoanHub calculator">
                    <NativeSelect value={form.calculator_method} onChange={(event) => update("calculator_method", event.target.value as InterestMethod)}>
                      {INTEREST_METHOD_OPTIONS.map((method) => <option key={method.value} value={method.value}>{method.label}</option>)}
                    </NativeSelect>
                  </Field>
                  <Field label="Schedule frequency"><Input readOnly value="Monthly — calculated from loan date" className="bg-muted/40 font-semibold" /></Field>
                </div>

                <div className="mt-5 flex flex-col gap-3 rounded-2xl border bg-primary/[0.035] p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-black">Calculate before saving</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">If you change the date, amount, term, rate, fee or calculator method, calculate again so the saved schedule remains authoritative.</p>
                  </div>
                  <Button type="button" onClick={() => void calculateLegacyTerms()} disabled={calculating} className="shrink-0">
                    {calculating ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Calculator className="h-4 w-4" />}
                    Calculate with LoanHub
                  </Button>
                </div>

                <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <Field label="Calculated total repayable"><Input readOnly type="number" value={form.total_repayable} className="bg-muted/40 font-semibold" /></Field>
                  <Field label="Calculated installment amount"><Input readOnly type="number" value={form.installment_amount} className="bg-muted/40 font-semibold" /></Field>
                  <Field label="Amount paid in the historic book"><Input type="number" min="0" step="0.01" value={form.amount_paid} onChange={(event) => update("amount_paid", event.target.value)} /></Field>
                </div>

                {calculation ? (
                  <div className="mt-5 grid gap-3 rounded-2xl border bg-muted/30 p-4 sm:grid-cols-3">
                    <ReviewTile label="Calculator method" value={calculation.method_label} plain />
                    <ReviewTile label="First payment" value={formatDate(calculation.first_payment_date)} plain />
                    <ReviewTile label="Maturity date" value={formatDate(calculation.maturity_date)} plain />
                  </div>
                ) : null}

                {historicAllocation.length > 0 ? (
                  <div className="mt-5 overflow-hidden rounded-2xl border">
                    <div className="flex flex-col gap-2 border-b bg-muted/30 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="font-black">Historic payment allocation</p>
                        <p className="mt-1 text-xs text-muted-foreground">Payments are allocated to the earliest calculated installments first. This is opening-balance evidence only.</p>
                      </div>
                      <p className="text-sm font-black">Outstanding {formatMoney(historicAllocation.reduce((total, row) => total + row.balance, 0))}</p>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[650px] text-sm">
                        <thead className="bg-muted/20 text-left text-xs font-bold uppercase tracking-wide text-muted-foreground">
                          <tr><th className="px-4 py-3">Installment</th><th className="px-4 py-3">Due date</th><th className="px-4 py-3 text-right">Due</th><th className="px-4 py-3 text-right">Historic paid</th><th className="px-4 py-3 text-right">Outstanding</th><th className="px-4 py-3">Status</th></tr>
                        </thead>
                        <tbody>
                          {historicAllocation.map((row) => (
                            <tr key={row.installmentNumber} className="border-t">
                              <td className="px-4 py-3 font-semibold">{row.installmentNumber}</td>
                              <td className="px-4 py-3">{formatDate(row.dueDate)}</td>
                              <td className="px-4 py-3 text-right">{formatMoney(row.dueAmount)}</td>
                              <td className="px-4 py-3 text-right">{formatMoney(row.paidAmount)}</td>
                              <td className="px-4 py-3 text-right">{formatMoney(row.balance)}</td>
                              <td className="px-4 py-3">
                                <Badge variant="outline" className={row.status === "paid" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-700" : row.status === "partial" ? "border-amber-500/25 bg-amber-500/10 text-amber-700" : "border-border bg-muted text-muted-foreground"}>
                                  {row.status === "paid" ? "Paid" : row.status === "partial" ? "Partially paid" : "Unpaid"}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : null}

                <div className="mt-5"><Field label="Capture notes"><Textarea placeholder="Anything written in the cash-out book that must be preserved for review" value={form.capture_notes} onChange={(event) => update("capture_notes", event.target.value)} /></Field></div>
              </WizardSection>
            </div>
          ) : null}

          <Card className="sticky bottom-3 z-20 border-primary/15 bg-background/95 shadow-lg backdrop-blur">
            <CardContent className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex gap-2">
                {editingId ? <Button type="button" variant="outline" onClick={resetEntry} disabled={saving}>Cancel edit</Button> : null}
                {currentStep > 0 ? (
                  <Button type="button" variant="outline" onClick={() => setCurrentStep((step) => Math.max(0, step - 1))} disabled={saving}>
                    <ChevronLeft className="h-4 w-4" />Back
                  </Button>
                ) : null}
              </div>
              <div className="flex items-center justify-end gap-2">
                <span className="hidden text-xs font-bold text-muted-foreground md:inline">Step {currentStep + 1} of {FORM_STEPS.length}</span>
                {currentStep < FORM_STEPS.length - 1 ? (
                  <Button type="button" onClick={nextStep}>
                    Continue<ChevronRight className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button type="submit" disabled={saving || calculating}>
                    {saving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : editingId ? <CheckCircle2 className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                    {editingId ? "Update draft" : "Save for review"}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </form>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <RegisterStat label="Needs review" value={statusCounts.draft} description="Draft or returned" />
            <RegisterStat label="Approved" value={statusCounts.reviewed} description="Ready to post" />
            <RegisterStat label="Posted" value={statusCounts.posted} description="Live LoanHub loans" />
          </div>

          <Card className="overflow-hidden shadow-sm">
            <CardHeader className="border-b bg-muted/15">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <CardTitle>Captured entries</CardTitle>
                  <CardDescription className="mt-1">Only reviewed entries can be posted. Customer-facing pages do not display internal identifiers.</CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => void load()} disabled={loading}>
                    <RefreshCcw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />Refresh
                  </Button>
                  <Button onClick={startNewEntry}><Plus className="h-4 w-4" />New entry</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? <div className="flex items-center gap-3 p-8 text-sm text-muted-foreground"><LoaderCircle className="h-5 w-5 animate-spin" />Loading legacy entries…</div> : null}
              {!loading && records.length === 0 ? (
                <div className="flex min-h-64 flex-col items-center justify-center p-8 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted"><BookOpenCheck className="h-6 w-6 text-muted-foreground" /></div>
                  <p className="mt-4 font-black">No captured entries yet</p>
                  <p className="mt-1 max-w-md text-sm text-muted-foreground">Start with the first cash-out book entry. Saved drafts will appear here for review and posting.</p>
                  <Button className="mt-4" onClick={startNewEntry}><Plus className="h-4 w-4" />Capture first entry</Button>
                </div>
              ) : null}
              {!loading && records.length > 0 ? (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[980px] text-sm">
                      <thead className="bg-muted/40 text-left text-xs font-black uppercase tracking-wide text-muted-foreground">
                        <tr><th className="px-5 py-3">Book reference</th><th className="px-5 py-3">Borrower</th><th className="px-5 py-3">Original loan</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Actions</th></tr>
                      </thead>
                      <tbody>
                        {pageRecords.map((record) => (
                          <tr key={record.id} className="border-t transition hover:bg-muted/20">
                            <td className="px-5 py-4 align-top">
                              <p className="font-black">Folio {record.folio_number}</p>
                              <p className="mt-1 text-xs text-muted-foreground">{[record.cashout_book_number && `Book ${record.cashout_book_number}`, record.page_number && `Page ${record.page_number}`, record.loan_date && formatDate(record.loan_date)].filter(Boolean).join(" · ") || "Book reference not recorded"}</p>
                            </td>
                            <td className="px-5 py-4 align-top">
                              <p className="font-black">{record.borrower_name}</p>
                              <p className="mt-1 text-xs text-muted-foreground">{record.identity_type === "national_id" ? "Lesotho national ID" : record.identity_type === "passport" ? "Passport" : "Identity still to be captured"} · {record.cell_phone ?? "No cell number"}</p>
                            </td>
                            <td className="px-5 py-4 align-top">
                              <p className="font-black">{formatMoney(record.amount_taken)}</p>
                              <p className="mt-1 text-xs text-muted-foreground">{record.installment_count} {titleCase(record.repayment_type)} installments · paid {formatMoney(record.amount_paid)} · balance {formatMoney(record.balance)}</p>
                              {record.loan_reference ? <p className="mt-1 text-xs font-black text-primary">Loan {record.loan_reference}</p> : null}
                            </td>
                            <td className="px-5 py-4 align-top">
                              <Badge className={statusTone(record.status)} variant="outline">{titleCase(record.status)}</Badge>
                              {record.review_notes ? <p className="mt-2 max-w-52 text-xs text-muted-foreground">{record.review_notes}</p> : null}
                            </td>
                            <td className="px-5 py-4 align-top">
                              <div className="flex flex-wrap gap-2">
                                {record.status === "draft" || record.status === "returned" ? <Button size="sm" variant="outline" disabled={actingId === record.id || saving} onClick={() => continueEntry(record)}><BookOpenCheck className="h-3.5 w-3.5" />Continue entry</Button> : null}
                                {record.status === "draft" || record.status === "returned" ? <Button size="sm" variant="outline" disabled={actingId === record.id} onClick={() => void approve(record)}><ClipboardCheck className="h-3.5 w-3.5" />Review & approve</Button> : null}
                                {record.status === "reviewed" ? <Button size="sm" disabled={actingId === record.id} onClick={() => void post(record)}>{actingId === record.id ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}Post live loan</Button> : null}
                                {record.status === "posted" ? <Button asChild size="sm" variant="outline"><Link href="/company/clients">Open borrower profiles</Link></Button> : null}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="flex flex-col gap-3 border-t bg-muted/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                    <p className="text-xs font-semibold text-muted-foreground">
                      Showing <span className="font-black text-foreground">{pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, records.length)}</span> of <span className="font-black text-foreground">{records.length}</span> entries
                    </p>
                    <div className="flex flex-wrap items-center gap-1.5" aria-label="Register pagination">
                      <Button type="button" size="sm" variant="outline" disabled={safePage === 1} onClick={() => setRegisterPage((page) => Math.max(1, page - 1))}>
                        <ChevronLeft className="h-4 w-4" /><span className="hidden sm:inline">Previous</span>
                      </Button>
                      {visiblePageStart > 1 ? <><PageButton page={1} currentPage={safePage} onSelect={setRegisterPage} />{visiblePageStart > 2 ? <span className="px-1 text-xs text-muted-foreground">…</span> : null}</> : null}
                      {visiblePages.map((page) => <PageButton key={page} page={page} currentPage={safePage} onSelect={setRegisterPage} />)}
                      {visiblePages[visiblePages.length - 1] < totalPages ? <>{visiblePages[visiblePages.length - 1] < totalPages - 1 ? <span className="px-1 text-xs text-muted-foreground">…</span> : null}<PageButton page={totalPages} currentPage={safePage} onSelect={setRegisterPage} /></> : null}
                      <Button type="button" size="sm" variant="outline" disabled={safePage === totalPages} onClick={() => setRegisterPage((page) => Math.min(totalPages, page + 1))}>
                        <span className="hidden sm:inline">Next</span><ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function WizardSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Card className="overflow-hidden shadow-sm">
      <CardHeader className="border-b bg-muted/10">
        <CardTitle className="flex items-center gap-2 text-lg"><Icon className="h-5 w-5 text-primary" />{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="p-5 sm:p-6">{children}</CardContent>
    </Card>
  );
}

function Field({ label, required = false, children }: { label: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="block space-y-2">
      <Label className="text-sm font-bold">{label}{required ? <span className="ml-1 text-destructive">*</span> : null}</Label>
      {children}
    </label>
  );
}

function InfoPanel({ children }: { children: ReactNode }) {
  return <div className="mt-5 rounded-2xl border border-primary/15 bg-primary/[0.035] px-4 py-3 text-xs leading-5 text-muted-foreground">{children}</div>;
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border bg-background/80 px-3 py-3 text-center shadow-sm backdrop-blur">
      <p className="text-xl font-black tracking-tight">{value}</p>
      <p className="mt-0.5 text-[10px] font-black uppercase tracking-wide text-muted-foreground">{label}</p>
    </div>
  );
}

function RegisterStat({ label, value, description }: { label: string; value: number; description: string }) {
  return (
    <Card className="shadow-sm">
      <CardContent className="flex items-center justify-between p-5">
        <div><p className="text-xs font-black uppercase tracking-[0.14em] text-muted-foreground">{label}</p><p className="mt-1 text-sm text-muted-foreground">{description}</p></div>
        <p className="text-3xl font-black tracking-tight">{value}</p>
      </CardContent>
    </Card>
  );
}

function ReviewTile({ label, value, plain = false }: { label: string; value: string; plain?: boolean }) {
  return (
    <div className={plain ? "" : "rounded-2xl border bg-card p-4 shadow-sm"}>
      <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-sm font-black" title={value}>{value}</p>
    </div>
  );
}

function PageButton({ page, currentPage, onSelect }: { page: number; currentPage: number; onSelect: (page: number) => void }) {
  const active = page === currentPage;
  return (
    <button
      type="button"
      aria-current={active ? "page" : undefined}
      onClick={() => onSelect(page)}
      className={`flex h-8 min-w-8 items-center justify-center rounded-lg border px-2 text-xs font-black transition ${active ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:border-primary/40 hover:text-primary"}`}
    >
      {page}
    </button>
  );
}
