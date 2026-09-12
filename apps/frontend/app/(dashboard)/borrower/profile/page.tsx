"use client";

import { originationApi } from "@/api/origination";
import { BorrowerEvaluationEvidence } from "@/components/borrower/borrower-evaluation-evidence";
import { BankAccountsStep } from "@/components/clients/bank-accounts-step";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import { NativeSelect } from "@/components/ui/native-select";
import { PageLoader } from "@/components/ui/page-loader";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { useAppDispatch } from "@/store/hooks";
import { fetchCurrentUser } from "@/store/slices/authSlice";
import type {
  BankAccountInput,
  BorrowerProfileActivity,
  DebtObligationInput,
  EmploymentProfileInput,
  ExpenseInput,
  FinancialProfile,
  FinancialProfileUpdate,
  IncomeSourceInput,
  KYCProfileInput,
} from "@/types/origination";
import type { Person } from "@/types/person";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  BriefcaseBusiness,
  Calculator,
  CheckCircle2,
  Clock3,
  FileCheck2,
  Landmark,
  Plus,
  ReceiptText,
  Save,
  ShieldCheck,
  Trash2,
  UserRound,
  WalletCards,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

const steps = [
  { label: "Application", icon: ReceiptText },
  { label: "KYC", icon: ShieldCheck },
  { label: "Employment", icon: BriefcaseBusiness },
  { label: "Expenses & debt", icon: WalletCards },
  { label: "Banking", icon: Landmark },
  { label: "Affordability", icon: Calculator },
  { label: "Review & activity", icon: FileCheck2 },
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


const emptyBorrower = {
  consent_to_share_profile: false,
  consent_to_share_documents: false,
  consent_to_credit_checks: false,
};

export default function BorrowerProfilePage() {
  const dispatch = useAppDispatch();
  const { user, currentBorrower, refreshAllData } = useAppData();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [profile, setProfile] = useState<FinancialProfile | null>(null);
  const [activity, setActivity] = useState<BorrowerProfileActivity[]>([]);
  const [person, setPerson] = useState({
    first_name: "",
    middle_name: "",
    last_name: "",
    nationality: "Mosotho",
    district: "",
    town_or_village: "",
    physical_address: "",
  });
  const [borrower, setBorrower] = useState(emptyBorrower);
  const [kyc, setKyc] = useState<KYCProfileInput>(emptyKyc);
  const [employment, setEmployment] = useState<EmploymentProfileInput>(emptyEmployment);
  const [incomeSources, setIncomeSources] = useState<IncomeSourceInput[]>([]);
  const [expenses, setExpenses] = useState<ExpenseInput[]>([emptyExpense()]);
  const [debts, setDebts] = useState<DebtObligationInput[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccountInput[]>([]);

  const fullName = [person.first_name, person.middle_name, person.last_name].filter(Boolean).join(" ");

  const applyProfile = useCallback((row: FinancialProfile) => {
    setProfile(row);
    setKyc(row.kyc ? { ...row.kyc } : emptyKyc);
    setEmployment(row.employment ? {
      ...row.employment,
      gross_salary: Number(row.employment.gross_salary),
      net_salary: Number(row.employment.net_salary),
      verified_net_income: Number(row.employment.verified_net_income),
      payslip_count: Number(row.employment.payslip_count),
      bank_statement_months: Number(row.employment.bank_statement_months),
    } : emptyEmployment);
    setIncomeSources(row.income_sources.map(({ id: _id, ...item }) => ({
      ...item,
      declared_amount: Number(item.declared_amount),
      verified_amount: Number(item.verified_amount),
    })));
    setExpenses(row.expenses.length ? row.expenses.map(({ id: _id, ...item }) => ({
      ...item,
      monthly_amount: Number(item.monthly_amount),
    })) : [emptyExpense()]);
    setDebts(row.debts.map((item) => ({
      ...item,
      original_amount: Number(item.original_amount),
      current_balance: Number(item.current_balance),
      installment_amount: Number(item.installment_amount ?? item.monthly_installment ?? 0),
      monthly_installment: Number(item.monthly_installment),
      installments_paid: Number(item.installments_paid || 0),
    })));
    const rows = row.bank_accounts ?? (row.bank_account ? [row.bank_account] : []);
    setBankAccounts(rows.map((item) => ({
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
    if (!currentBorrower || !user?.person) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setPerson({
        first_name: user.person.first_name ?? "",
        middle_name: user.person.middle_name ?? "",
        last_name: user.person.last_name ?? "",
        nationality: user.person.nationality ?? "Mosotho",
        district: user.person.district ?? "",
        town_or_village: user.person.town_or_village ?? "",
        physical_address: user.person.physical_address ?? "",
      });
      setBorrower({
        consent_to_share_profile: currentBorrower.consent_to_share_profile,
        consent_to_share_documents: currentBorrower.consent_to_share_documents,
        consent_to_credit_checks: currentBorrower.consent_to_credit_checks,
      });
      const [financial, events] = await Promise.all([
        originationApi.getMyFinancialProfile(),
        originationApi.getMyProfileActivity(),
      ]);
      applyProfile(financial);
      setActivity(events);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Could not load the shared assessment profile"));
    } finally {
      setLoading(false);
    }
  }, [applyProfile, currentBorrower, user?.person]);

  useEffect(() => {
    void load();
  }, [load]);

  const evidenceChanged = useCallback((fileIds: string[]) => {
    setKyc((current) => ({
      ...current,
      document_file_ids: fileIds,
      status: fileIds.length && current.status === "not_started" ? "documents_pending" : current.status,
    }));
  }, []);

  function profilePayload(): FinancialProfileUpdate {
    return {
      kyc,
      employment,
      income_sources: incomeSources,
      expenses,
      debts,
      bank_accounts: bankAccounts,
    };
  }

  async function saveCurrent(advance = false) {
    if (!currentBorrower || !user?.person) return;
    setWorking(true);
    try {
      if (step === 0) {
        await Promise.all([
          api.put<Person>(`/people/${user.person.id}`, person),
          api.put(`/borrowers/${currentBorrower.id}`, borrower),
        ]);
        await dispatch(fetchCurrentUser()).unwrap();
        await refreshAllData();
      } else if (step <= 4) {
        const saved = await originationApi.saveMyFinancialProfile(profilePayload());
        applyProfile(saved);
      }
      const events = await originationApi.getMyProfileActivity();
      setActivity(events);
      toast.success("Shared borrower profile saved", {
        description: "Concerned lenders now see the same assessment facts.",
      });
      if (advance) setStep((current) => Math.min(current + 1, steps.length - 1));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Could not save this profile step"));
    } finally {
      setWorking(false);
    }
  }

  const declaredIncome = Number(employment.net_salary || employment.gross_salary || 0)
    + incomeSources.reduce((sum, item) => sum + Number(item.declared_amount || 0), 0);
  const verifiedIncome = Number(employment.verified_net_income || 0)
    + incomeSources.filter((item) => item.is_verified).reduce((sum, item) => sum + Number(item.verified_amount || 0), 0);
  const totalExpenses = expenses.reduce((sum, item) => sum + Number(item.monthly_amount || 0), 0);
  const totalDebts = debts
    .filter((item) => !["settled", "written_off"].includes(item.status))
    .reduce((sum, item) => sum + Number(item.monthly_installment || 0), 0);
  const disposable = Math.max((verifiedIncome || declaredIncome) - totalExpenses - totalDebts, 0);
  const readinessChecks = [
    Boolean(person.first_name && person.last_name && person.physical_address),
    kyc.document_file_ids.length > 0,
    Boolean(employment.employment_status),
    declaredIncome > 0,
    expenses.length > 0,
    bankAccounts.length > 0,
    borrower.consent_to_share_profile,
  ];
  const readiness = Math.round((readinessChecks.filter(Boolean).length / readinessChecks.length) * 100);

  if (loading) return <PageLoader rows={10} />;

  return (
    <main className="loanhub-page space-y-5">
      <section className="loanhub-hero p-6 sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Shared borrower assessment</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight">My financial profile</h1>
            <p className="mt-2 text-sm text-muted-foreground">{fullName || profile?.identity.full_name || "Borrower"} · Step {step + 1} of {steps.length}</p>
          </div>
          <LoadingButton variant="outline" loading={working} loadingText="Saving…" onClick={() => void saveCurrent(false)}><Save className="h-4 w-4" />Save progress</LoadingButton>
        </div>
        <Progress value={((step + 1) / steps.length) * 100} className="mt-6" />
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-7">
          {steps.map((item, index) => {
            const Icon = item.icon;
            return <button key={item.label} type="button" onClick={() => setStep(index)} className={`flex min-h-14 items-center gap-2 rounded-2xl border px-3 py-3 text-left text-xs font-bold transition ${step === index ? "border-primary bg-primary text-primary-foreground shadow-sm" : "bg-card hover:border-primary/50"}`}><Icon className="h-4 w-4 shrink-0" />{item.label}</button>;
          })}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_330px]">
        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle>{steps[step].label}</CardTitle>
            <CardDescription>{step === 0 ? "Keep your system-wide identity and sharing choices accurate." : "These facts use the same assessment records that authorised lending companies review."}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {step === 0 ? <ApplicationStep person={person} onPersonChange={setPerson} borrower={borrower} onBorrowerChange={setBorrower} /> : null}
            {step === 1 ? <KycStep value={kyc} onChange={setKyc} borrowerId={currentBorrower?.id ?? ""} sharingEnabled={borrower.consent_to_share_documents} onEvidenceChange={evidenceChanged} /> : null}
            {step === 2 ? <EmploymentStep value={employment} onChange={setEmployment} incomes={incomeSources} onIncomesChange={setIncomeSources} /> : null}
            {step === 3 ? <ExpensesDebtStep expenses={expenses} onExpensesChange={setExpenses} debts={debts} onDebtsChange={setDebts} /> : null}
            {step === 4 ? <BankingStep values={bankAccounts} onChange={setBankAccounts} identityName={fullName} /> : null}
            {step === 5 ? <AffordabilityStep declaredIncome={declaredIncome} verifiedIncome={verifiedIncome} expenses={totalExpenses} debts={totalDebts} disposable={disposable} /> : null}
            {step === 6 ? <ReviewStep profile={profile} readiness={readiness} activity={activity} banks={bankAccounts.length} documents={kyc.document_file_ids.length} /> : null}

            <div className="flex flex-wrap justify-between gap-3 border-t pt-5">
              <Button type="button" variant="outline" disabled={step === 0 || working} onClick={() => setStep((current) => Math.max(current - 1, 0))}><ArrowLeft className="h-4 w-4" />Previous</Button>
              {step < steps.length - 1
                ? <LoadingButton type="button" loading={working} loadingText="Saving step…" onClick={() => void saveCurrent(true)}>Save and continue<ArrowRight className="h-4 w-4" /></LoadingButton>
                : <Button type="button" onClick={() => setStep(0)}><CheckCircle2 className="h-4 w-4" />Profile reviewed</Button>}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card className="rounded-3xl border-primary/20 bg-gradient-to-br from-primary/10 via-card to-emerald-500/10">
            <CardHeader><CardTitle className="flex items-center gap-2"><BadgeCheck className="h-5 w-5 text-primary" />Assessment health</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Health label="Identity captured" ok={readinessChecks[0]} />
              <Health label="Documents uploaded" ok={readinessChecks[1]} />
              <Health label="Employment captured" ok={readinessChecks[2]} />
              <Health label="Income declared" ok={readinessChecks[3]} />
              <Health label="Expenses captured" ok={readinessChecks[4]} />
              <Health label="Banking captured" ok={readinessChecks[5]} />
              <Health label="Sharing consent" ok={readinessChecks[6]} />
              <div className="pt-2"><div className="flex justify-between text-sm font-bold"><span>Readiness</span><span>{readiness}%</span></div><Progress value={readiness} className="mt-2" /></div>
            </CardContent>
          </Card>
          <Card className="rounded-3xl"><CardHeader><CardTitle>Financial snapshot</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><Line label="Declared income" value={formatMoney(declaredIncome)} /><Line label="Verified by lenders" value={formatMoney(verifiedIncome)} /><Line label="Household expenses" value={formatMoney(totalExpenses)} /><Line label="Debt instalments" value={formatMoney(totalDebts)} /><Line label="Available before new loan" value={formatMoney(disposable)} /></CardContent></Card>
          <div className="rounded-3xl border bg-card p-5 text-sm text-muted-foreground"><ShieldCheck className="mb-2 h-5 w-5 text-primary" /><strong className="text-foreground">Shared facts, private agreements.</strong><p className="mt-2">Your identity and assessment facts are system-wide. Each lender’s application decision, internal notes, contract and agreement remain private to that company.</p></div>
        </div>
      </div>
    </main>
  );
}

type PersonState = {
  first_name: string;
  middle_name: string;
  last_name: string;
  nationality: string;
  district: string;
  town_or_village: string;
  physical_address: string;
};

type BorrowerConsentState = typeof emptyBorrower;

function ApplicationStep({ person, onPersonChange, borrower, onBorrowerChange }: {
  person: PersonState;
  onPersonChange: (value: PersonState) => void;
  borrower: BorrowerConsentState;
  onBorrowerChange: (value: BorrowerConsentState) => void;
}) {
  const fields: Array<[keyof PersonState, string]> = [
    ["first_name", "First name"], ["middle_name", "Middle name"], ["last_name", "Last name"],
    ["nationality", "Nationality"], ["district", "District"], ["town_or_village", "Town or village"],
    ["physical_address", "Physical address"],
  ];
  return <div className="space-y-7">
    <div><h3 className="font-black">Personal and contact location</h3><div className="mt-4 grid gap-4 sm:grid-cols-2">{fields.map(([key, label]) => <Field key={key} label={label} className={key === "physical_address" ? "sm:col-span-2" : ""}><Input value={person[key]} onChange={(event) => onPersonChange({ ...person, [key]: event.target.value })} /></Field>)}</div></div>
    <div className="space-y-3"><h3 className="font-black">Privacy and lender consent</h3>
      <Consent label="Share my redacted assessment profile with concerned lending companies" checked={borrower.consent_to_share_profile} onChange={(value) => onBorrowerChange({ ...borrower, consent_to_share_profile: value })} />
      <Consent label="Share my uploaded evidence with concerned lending companies" checked={borrower.consent_to_share_documents} onChange={(value) => onBorrowerChange({ ...borrower, consent_to_share_documents: value })} />
      <Consent label="Allow permitted credit and affordability checks" checked={borrower.consent_to_credit_checks} onChange={(value) => onBorrowerChange({ ...borrower, consent_to_credit_checks: value })} />
    </div>
  </div>;
}

function KycStep({ value, onChange, borrowerId, sharingEnabled, onEvidenceChange }: {
  value: KYCProfileInput;
  onChange: (value: KYCProfileInput) => void;
  borrowerId: string;
  sharingEnabled: boolean;
  onEvidenceChange: (ids: string[]) => void;
}) {
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-muted/20 p-4"><div><p className="font-black">Lender verification status</p><p className="text-sm text-muted-foreground">Only an authorised lender can verify identity, sanctions and fraud checks.</p></div><Badge variant="outline">{titleCase(value.status)}</Badge></div>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="Source of funds"><Input value={value.source_of_funds ?? ""} onChange={(event) => onChange({ ...value, source_of_funds: event.target.value || null })} /></Field>
      <Field label="Residence status"><NativeSelect value={value.residence_status ?? ""} onChange={(event) => onChange({ ...value, residence_status: event.target.value || null })}><option value="">Select</option><option value="owner">Owner</option><option value="tenant">Tenant</option><option value="family">Living with family</option><option value="employer">Employer housing</option></NativeSelect></Field>
      <NumberField label="Years at address" value={value.years_at_address ?? 0} onChange={(years_at_address) => onChange({ ...value, years_at_address })} />
      <NumberField label="Dependants" value={value.dependants} step="1" onChange={(dependants) => onChange({ ...value, dependants })} />
    </div>
    <div className="grid gap-5 lg:grid-cols-2">
      <Contact title="Next of kin" value={value.next_of_kin} onChange={(next_of_kin) => onChange({ ...value, next_of_kin })} />
      <Contact title="Emergency contact" value={value.emergency_contact} onChange={(emergency_contact) => onChange({ ...value, emergency_contact })} />
    </div>
    {borrowerId ? <BorrowerEvaluationEvidence borrowerId={borrowerId} sharingEnabled={sharingEnabled} onEvidenceChange={onEvidenceChange} /> : null}
  </div>;
}

function EmploymentStep({ value, onChange, incomes, onIncomesChange }: {
  value: EmploymentProfileInput;
  onChange: (value: EmploymentProfileInput) => void;
  incomes: IncomeSourceInput[];
  onIncomesChange: (value: IncomeSourceInput[]) => void;
}) {
  return <div className="space-y-7">
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-muted/20 p-4"><div><p className="font-black">Employment verification</p><p className="text-sm text-muted-foreground">You declare facts; lenders verify them without changing your declaration.</p></div><Badge variant="outline">{titleCase(value.verification_status)}</Badge></div>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="Employment status"><NativeSelect value={value.employment_status} onChange={(event) => onChange({ ...value, employment_status: event.target.value })}><option value="employed">Employed</option><option value="self_employed">Self-employed</option><option value="pensioner">Pensioner</option><option value="student">Student</option><option value="unemployed">Unemployed</option></NativeSelect></Field>
      <Field label="Employer or business"><Input value={value.employer_name ?? ""} onChange={(event) => onChange({ ...value, employer_name: event.target.value || null })} /></Field>
      <Field label="Job title or trade"><Input value={value.job_title ?? ""} onChange={(event) => onChange({ ...value, job_title: event.target.value || null })} /></Field>
      <Field label="Employee number"><Input value={value.employee_number ?? ""} onChange={(event) => onChange({ ...value, employee_number: event.target.value || null })} /></Field>
      <Field label="Employer phone"><Input value={value.employer_phone ?? ""} onChange={(event) => onChange({ ...value, employer_phone: event.target.value || null })} /></Field>
      <Field label="Contract type"><Input value={value.contract_type ?? ""} onChange={(event) => onChange({ ...value, contract_type: event.target.value || null })} /></Field>
      <Field label="Employment start date"><Input type="date" value={value.employment_start_date ?? ""} onChange={(event) => onChange({ ...value, employment_start_date: event.target.value || null })} /></Field>
      <NumberField label="Gross monthly income" value={value.gross_salary} onChange={(gross_salary) => onChange({ ...value, gross_salary })} />
      <NumberField label="Net monthly income" value={value.net_salary} onChange={(net_salary) => onChange({ ...value, net_salary })} />
      <NumberField label="Salary day" value={value.salary_day ?? 0} step="1" onChange={(salary_day) => onChange({ ...value, salary_day })} />
      <Field label="Verified net income"><Input value={formatMoney(value.verified_net_income)} disabled /></Field>
      <Field label="Employer address" className="sm:col-span-2"><Input value={value.employer_address ?? ""} onChange={(event) => onChange({ ...value, employer_address: event.target.value || null })} /></Field>
    </div>
    <div>
      <ArrayHeader title="Additional income sources" action="Add income" onAdd={() => onIncomesChange([...incomes, emptyIncome()])} />
      <div className="mt-4 space-y-3">{incomes.map((item, index) => <div key={index} className="grid gap-3 rounded-2xl border p-4 sm:grid-cols-4"><Input value={item.description ?? ""} onChange={(event) => onIncomesChange(incomes.map((row, i) => i === index ? { ...row, description: event.target.value || null } : row))} placeholder="Income source" /><Input type="number" min="0" value={item.declared_amount} onChange={(event) => onIncomesChange(incomes.map((row, i) => i === index ? { ...row, declared_amount: Number(event.target.value) } : row))} placeholder="Monthly amount" /><NativeSelect value={item.frequency} onChange={(event) => onIncomesChange(incomes.map((row, i) => i === index ? { ...row, frequency: event.target.value } : row))}><option value="monthly">Monthly</option><option value="weekly">Weekly</option><option value="annual">Annual</option></NativeSelect><Button type="button" variant="ghost" onClick={() => onIncomesChange(incomes.filter((_, i) => i !== index))}><Trash2 className="h-4 w-4" />Remove</Button></div>)}</div>
    </div>
  </div>;
}

function ExpensesDebtStep({ expenses, onExpensesChange, debts, onDebtsChange }: {
  expenses: ExpenseInput[];
  onExpensesChange: (value: ExpenseInput[]) => void;
  debts: DebtObligationInput[];
  onDebtsChange: (value: DebtObligationInput[]) => void;
}) {
  const updateDebt = (index: number, patch: Partial<DebtObligationInput>) => {
    onDebtsChange(debts.map((row, i) => {
      if (i !== index) return row;
      const next = { ...row, ...patch };
      const factor = next.installment_frequency === "weekly" ? 52 / 12 : next.installment_frequency === "fortnightly" ? 26 / 12 : next.installment_frequency === "quarterly" ? 1 / 3 : 1;
      next.monthly_installment = Number((Number(next.installment_amount || 0) * factor).toFixed(2));
      return next;
    }));
  };
  return <div className="space-y-8">
    <div><ArrayHeader title="Monthly household expenses" action="Add expense" onAdd={() => onExpensesChange([...expenses, emptyExpense()])} /><div className="mt-4 space-y-3">{expenses.map((item, index) => <div key={index} className="grid gap-3 rounded-2xl border p-4 sm:grid-cols-4"><NativeSelect value={item.category} onChange={(event) => onExpensesChange(expenses.map((row, i) => i === index ? { ...row, category: event.target.value } : row))}><option value="food">Food</option><option value="housing">Housing</option><option value="transport">Transport</option><option value="utilities">Utilities</option><option value="education">Education</option><option value="medical">Medical</option><option value="other">Other</option></NativeSelect><Input value={item.description ?? ""} onChange={(event) => onExpensesChange(expenses.map((row, i) => i === index ? { ...row, description: event.target.value || null } : row))} placeholder="Description" /><Input type="number" min="0" value={item.monthly_amount} onChange={(event) => onExpensesChange(expenses.map((row, i) => i === index ? { ...row, monthly_amount: Number(event.target.value) } : row))} /><Button type="button" variant="ghost" onClick={() => onExpensesChange(expenses.filter((_, i) => i !== index))}><Trash2 className="h-4 w-4" />Remove</Button></div>)}</div></div>
    <div><ArrayHeader title="Existing debt obligations" action="Add debt" onAdd={() => onDebtsChange([...debts, emptyDebt()])} /><p className="mt-1 text-sm text-muted-foreground">Every concerned lender sees the same declared loan history. Lender agreements remain private.</p><div className="mt-4 space-y-4">{debts.map((item, index) => <div key={item.id ?? index} className="space-y-4 rounded-2xl border p-4"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Input value={item.creditor} onChange={(event) => updateDebt(index, { creditor: event.target.value })} placeholder="Creditor" /><Input type="number" min="0" value={item.current_balance} onChange={(event) => updateDebt(index, { current_balance: Number(event.target.value) })} placeholder="Outstanding balance" /><Input type="number" min="0" value={item.installment_amount} onChange={(event) => updateDebt(index, { installment_amount: Number(event.target.value) })} placeholder="Instalment amount" /><NativeSelect value={item.installment_frequency} onChange={(event) => updateDebt(index, { installment_frequency: event.target.value as DebtObligationInput["installment_frequency"] })}><option value="weekly">Weekly</option><option value="fortnightly">Fortnightly</option><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option></NativeSelect><Input type="date" value={item.next_due_date ?? ""} onChange={(event) => updateDebt(index, { next_due_date: event.target.value || null })} /><NativeSelect value={item.status} onChange={(event) => updateDebt(index, { status: event.target.value as DebtObligationInput["status"] })}><option value="active">Active</option><option value="restructured">Restructured</option><option value="settled">Settled</option><option value="defaulted">Defaulted</option><option value="unknown">Unknown</option></NativeSelect><Input value={formatMoney(item.monthly_installment)} disabled /><Button type="button" variant="ghost" onClick={() => item.id ? updateDebt(index, { status: "settled", current_balance: 0, remaining_installments: 0, remaining_term_months: 0, next_due_date: null }) : onDebtsChange(debts.filter((_, i) => i !== index))}><Trash2 className="h-4 w-4" />{item.id ? "Mark settled" : "Remove"}</Button></div><Textarea value={item.notes ?? ""} onChange={(event) => updateDebt(index, { notes: event.target.value || null })} placeholder="Debt notes" /></div>)}</div></div>
  </div>;
}

function BankingStep({ values, onChange, identityName }: {
  values: BankAccountInput[];
  onChange: (value: BankAccountInput[]) => void;
  identityName: string;
}) {
  return (
    <BankAccountsStep
      values={values}
      onChange={onChange}
      identityName={identityName}
      ownerLabel="My"
    />
  );
}

function AffordabilityStep({ declaredIncome, verifiedIncome, expenses, debts, disposable }: {
  declaredIncome: number;
  verifiedIncome: number;
  expenses: number;
  debts: number;
  disposable: number;
}) {
  return <div className="space-y-6"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Metric label="Declared monthly income" value={formatMoney(declaredIncome)} /><Metric label="Lender-verified income" value={formatMoney(verifiedIncome)} /><Metric label="Household expenses" value={formatMoney(expenses)} /><Metric label="Existing debt instalments" value={formatMoney(debts)} /><Metric label="Available before new loan" value={formatMoney(disposable)} /><Metric label="Debt-to-income" value={`${((debts / Math.max(verifiedIncome || declaredIncome, 1)) * 100).toFixed(1)}%`} /></div><div className="rounded-3xl border border-primary/20 bg-primary/5 p-5"><Calculator className="h-6 w-6 text-primary" /><h3 className="mt-3 font-black">A snapshot, not a loan decision</h3><p className="mt-2 text-sm text-muted-foreground">Each lending company applies its own policy to a specific application. Editing this profile cannot approve a loan or overwrite a lender’s affordability assessment.</p></div></div>;
}

function ReviewStep({ profile, readiness, activity, banks, documents }: {
  profile: FinancialProfile | null;
  readiness: number;
  activity: BorrowerProfileActivity[];
  banks: number;
  documents: number;
}) {
  return <div className="space-y-7"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Profile readiness" value={`${readiness}%`} /><Metric label="KYC status" value={titleCase(profile?.kyc?.status ?? "not started")} /><Metric label="Bank accounts" value={String(banks)} /><Metric label="Documents" value={String(documents)} /></div><div><h3 className="font-black">Who changed my profile</h3><p className="mt-1 text-sm text-muted-foreground">This record shows borrower and lender edits to shared assessment facts. Private agreements do not appear here.</p><div className="mt-4 space-y-3">{activity.length ? activity.map((event) => <div key={event.id} className="flex gap-3 rounded-2xl border p-4"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><Clock3 className="h-4 w-4" /></div><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="font-bold">{event.actor_name}</p><Badge variant="outline">{titleCase(event.actor_type)}</Badge>{event.company_name ? <Badge>{event.company_name}</Badge> : null}</div><p className="mt-1 text-sm text-muted-foreground">{event.changed_fields.length ? event.changed_fields.map((field) => titleCase(field)).join(", ") : titleCase(event.action)}</p><p className="mt-1 text-xs text-muted-foreground">{new Date(event.created_at).toLocaleString()}</p></div></div>) : <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">No shared-profile changes recorded yet.</div>}</div></div></div>;
}

function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return <label className={className}><span className="mb-2 block text-sm font-bold">{label}</span>{children}</label>;
}

function NumberField({ label, value, onChange, step = "0.01" }: { label: string; value: number; onChange: (value: number) => void; step?: string }) {
  return <Field label={label}><Input type="number" min="0" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /></Field>;
}

function Contact({ title, value, onChange }: { title: string; value: Record<string, string>; onChange: (value: Record<string, string>) => void }) {
  return <div className="rounded-2xl border p-4"><h3 className="font-black">{title}</h3><div className="mt-3 grid gap-3"><Input value={value.name ?? ""} onChange={(event) => onChange({ ...value, name: event.target.value })} placeholder="Full name" /><Input value={value.phone ?? ""} onChange={(event) => onChange({ ...value, phone: event.target.value })} placeholder="Phone" /><Input value={value.relationship ?? ""} onChange={(event) => onChange({ ...value, relationship: event.target.value })} placeholder="Relationship" /></div></div>;
}

function Consent({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex items-start gap-3 rounded-2xl border p-4"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-1 h-4 w-4 accent-primary" /><span className="text-sm font-bold">{label}</span></label>;
}

function ArrayHeader({ title, action, onAdd }: { title: string; action: string; onAdd: () => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-black">{title}</h3><Button type="button" variant="outline" onClick={onAdd}><Plus className="h-4 w-4" />{action}</Button></div>;
}

function Health({ label, ok }: { label: string; ok: boolean }) {
  return <div className="flex items-center justify-between rounded-2xl border bg-card/70 px-3 py-2"><span className="text-sm font-bold">{label}</span><Badge variant={ok ? "default" : "secondary"}>{ok ? "Ready" : "Pending"}</Badge></div>;
}

function Line({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-4 border-b pb-3 last:border-0"><span className="text-muted-foreground">{label}</span><span className="font-black">{value}</span></div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border bg-muted/20 p-4"><p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-2 text-xl font-black">{value}</p></div>;
}
