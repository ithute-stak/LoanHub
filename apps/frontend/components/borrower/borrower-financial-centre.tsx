"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Activity,
  BadgeDollarSign,
  Banknote,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  FileClock,
  Gauge,
  HandCoins,
  Landmark,
  ListChecks,
  Loader2,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
  WalletCards,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  cancelBorrowerServiceRequest,
  createBorrowerServiceRequest,
  getBorrowerApplications,
  getBorrowerEligibility,
  getBorrowerFinancialOverview,
  getBorrowerFinancialProfile,
  getBorrowerOfferComparison,
  getBorrowerRepaymentCalendar,
  getBorrowerSecurity,
  getBorrowerServiceRequests,
  getBorrowerTimeline,
  getPayoffEstimate,
  updateBorrowerConsents,
  type BorrowerApplicationTracker,
  type BorrowerEligibility,
  type BorrowerFinancialOverview,
  type BorrowerFinancialProfile,
  type BorrowerSecurity,
  type BorrowerServiceRequest,
  type BorrowerTimelineEvent,
  type OfferComparison,
  type PayoffEstimate,
  type RepaymentCalendarItem,
} from "@/api/borrowerCommand";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";


type CentreTab = "overview" | "applications" | "repayments" | "requests" | "timeline" | "security";

const TABS: Array<{ key: CentreTab; label: string; icon: typeof Gauge }> = [
  { key: "overview", label: "Overview", icon: Gauge },
  { key: "applications", label: "Applications & offers", icon: ListChecks },
  { key: "repayments", label: "Repayments", icon: CalendarDays },
  { key: "requests", label: "Requests", icon: FileClock },
  { key: "timeline", label: "Timeline", icon: Activity },
  { key: "security", label: "Trust & security", icon: ShieldCheck },
];

const REQUEST_TYPES = [
  ["settlement_quote", "Settlement quotation"],
  ["payment_arrangement", "Payment arrangement"],
  ["hardship", "Financial hardship assistance"],
  ["change_payment_date", "Change repayment date"],
  ["top_up", "Loan top-up"],
  ["refinance", "Refinance"],
  ["consolidation", "Debt consolidation"],
  ["early_repayment", "Early repayment"],
  ["statement", "Loan statement"],
  ["paid_up_letter", "Paid-up letter"],
  ["payment_allocation_dispute", "Payment allocation dispute"],
  ["balance_dispute", "Balance dispute"],
  ["update_payment_account", "Update payment account"],
] as const;

const LOAN_REQUIRED = new Set([
  "settlement_quote",
  "payment_arrangement",
  "hardship",
  "change_payment_date",
  "top_up",
  "early_repayment",
  "statement",
  "paid_up_letter",
  "payment_allocation_dispute",
  "balance_dispute",
  "update_payment_account",
]);

function errorMessage(error: unknown): string {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function statusClass(value: string): string {
  const normalized = value.toLowerCase();
  if (["active", "paid", "completed", "approved", "accepted", "appears_eligible", "strong", "good"].includes(normalized)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300";
  }
  if (["overdue", "defaulted", "declined", "rejected", "unlikely", "action needed"].includes(normalized)) {
    return "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300";
  }
  return "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300";
}

function Pill({ value, label }: { value: string; label?: string }) {
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-black ${statusClass(value)}`}>{label ?? titleCase(value)}</span>;
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="rounded-3xl border border-dashed p-8 text-center text-sm text-muted-foreground">{children}</div>;
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="rounded-3xl border bg-card p-5 shadow-sm">
      <p className="text-xs font-black uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-3 text-2xl font-black tracking-tight">{value}</p>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">{note}</p>
    </article>
  );
}

export function BorrowerFinancialCentre() {
  const searchParams = useSearchParams();
  const { loans } = useAppData();
  const [tab, setTab] = useState<CentreTab>("overview");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [overview, setOverview] = useState<BorrowerFinancialOverview | null>(null);
  const [profile, setProfile] = useState<BorrowerFinancialProfile | null>(null);
  const [applications, setApplications] = useState<BorrowerApplicationTracker[]>([]);
  const [calendar, setCalendar] = useState<RepaymentCalendarItem[]>([]);
  const [eligibility, setEligibility] = useState<BorrowerEligibility | null>(null);
  const [requests, setRequests] = useState<BorrowerServiceRequest[]>([]);
  const [timeline, setTimeline] = useState<BorrowerTimelineEvent[]>([]);
  const [security, setSecurity] = useState<BorrowerSecurity | null>(null);
  const [comparison, setComparison] = useState<OfferComparison | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState<string | null>(null);
  const [payoffLoanId, setPayoffLoanId] = useState("");
  const [extraPayment, setExtraPayment] = useState("0");
  const [payoff, setPayoff] = useState<PayoffEstimate | null>(null);
  const [payoffLoading, setPayoffLoading] = useState(false);
  const [requestType, setRequestType] = useState("settlement_quote");
  const [requestLoanId, setRequestLoanId] = useState("");
  const [requestCompanyId, setRequestCompanyId] = useState("");
  const [requestDetails, setRequestDetails] = useState("");
  const [requestValue, setRequestValue] = useState("");
  const [requestSubmitting, setRequestSubmitting] = useState(false);
  const [consentSaving, setConsentSaving] = useState(false);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    else setRefreshing(true);
    try {
      const [overviewData, profileData, applicationsData, calendarData, eligibilityData, requestsData, timelineData, securityData] = await Promise.all([
        getBorrowerFinancialOverview(),
        getBorrowerFinancialProfile(),
        getBorrowerApplications(),
        getBorrowerRepaymentCalendar(),
        getBorrowerEligibility(),
        getBorrowerServiceRequests(),
        getBorrowerTimeline(),
        getBorrowerSecurity(),
      ]);
      setOverview(overviewData);
      setProfile(profileData);
      setApplications(applicationsData);
      setCalendar(calendarData);
      setEligibility(eligibilityData);
      setRequests(requestsData);
      setTimeline(timelineData);
      setSecurity(securityData);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const requestedTab = searchParams.get("tab") as CentreTab | null;
    if (requestedTab && TABS.some((item) => item.key === requestedTab)) setTab(requestedTab);
  }, [searchParams]);

  useEffect(() => {
    if (!payoffLoanId && loans.length) {
      const firstActive = loans.find((loan) => ["active", "approved", "defaulted"].includes(loan.status));
      if (firstActive) setPayoffLoanId(firstActive.id);
    }
    if (!requestLoanId && loans.length) {
      const firstActive = loans.find((loan) => ["active", "approved", "defaulted"].includes(loan.status));
      if (firstActive) setRequestLoanId(firstActive.id);
    }
  }, [loans, payoffLoanId, requestLoanId]);

  const lenders = useMemo(() => {
    const map = new Map<string, string>();
    eligibility?.products.forEach((product) => map.set(product.company_id, product.company_name));
    return Array.from(map, ([id, name]) => ({ id, name }));
  }, [eligibility]);

  const activeLoans = useMemo(() => loans.filter((loan) => ["active", "approved", "defaulted"].includes(loan.status)), [loans]);

  async function compareOffers(requestId: string) {
    setComparisonLoading(requestId);
    try {
      setComparison(await getBorrowerOfferComparison(requestId));
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setComparisonLoading(null);
    }
  }

  async function calculatePayoff() {
    if (!payoffLoanId) return;
    setPayoffLoading(true);
    try {
      setPayoff(await getPayoffEstimate(payoffLoanId, Math.max(0, Number(extraPayment) || 0)));
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPayoffLoading(false);
    }
  }

  function prepareRequest(type: string, loanId?: string) {
    setRequestType(type);
    if (loanId) setRequestLoanId(loanId);
    setTab("requests");
  }

  async function submitServiceRequest(event: React.FormEvent) {
    event.preventDefault();
    const needsLoan = LOAN_REQUIRED.has(requestType);
    if (needsLoan && !requestLoanId) {
      toast.error("Select the loan this request relates to.");
      return;
    }
    if (!needsLoan && !requestLoanId && !requestCompanyId) {
      toast.error("Select a lender for this request.");
      return;
    }
    setRequestSubmitting(true);
    try {
      await createBorrowerServiceRequest({
        request_type: requestType,
        loan_id: requestLoanId || null,
        company_id: requestLoanId ? null : requestCompanyId || null,
        details: requestDetails.trim() || null,
        requested_value: requestValue ? Math.max(0, Number(requestValue)) : null,
      });
      toast.success("Your request was sent to the lender.");
      setRequestDetails("");
      setRequestValue("");
      await load(true);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setRequestSubmitting(false);
    }
  }

  async function cancelRequest(id: string) {
    try {
      await cancelBorrowerServiceRequest(id);
      toast.success("Request cancelled.");
      await load(true);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  async function setConsent(field: "consent_to_share_profile" | "consent_to_credit_checks", value: boolean) {
    setConsentSaving(true);
    try {
      await updateBorrowerConsents({ [field]: value });
      toast.success("Consent preference updated.");
      await load(true);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setConsentSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[50dvh] items-center justify-center rounded-3xl border bg-card">
        <div className="text-center"><Loader2 className="mx-auto h-7 w-7 animate-spin text-primary" /><p className="mt-3 text-sm font-bold">Building your financial view…</p></div>
      </div>
    );
  }

  const health = overview?.financial_health;
  const readiness = overview?.readiness;

  return (
    <div className="space-y-5 pb-10">
      <section className="relative overflow-hidden rounded-3xl border bg-card p-5 shadow-sm sm:p-7">
        <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1 text-xs font-black text-primary"><Sparkles className="h-3.5 w-3.5" /> Borrower Financial Command Centre</div>
            <h1 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">Understand and control your complete borrowing position</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Financial health, application progress, lender offers, repayment dates, settlement planning, servicing requests and profile-access transparency in one place.</p>
          </div>
          <button type="button" onClick={() => void load(true)} disabled={refreshing} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black transition hover:bg-muted disabled:opacity-60">
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} /> Refresh data
          </button>
        </div>
      </section>

      <nav className="flex gap-2 overflow-x-auto rounded-2xl border bg-card p-2 shadow-sm [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" aria-label="Financial centre sections">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} type="button" onClick={() => setTab(key)} className={`inline-flex min-h-11 shrink-0 items-center gap-2 rounded-xl px-3.5 text-sm font-black transition ${tab === key ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </nav>

      {tab === "overview" && health && readiness ? (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Monthly income" value={formatMoney(health.monthly_income)} note={`Includes ${formatMoney(health.additional_income)} recorded additional income`} />
            <Metric label="Monthly debt commitments" value={formatMoney(health.total_monthly_commitments)} note={`${formatMoney(health.loanhub_installments)} LoanHub + ${formatMoney(health.external_installments)} external`} />
            <Metric label="Total outstanding debt" value={formatMoney(health.total_outstanding_debt)} note={`${formatMoney(health.loanhub_balance)} LoanHub + ${formatMoney(health.external_debt_balance)} external`} />
            <Metric label="Estimated disposable income" value={formatMoney(health.estimated_disposable_income)} note={`After recorded living expenses and debt commitments · DTI ${health.debt_to_income_percent.toFixed(1)}%`} />
          </section>

          <section className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
            <article className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
              <div className="flex items-start justify-between gap-4">
                <div><p className="text-xs font-black uppercase tracking-[0.16em] text-muted-foreground">LoanHub readiness</p><p className="mt-2 text-4xl font-black">{readiness.score}<span className="text-base text-muted-foreground"> / 100</span></p></div>
                <Pill value={readiness.band} />
              </div>
              <p className="mt-3 text-xs leading-5 text-muted-foreground">Confidence: <strong className="text-foreground">{titleCase(readiness.confidence)}</strong>. {readiness.disclaimer}</p>
              <div className="mt-5 space-y-3">
                {readiness.components.map((component) => {
                  const percent = Math.min(100, Math.round((component.score / component.max) * 100));
                  return <div key={component.key}><div className="mb-1.5 flex justify-between gap-3 text-xs font-bold"><span>{component.label}</span><span>{component.score}/{component.max}</span></div><div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} /></div></div>;
                })}
              </div>
            </article>

            <article className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
              <div className="flex items-center gap-2"><Scale className="h-5 w-5 text-primary" /><h2 className="font-black">What is influencing readiness</h2></div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl bg-emerald-50 p-4 dark:bg-emerald-950/20"><p className="text-xs font-black uppercase tracking-wide text-emerald-700 dark:text-emerald-300">Helping</p><ul className="mt-2 space-y-2 text-sm">{readiness.helping.map((item) => <li key={item} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />{item}</li>)}{!readiness.helping.length && <li className="text-muted-foreground">More verified evidence will strengthen this section.</li>}</ul></div>
                <div className="rounded-2xl bg-amber-50 p-4 dark:bg-amber-950/20"><p className="text-xs font-black uppercase tracking-wide text-amber-800 dark:text-amber-300">Improve next</p><ul className="mt-2 space-y-2 text-sm">{readiness.actions.map((item) => <li key={item} className="flex gap-2"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />{item}</li>)}{!readiness.actions.length && <li>No immediate readiness actions are identified from current records.</li>}</ul></div>
              </div>
            </article>
          </section>

          {overview?.next_due ? (
            <section className="flex flex-col gap-4 rounded-3xl border border-primary/20 bg-primary/5 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div><p className="text-xs font-black uppercase tracking-[0.16em] text-primary">Next repayment</p><h2 className="mt-1 text-xl font-black">{formatMoney(overview.next_due.amount_due)} · {formatDate(overview.next_due.due_date)}</h2><p className="mt-1 text-sm text-muted-foreground">{overview.next_due.loan_reference} · {overview.next_due.lender ?? "Lender"}</p></div>
              <Link href="/borrower/payments" className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground"><Banknote className="h-4 w-4" /> Open payments</Link>
            </section>
          ) : null}

          <section className="grid gap-5 xl:grid-cols-2">
            <article className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
              <div className="flex items-center justify-between gap-3"><div><h2 className="font-black">Product eligibility guide</h2><p className="mt-1 text-xs text-muted-foreground">Calculated with lender rules and LoanHub’s configured interest engine.</p></div><BadgeDollarSign className="h-5 w-5 text-primary" /></div>
              <div className="mt-4 space-y-3">
                {eligibility?.products.slice(0, 6).map((product) => <div key={product.product_id} className="rounded-2xl border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-black">{product.product_name}</p><p className="text-xs text-muted-foreground">{product.company_name}</p></div><Pill value={product.status} /></div><div className="mt-3 grid grid-cols-2 gap-3 text-xs"><div><p className="text-muted-foreground">Estimate at minimum</p><p className="font-black">{formatMoney(product.estimated_for_amount)}</p></div><div><p className="text-muted-foreground">Estimated installment</p><p className="font-black">{formatMoney(product.estimated_monthly_installment)}</p></div><div><p className="text-muted-foreground">Estimated total</p><p className="font-black">{formatMoney(product.estimated_total_repayment)}</p></div><div><p className="text-muted-foreground">Projected DTI</p><p className="font-black">{product.estimated_projected_dti_percent.toFixed(1)}%</p></div></div>{product.reasons.length ? <ul className="mt-3 space-y-1 text-xs text-muted-foreground">{product.reasons.slice(0, 3).map((reason) => <li key={reason}>• {reason}</li>)}</ul> : null}</div>)}
                {!eligibility?.products.length && <EmptyState>No active lender products are available for an eligibility estimate right now.</EmptyState>}
              </div>
              {eligibility?.disclaimer ? <p className="mt-4 text-[11px] leading-5 text-muted-foreground">{eligibility.disclaimer}</p> : null}
            </article>

            <article className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
              <div className="flex items-center justify-between gap-3"><div><h2 className="font-black">External debt & financial profile</h2><p className="mt-1 text-xs text-muted-foreground">Existing credit recorded for affordability and future applications.</p></div><Landmark className="h-5 w-5 text-primary" /></div>
              <div className="mt-4 space-y-3">
                {profile?.external_debts.map((debt) => <div key={debt.id} className="rounded-2xl border p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-black">{debt.creditor}</p><p className="mt-1 text-xs text-muted-foreground">Started {formatDate(debt.started_on)} · {debt.account_reference || titleCase(debt.debt_type)}</p></div>{debt.is_verified ? <Pill value="approved" label="Verified" /> : <Pill value="pending" label="Declared" />}</div><div className="mt-3 grid grid-cols-2 gap-3 text-xs"><div><p className="text-muted-foreground">Balance</p><p className="font-black">{formatMoney(debt.current_balance)}</p></div><div><p className="text-muted-foreground">Monthly installment</p><p className="font-black">{formatMoney(debt.monthly_installment)}</p></div><div><p className="text-muted-foreground">Remaining installments</p><p className="font-black">{debt.remaining_installments ?? "—"}</p></div><div><p className="text-muted-foreground">Next due</p><p className="font-black">{formatDate(debt.next_due_date)}</p></div></div></div>)}
                {!profile?.external_debts.length && <EmptyState>No active external debt obligations are currently recorded.</EmptyState>}
              </div>
              <div className="mt-4 rounded-2xl bg-muted/50 p-4 text-xs"><p className="font-black">Employment evidence</p><p className="mt-1 text-muted-foreground">{String(profile?.employment.employer_name ?? "Employer not recorded")} · {titleCase(String(profile?.employment.verification_status ?? "unverified"))}</p><p className="mt-2 font-bold">Verified net income: {formatMoney(Number(profile?.employment.verified_net_income ?? 0))}</p></div>
            </article>
          </section>
        </div>
      ) : null}

      {tab === "applications" ? (
        <div className="space-y-5">
          <section className="rounded-3xl border bg-card p-5 shadow-sm"><h2 className="text-lg font-black">Application tracker</h2><p className="mt-1 text-sm text-muted-foreground">See exactly where each request is and whether anything needs your attention.</p></section>
          {applications.map((application) => (
            <article key={application.id} className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xl font-black">{formatMoney(application.requested_amount)}</p><p className="mt-1 text-xs text-muted-foreground">{application.loan_purpose || "General purpose"} · {application.preferred_term_months} months · {formatDate(application.created_at)}</p></div><Pill value={application.status} /></div>
              <div className="mt-5 grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
                {application.stages.map((stage, index) => <div key={stage.key} className={`rounded-2xl border p-3 ${stage.complete ? "border-primary/30 bg-primary/5" : "bg-muted/20"}`}><div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-black ${stage.complete ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>{stage.complete ? <CheckCircle2 className="h-4 w-4" /> : index + 1}</div><p className="mt-2 text-xs font-black leading-4">{stage.label}</p></div>)}
              </div>
              {application.action_required ? <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200"><strong>Action required:</strong> {application.action_required}</div> : <div className="mt-4 rounded-2xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950/20 dark:text-emerald-200">No borrower action is currently identified.</div>}
              <div className="mt-4 flex flex-wrap gap-2"><Link href="/borrower/requests" className="inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-xs font-black">Open request <ChevronRight className="h-3.5 w-3.5" /></Link>{application.offer_count > 0 ? <button type="button" onClick={() => void compareOffers(application.id)} className="inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-3 text-xs font-black text-primary-foreground">{comparisonLoading === application.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Scale className="h-3.5 w-3.5" />} Compare {application.offer_count} offer{application.offer_count === 1 ? "" : "s"}</button> : null}</div>
            </article>
          ))}
          {!applications.length && <EmptyState>You do not have any loan applications yet.</EmptyState>}

          {comparison ? <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6"><div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-lg font-black">Offer comparison</h2><p className="text-xs text-muted-foreground">Requested {formatMoney(comparison.request.requested_amount)} · {comparison.request.preferred_term_months} months</p></div><Link href="/borrower/requests" className="text-sm font-black text-primary">Choose from request page →</Link></div><div className="mt-4 grid gap-3 lg:grid-cols-3">{comparison.offers.map((offer) => <article key={offer.id} className={`rounded-2xl border p-4 ${offer.is_selected ? "border-primary bg-primary/5" : ""}`}><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-black">{offer.company_name}</p><p className="text-xs text-muted-foreground">{offer.term_months} months · {offer.interest_rate_percent}%</p></div><Pill value={offer.status} /></div><div className="mt-4 space-y-2 text-sm"><div className="flex justify-between gap-3"><span className="text-muted-foreground">Approved amount</span><strong>{formatMoney(offer.approved_amount)}</strong></div><div className="flex justify-between gap-3"><span className="text-muted-foreground">Monthly installment</span><strong>{formatMoney(offer.monthly_repayment)}</strong></div><div className="flex justify-between gap-3"><span className="text-muted-foreground">Fees</span><strong>{formatMoney(offer.processing_fee)}</strong></div><div className="flex justify-between gap-3 border-t pt-2"><span className="font-bold">Total repayment</span><strong>{formatMoney(offer.total_repayment)}</strong></div></div><div className="mt-3 flex flex-wrap gap-1.5">{offer.is_lowest_total ? <Pill value="approved" label="Lowest total cost" /> : null}{offer.is_lowest_installment ? <Pill value="pending" label="Lowest installment" /> : null}{offer.is_selected ? <Pill value="active" label="Selected" /> : null}</div></article>)}</div><p className="mt-4 text-xs text-muted-foreground">{comparison.guidance}</p></section> : null}
        </div>
      ) : null}

      {tab === "repayments" ? (
        <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
          <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6"><div className="flex items-center justify-between gap-3"><div><h2 className="text-lg font-black">Repayment calendar</h2><p className="mt-1 text-xs text-muted-foreground">Upcoming and overdue installments with scheduled principal, interest and fees.</p></div><Link href="/borrower/payments" className="text-sm font-black text-primary">Payments →</Link></div><div className="mt-4 space-y-3">{calendar.slice(0, 24).map((item) => <article key={item.id} className="rounded-2xl border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-black">{item.loan_reference} · installment {item.installment_number}</p><p className="mt-1 text-xs text-muted-foreground">{item.lender} · due {formatDate(item.due_date)}</p></div><Pill value={item.status} /></div><div className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-5"><div><p className="text-muted-foreground">Principal</p><p className="font-black">{formatMoney(item.principal_due)}</p></div><div><p className="text-muted-foreground">Interest</p><p className="font-black">{formatMoney(item.interest_due)}</p></div><div><p className="text-muted-foreground">Fees</p><p className="font-black">{formatMoney(item.fee_due)}</p></div><div><p className="text-muted-foreground">Paid</p><p className="font-black">{formatMoney(item.paid_amount)}</p></div><div><p className="text-muted-foreground">Remaining</p><p className="font-black">{formatMoney(item.remaining_due)}</p></div></div></article>)}{!calendar.length && <EmptyState>No unpaid installments are currently scheduled.</EmptyState>}</div></section>

          <section className="space-y-5">
            <article className="rounded-3xl border bg-card p-5 shadow-sm"><div className="flex items-center gap-2"><WalletCards className="h-5 w-5 text-primary" /><h2 className="font-black">Payoff simulator</h2></div><p className="mt-1 text-xs leading-5 text-muted-foreground">Plan an extra payment. This does not replace an official lender settlement quotation.</p><label className="mt-4 block text-xs font-black">Loan<select value={payoffLoanId} onChange={(event) => { setPayoffLoanId(event.target.value); setPayoff(null); }} className="mt-1.5 h-11 w-full rounded-xl border bg-background px-3 text-sm">{activeLoans.map((loan) => <option key={loan.id} value={loan.id}>{loan.loan_reference} · {formatMoney(loan.balance)}</option>)}</select></label><label className="mt-3 block text-xs font-black">Extra payment<input type="number" min="0" step="0.01" value={extraPayment} onChange={(event) => setExtraPayment(event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border bg-background px-3 text-sm" /></label><button type="button" disabled={!payoffLoanId || payoffLoading} onClick={() => void calculatePayoff()} className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50">{payoffLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gauge className="h-4 w-4" />} Calculate plan</button>{payoff ? <div className="mt-4 rounded-2xl bg-muted/50 p-4 text-sm"><div className="flex justify-between gap-3"><span>Current balance</span><strong>{formatMoney(payoff.current_balance)}</strong></div><div className="mt-2 flex justify-between gap-3"><span>After extra payment</span><strong>{formatMoney(payoff.estimated_balance_after_extra)}</strong></div><div className="mt-2 flex justify-between gap-3"><span>Estimated installments left</span><strong>{payoff.estimated_installments_remaining}</strong></div><p className="mt-3 text-[11px] leading-5 text-muted-foreground">{payoff.disclaimer}</p><button type="button" onClick={() => prepareRequest("settlement_quote", payoff.loan_id)} className="mt-3 inline-flex h-10 w-full items-center justify-center rounded-xl border bg-background px-3 text-xs font-black">Request official settlement</button></div> : null}</article>
            <article className="rounded-3xl border bg-card p-5 shadow-sm"><h2 className="font-black">Need breathing room?</h2><p className="mt-1 text-xs leading-5 text-muted-foreground">Do not wait for a missed payment. Send a structured request to your lender.</p><div className="mt-3 grid gap-2"><button onClick={() => prepareRequest("payment_arrangement", payoffLoanId)} type="button" className="h-10 rounded-xl border text-xs font-black">Request payment arrangement</button><button onClick={() => prepareRequest("hardship", payoffLoanId)} type="button" className="h-10 rounded-xl border text-xs font-black">Report financial hardship</button><button onClick={() => prepareRequest("change_payment_date", payoffLoanId)} type="button" className="h-10 rounded-xl border text-xs font-black">Request due-date change</button></div></article>
          </section>
        </div>
      ) : null}

      {tab === "requests" ? (
        <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
          <section className="space-y-5">
            <article className="rounded-3xl border bg-card p-5 shadow-sm"><h2 className="text-lg font-black">Borrower self-service</h2><p className="mt-1 text-xs leading-5 text-muted-foreground">Send a formal, trackable request directly to the lender responsible for the loan.</p><div className="mt-4 grid grid-cols-2 gap-2">{REQUEST_TYPES.slice(0, 8).map(([value, label]) => <button key={value} type="button" onClick={() => setRequestType(value)} className={`min-h-11 rounded-xl border px-2 text-xs font-black ${requestType === value ? "border-primary bg-primary/5 text-primary" : ""}`}>{label}</button>)}</div></article>
            <form onSubmit={submitServiceRequest} className="rounded-3xl border bg-card p-5 shadow-sm"><label className="block text-xs font-black">Request type<select value={requestType} onChange={(event) => setRequestType(event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border bg-background px-3 text-sm">{REQUEST_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="mt-3 block text-xs font-black">Related LoanHub loan<select value={requestLoanId} onChange={(event) => setRequestLoanId(event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border bg-background px-3 text-sm"><option value="">No specific loan</option>{loans.map((loan) => <option key={loan.id} value={loan.id}>{loan.loan_reference} · {formatMoney(loan.balance)}</option>)}</select></label>{!requestLoanId ? <label className="mt-3 block text-xs font-black">Lender<select value={requestCompanyId} onChange={(event) => setRequestCompanyId(event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border bg-background px-3 text-sm"><option value="">Select lender</option>{lenders.map((lender) => <option key={lender.id} value={lender.id}>{lender.name}</option>)}</select></label> : null}<label className="mt-3 block text-xs font-black">Amount/value (optional)<input value={requestValue} onChange={(event) => setRequestValue(event.target.value)} type="number" min="0" step="0.01" className="mt-1.5 h-11 w-full rounded-xl border bg-background px-3 text-sm" placeholder="e.g. proposed installment or extra payment" /></label><label className="mt-3 block text-xs font-black">Details<textarea value={requestDetails} onChange={(event) => setRequestDetails(event.target.value)} rows={5} maxLength={4000} className="mt-1.5 w-full rounded-xl border bg-background p-3 text-sm" placeholder="Explain what you are requesting and anything the lender should consider." /></label><button type="submit" disabled={requestSubmitting} className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50">{requestSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileClock className="h-4 w-4" />} Send to lender</button></form>
          </section>
          <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6"><div><h2 className="text-lg font-black">Your request history</h2><p className="mt-1 text-xs text-muted-foreground">Responses remain attached to the formal request for future reference.</p></div><div className="mt-4 space-y-3">{requests.map((request) => <article key={request.id} className="rounded-2xl border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-black">{request.request_type_label}</p><p className="mt-1 text-xs text-muted-foreground">{request.company_name}{request.loan_reference ? ` · ${request.loan_reference}` : ""} · {formatDateTime(request.created_at)}</p></div><Pill value={request.status} /></div>{request.details ? <p className="mt-3 text-sm leading-6">{request.details}</p> : null}{request.company_response ? <div className="mt-3 rounded-xl bg-primary/5 p-3 text-sm"><p className="text-xs font-black uppercase tracking-wide text-primary">Lender response</p><p className="mt-1 leading-6">{request.company_response}</p></div> : null}{["submitted", "under_review"].includes(request.status) ? <button type="button" onClick={() => void cancelRequest(request.id)} className="mt-3 text-xs font-black text-red-600">Cancel request</button> : null}</article>)}{!requests.length && <EmptyState>You have not submitted any lender service requests yet.</EmptyState>}</div></section>
        </div>
      ) : null}

      {tab === "timeline" ? (
        <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6"><h2 className="text-lg font-black">Borrower life timeline</h2><p className="mt-1 text-xs text-muted-foreground">Applications, offers, loans, payments and lender service responses in one chronology.</p><div className="mt-5 space-y-1">{timeline.map((event, index) => <div key={`${event.type}-${event.at}-${index}`} className="relative flex gap-4 pb-5"><div className="relative z-10 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-background"><Activity className="h-3.5 w-3.5 text-primary" /></div>{index < timeline.length - 1 ? <div className="absolute bottom-0 left-4 top-8 w-px bg-border" /> : null}<div className="min-w-0 flex-1 rounded-2xl border p-4"><div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"><p className="font-black">{event.title}</p><p className="text-xs text-muted-foreground">{formatDateTime(event.at)}</p></div><p className="mt-1 text-sm text-muted-foreground">{event.description}</p><Link href={event.href} className="mt-2 inline-flex items-center gap-1 text-xs font-black text-primary">Open <ChevronRight className="h-3 w-3" /></Link></div></div>)}{!timeline.length && <EmptyState>Your activity timeline will appear here as you use LoanHub.</EmptyState>}</div></section>
      ) : null}

      {tab === "security" ? (
        <div className="space-y-5">
          <section className="grid gap-4 sm:grid-cols-3"><Metric label="Active sessions" value={String(security?.active_sessions ?? 0)} note="Currently valid LoanHub login sessions" /><Metric label="Account verification" value={security?.account_verified ? "Verified" : "Needs verification"} note={`Last seen ${formatDateTime(security?.last_seen_at ?? null)}`} /><Metric label="Profile access records" value={String(security?.profile_access.length ?? 0)} note="Lenders that unlocked a marketplace request profile" /></section>
          <section className="grid gap-5 xl:grid-cols-2">
            <article className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6"><div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /><h2 className="font-black">Consent centre</h2></div><p className="mt-1 text-xs leading-5 text-muted-foreground">You control optional profile sharing and credit-assessment permission. Turning these off can prevent lenders from assessing new requests.</p><div className="mt-4 space-y-3"><div className="flex items-center justify-between gap-4 rounded-2xl border p-4"><div><p className="text-sm font-black">Share profile with approved lenders</p><p className="mt-1 text-xs text-muted-foreground">Used for lender assessment when you broadcast a request.</p></div><button type="button" disabled={consentSaving} onClick={() => void setConsent("consent_to_share_profile", !(security?.consents.share_profile ?? false))} className={`min-w-20 rounded-full border px-3 py-2 text-xs font-black ${security?.consents.share_profile ? "bg-primary text-primary-foreground" : "bg-background"}`}>{security?.consents.share_profile ? "On" : "Off"}</button></div><div className="flex items-center justify-between gap-4 rounded-2xl border p-4"><div><p className="text-sm font-black">Allow credit checks</p><p className="mt-1 text-xs text-muted-foreground">Lets authorised lender workflows perform permitted credit assessment.</p></div><button type="button" disabled={consentSaving} onClick={() => void setConsent("consent_to_credit_checks", !(security?.consents.credit_checks ?? false))} className={`min-w-20 rounded-full border px-3 py-2 text-xs font-black ${security?.consents.credit_checks ? "bg-primary text-primary-foreground" : "bg-background"}`}>{security?.consents.credit_checks ? "On" : "Off"}</button></div></div><div className="mt-4 grid gap-2 sm:grid-cols-2"><Link href="/borrower/account" className="inline-flex h-11 items-center justify-center rounded-xl border text-sm font-black">Manage sessions & password</Link><Link href="/borrower/profile" className="inline-flex h-11 items-center justify-center rounded-xl border text-sm font-black">Review borrower profile</Link></div></article>
            <article className="rounded-3xl border bg-card p-5 shadow-sm sm:p-6"><h2 className="font-black">Who accessed marketplace profile data</h2><p className="mt-1 text-xs text-muted-foreground">These records come from LoanHub marketplace unlocks for your own loan requests.</p><div className="mt-4 space-y-3">{security?.profile_access.map((access) => <div key={`${access.company_id}-${access.loan_request_id}`} className="rounded-2xl border p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-black">{access.company_name}</p><p className="mt-1 text-xs text-muted-foreground">{access.purpose}</p></div><ShieldCheck className="h-4 w-4 text-primary" /></div><p className="mt-2 text-xs">Accessed: <strong>{formatDateTime(access.unlocked_at)}</strong></p>{access.expires_at ? <p className="mt-1 text-xs text-muted-foreground">Access expires: {formatDateTime(access.expires_at)}</p> : null}</div>)}{!security?.profile_access.length && <EmptyState>No lender marketplace profile-access records are available yet.</EmptyState>}</div></article>
          </section>
          <section className="rounded-3xl border bg-card p-5 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-black">Masked payment accounts</h2><p className="mt-1 text-xs text-muted-foreground">LoanHub never exposes stored encrypted account numbers here.</p></div><Link href="/borrower/profile" className="text-xs font-black text-primary">Manage profile →</Link></div><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{profile?.bank_accounts.map((account) => <div key={account.id} className="rounded-2xl border p-4"><div className="flex items-center gap-2"><Landmark className="h-4 w-4 text-primary" /><p className="font-black">{account.bank_name}</p></div><p className="mt-2 text-sm">•••• {account.account_last4}</p><p className="mt-1 text-xs text-muted-foreground">{titleCase(account.account_type)} · {titleCase(account.verification_status)}</p></div>)}{!profile?.bank_accounts.length && <EmptyState>No bank account summary is currently available.</EmptyState>}</div></section>
        </div>
      ) : null}
    </div>
  );
}
