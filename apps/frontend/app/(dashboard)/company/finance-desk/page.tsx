"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { ArrowDownLeft, ArrowUpRight, BookOpen, CalendarDays, HandCoins, ReceiptText, RefreshCcw, Wallet } from "lucide-react";
import { listJournalEntries } from "@/api/accounting";
import { branchApi } from "@/api/branch";
import { useTenant } from "@/provider/tenantProvider";
import { PlusCircle } from "lucide-react";
import type { Branch } from "@/types/branch";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { JournalEntry } from "@/types/accounting";
import { toast } from "@/utils/toast";
import { getErrorMessage } from "@/utils/apiError";

type CashSession = {
  id: string; status: "open" | "closed"; business_date: string; branch_id: string | null;
  counted_opening: string; cash_movement: string; expected_closing: string;
  counted_closing: string | null; variance: string | null;
  float_topups: Array<{amount: string; source: string; reference: string; reason: string; recorded_at: string}>;
  coverage_note: string;
};
type LegacyReceipt = {id: string; receipt_reference: string; description: string; amount: string; entry_date: string; status: string};
type FinanceSummary = {amount: string; count: number};
type FinanceReport = {disbursements: FinanceSummary; repayments: FinanceSummary; expenses: FinanceSummary; legacy_folio_receipts: FinanceSummary; basis: string};
type Period = "day" | "week" | "month" | "year";
const CATEGORIES = ["Airtime", "Water", "Electricity", "Transport", "Stationery", "Rent", "Maintenance", "Other"];
function localDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function periodStart(period: Period, today: Date) {
  const first = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (period === "week") first.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  if (period === "month") first.setDate(1);
  if (period === "year") { first.setMonth(0); first.setDate(1); }
  return localDate(first);
}
export default function FinanceDeskPage() {
  const {activeCompanyId, activeBranchId, activeRole} = useTenant();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchSelection, setBranchSelection] = useState("");
  const selectedBranchId = branchSelection || activeBranchId || null;
  useEffect(() => { if (!activeCompanyId) return; void branchApi.getByCompany(activeCompanyId).then(res => setBranches(res.data.filter(row => row.is_active))).catch(() => setBranches([])); }, [activeCompanyId]);
  const [period, setPeriod] = useState<Period>("day");
  const [activeTab, setActiveTab] = useState("cash");
  const [asOf, setAsOf] = useState(() => localDate(new Date()));
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [cashSession, setCashSession] = useState<CashSession | null>(null);
  const [opening, setOpening] = useState("");
  const [closing, setClosing] = useState("");
  const [cashNote, setCashNote] = useState("");
  const [cashBusy, setCashBusy] = useState(false);
  const [floatAmount, setFloatAmount] = useState("");
  const [floatSource, setFloatSource] = useState("owner_float");
  const [floatReason, setFloatReason] = useState("");
  const [floatReference, setFloatReference] = useState("");
  const [floatBusy, setFloatBusy] = useState(false);
  const [report, setReport] = useState<FinanceReport | null>(null);
  const [legacyReceipts, setLegacyReceipts] = useState<LegacyReceipt[]>([]);
  const [folio, setFolio] = useState("");
  const [legacyClient, setLegacyClient] = useState("");
  const [legacyAmount, setLegacyAmount] = useState("");
  const [legacyReference, setLegacyReference] = useState("");
  const [legacyChannel, setLegacyChannel] = useState<"cash" | "bank" | "electronic">("cash");
  const [legacySaving, setLegacySaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [category, setCategory] = useState("Airtime");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const rangeStart = useMemo(() => {
    const [year, month, day] = asOf.split("-").map(Number);
    return periodStart(period, new Date(year, month - 1, day));
  }, [period, asOf]);
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [journal, session, receipts, financeReport] = await Promise.all([
        listJournalEntries({ fromDate: rangeStart, toDate: asOf, branchId: selectedBranchId, limit: 500 }),
        api.get<CashSession | null>("/accounting/daily-cash", {params: {business_date: localDate(new Date()), branch_id: selectedBranchId || undefined}}).then(res => res.data),
        api.get<LegacyReceipt[]>("/accounting/legacy-folio-receipts", {params: {from_date: rangeStart, to_date: asOf, branch_id: selectedBranchId || undefined}}).then(res => res.data),
        api.get<FinanceReport>("/accounting/daily-finance/report", {params: {from_date: rangeStart, to_date: asOf, branch_id: selectedBranchId || undefined}}).then(res => res.data),
      ]);
      setEntries(journal);
      setReport(financeReport);
      setCashSession(session);
      setLegacyReceipts(receipts);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Could not load daily finance activity"));
    } finally {
      setLoading(false);
    }
  }, [rangeStart, asOf, selectedBranchId]);
  useEffect(() => { void reload(); }, [reload]);

  const expenses = useMemo(() => entries.filter(e => e.reference_type === "expense" && e.status === "posted"), [entries]);
  const expenseTotal = Number(report?.expenses.amount ?? 0);
  const issuedTotal = Number(report?.disbursements.amount ?? 0);
  const repaidTotal = Number(report?.repayments.amount ?? 0);
  async function submitCashSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const count = Number(cashSession ? closing : opening);
    if (!Number.isFinite(count) || count < 0) { toast.error("Enter a valid nonnegative cash count."); return; }
    if (cashSession && cashNote.trim().length < 5) { toast.error("Enter a closing confirmation note."); return; }
    setCashBusy(true);
    try {
      if (cashSession) {
        if (cashSession.status !== "open") return;
        await api.post(`/accounting/daily-cash/${cashSession.id}/close`, { counted_closing: count, note: cashNote.trim() });
        toast.success("Daily closing count confirmed");
      } else {
        await api.post("/accounting/daily-cash/open", { business_date: localDate(new Date()), branch_id: selectedBranchId, counted_opening: count, note: cashNote.trim() || null });
        toast.success("Daily opening cash recorded");
      }
      setOpening(""); setClosing(""); setCashNote("");
      await reload();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Could not save cash session"));
    } finally { setCashBusy(false); }
  }
  async function addCashFloat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!cashSession || cashSession.status !== "open") return;
    const value = Number(floatAmount);
    if (!Number.isFinite(value) || value <= 0) { toast.error("Enter a positive float amount."); return; }
    setFloatBusy(true);
    try {
      await api.post(`/accounting/daily-cash/${cashSession.id}/top-up`, {
        amount: value, source: floatSource, reference: floatReference.trim(),
        reason: floatReason.trim(),
      });
      toast.success("Cash float added and recorded in the ledger");
      setFloatAmount(""); setFloatReason(""); setFloatReference("");
      await reload();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Could not add cash float"));
    } finally { setFloatBusy(false); }
  }
  async function saveLegacyReceipt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = Number(legacyAmount);
    if (!Number.isFinite(parsed) || parsed <= 0) { toast.error("Enter a valid legacy payment amount."); return; }
    setLegacySaving(true);
    try {
      await api.post("/accounting/legacy-folio-receipts", {
        folio_number: folio.trim(), client_name: legacyClient.trim(),
        amount: parsed, payment_channel: legacyChannel, receipt_reference: legacyReference.trim(), branch_id: selectedBranchId,
      });
      toast.success("Legacy folio payment recorded for reconciliation");
      setFolio(""); setLegacyClient(""); setLegacyAmount(""); setLegacyReference("");
      await reload();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Could not record legacy folio receipt"));
    } finally { setLegacySaving(false); }
  }
  async function saveExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) { toast.error("Enter a valid positive expense amount."); return; }
    setSaving(true);
    try {
      await api.post("/accounting/expenses", {
        amount: parsed,
        description: `${category}: ${description.trim()}`,
        expense_account_code: "6500",
        branch_id: selectedBranchId,
        paid_now: true,
        entry_date: localDate(new Date()),
        external_reference: reference.trim() || undefined,
      });
      toast.success("Expense posted to accounting");
      setAmount(""); setDescription(""); setReference("");
      await reload();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Expense could not be recorded"));
    } finally { setSaving(false); }
  }
  return <div className="mx-auto w-full max-w-[1600px] space-y-6 pb-10">
    <div className="rounded-2xl border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-widest text-primary">Payments & Finance</p><h1 className="mt-1 text-2xl font-extrabold tracking-tight sm:text-3xl">Daily Finance Desk</h1><p className="mt-2 text-sm text-muted-foreground">A focused workspace for daily cash control, expenses, borrower collections and financial reporting.</p></div>
        <Button variant="outline" onClick={() => void reload()} disabled={loading}><RefreshCcw className="mr-2 h-4 w-4"/>Refresh</Button>
      </div>
      <div className="mt-4 flex flex-wrap items-end gap-3 border-t pt-4">
        {branches.length ? <div className="space-y-1"><Label htmlFor="finance-branch">Branch</Label><select id="finance-branch" className="h-11 w-full min-w-48 rounded-xl border bg-background px-3 text-sm" value={selectedBranchId ?? ""} onChange={e => setBranchSelection(e.target.value)}><option value="">All-company / unassigned cash</option>{branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></div> : null}
        <div className="space-y-1"><Label htmlFor="finance-date">Through date</Label><Input className="h-11" id="finance-date" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} max={localDate(new Date())}/></div>
        <div className="flex flex-wrap gap-1 rounded-xl border p-1">{(["day","week","month","year"] as Period[]).map(p => <Button key={p} type="button" size="sm" variant={period === p ? "default" : "ghost"} onClick={() => setPeriod(p)}>{({day:"Day",week:"Week",month:"Month",year:"Year"})[p]}</Button>)}</div>
        <p className="w-full text-xs font-medium text-muted-foreground">Showing {rangeStart} to {asOf} · totals include all matching transactions</p>
      </div>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric icon={<HandCoins className="h-5 w-5"/>} title="Money issued to clients" amount={issuedTotal} hint={`${report?.disbursements.count ?? 0} successful disbursements`}/>
      <Metric icon={<ReceiptText className="h-5 w-5"/>} title="Recorded expenses" amount={expenseTotal} hint={`${report?.expenses.count ?? 0} posted expenses`}/>
      <Metric icon={<ArrowDownLeft className="h-5 w-5"/>} title="Client repayments" amount={repaidTotal} hint={`${report?.repayments.count ?? 0} successful loan repayments`}/>
      <Metric icon={<Wallet className="h-5 w-5"/>} title="Expected closing cash" amount={cashSession ? Number(cashSession.expected_closing) : null} hint={cashSession ? (cashSession.status === "closed" ? "Closed — see confirmed count below" : "Posted cash movements since opening only") : "Open today’s cash session to begin"}/>
    </div>
    <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-lg font-bold tracking-tight">Daily operations</h2><p className="text-xs text-muted-foreground">Choose a task below; your reports and balances stay visible above.</p></div><span className="rounded-full border bg-muted/30 px-3 py-1 text-xs font-semibold text-muted-foreground">{cashSession?.status === "closed" ? "Cash day closed" : cashSession?.status === "open" ? "Cash day open" : "Cash day not opened"}</span></div>
      <TabsList className="grid h-auto w-full grid-cols-2 gap-1 rounded-xl bg-muted/50 p-1.5 md:grid-cols-5">
        <TabsTrigger value="cash" className="min-h-11 w-full rounded-lg px-2 text-xs font-semibold sm:px-4 sm:text-sm"><Wallet className="mr-2 h-4 w-4"/>Cash day</TabsTrigger>
        <TabsTrigger value="expenses" className="min-h-10 flex-1 rounded-xl px-4 sm:flex-none"><ReceiptText className="mr-2 h-4 w-4"/>Expenses</TabsTrigger>
        <TabsTrigger value="payments" className="min-h-10 flex-1 rounded-xl px-4 sm:flex-none"><ArrowDownLeft className="mr-2 h-4 w-4"/>Payments</TabsTrigger>
        <TabsTrigger value="legacy" className="min-h-11 w-full rounded-lg px-2 text-xs font-semibold sm:px-4 sm:text-sm"><BookOpen className="mr-2 h-4 w-4"/>Legacy folio</TabsTrigger>
        <TabsTrigger value="reports" className="min-h-10 flex-1 rounded-xl px-4 sm:flex-none"><HandCoins className="mr-2 h-4 w-4"/>Reports & links</TabsTrigger>
      </TabsList>
      <TabsContent value="cash" className="space-y-4">
        <Card className="rounded-2xl"><CardHeader><CardTitle>Daily cash opening & closing</CardTitle><p className="text-sm text-muted-foreground">A counted, auditable cash session is separate from the accounting journal. Only posted cash-ledger movements are included in the expected figure.</p></CardHeader><CardContent className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
      <div className="space-y-3 rounded-xl bg-muted/30 p-4">
        <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Today&apos;s cash session</p>
        <p className="text-xl font-bold">{cashSession ? (cashSession.status === "closed" ? "Closed" : "Open") : "Not opened yet"}</p>
        {cashSession ? <>
          <div className="flex justify-between text-sm"><span>Opening count</span><strong>{formatMoney(Number(cashSession.counted_opening))}</strong></div>
          <div className="flex justify-between text-sm"><span>Posted net cash movement</span><strong>{formatMoney(Number(cashSession.cash_movement))}</strong></div>
          <div className="flex justify-between border-t pt-2 text-sm"><span>Expected cash</span><strong>{formatMoney(Number(cashSession.expected_closing))}</strong></div>
          {cashSession.counted_closing !== null ? <><div className="flex justify-between text-sm"><span>Physical closing count</span><strong>{formatMoney(Number(cashSession.counted_closing))}</strong></div><div className="flex justify-between text-sm"><span>Variance</span><strong>{formatMoney(Number(cashSession.variance))}</strong></div></> : null}
        </> : null}
        <p className="text-xs text-muted-foreground">{cashSession?.coverage_note ?? "One session is allowed for the current branch and business date."}</p>
      </div>
      <form onSubmit={submitCashSession} className="space-y-3">
        {cashSession?.status === "closed" ? <p className="rounded-xl border p-4 text-sm">This cash session is closed. A new opening count can be entered on the next business day. Any missing cash movements require separate accounting reconciliation.</p> : <>
          <Label htmlFor="cash-count">{cashSession ? "Physical closing cash counted (LSL)" : "Physical opening cash counted (LSL)"}</Label>
          <Input id="cash-count" type="number" min="0" step="0.01" required value={cashSession ? closing : opening} onChange={e => cashSession ? setClosing(e.target.value) : setOpening(e.target.value)} placeholder="0.00"/>
          <Label htmlFor="cash-note">{cashSession ? "Closing explanation / confirmation" : "Opening note (optional)"}</Label>
          <Textarea id="cash-note" minLength={cashSession ? 5 : undefined} required={Boolean(cashSession)} value={cashNote} onChange={e => setCashNote(e.target.value)} placeholder={cashSession ? "Confirm physical count and explain any difference" : "Cash counted at opening"}/>
          <Button disabled={cashBusy || loading || (branches.length > 0 && !selectedBranchId)} type="submit" className="w-full">{cashBusy ? "Saving..." : cashSession ? "Confirm & close cash day" : "Record opening cash"}</Button>
        </>}
      </form>
    </CardContent></Card>
        {cashSession?.status === "open" && (activeRole === "company_owner" || activeRole === "branch_manager") ? (
          <Card className="rounded-2xl border-primary/20 shadow-sm">
            <CardHeader><CardTitle className="flex items-center gap-2"><PlusCircle className="h-5 w-5 text-primary"/> Top up opening cash</CardTitle>
              <p className="text-sm text-muted-foreground">Add physical cash to this branch without changing the original opening count. Every addition is posted to the ledger and included once in expected closing cash.</p>
            </CardHeader>
            <CardContent className="grid gap-5 lg:grid-cols-2">
              <form onSubmit={addCashFloat} className="grid gap-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1"><Label htmlFor="float-amount">Amount (LSL)</Label><Input id="float-amount" type="number" min="0.01" step="0.01" required value={floatAmount} onChange={e => setFloatAmount(e.target.value)}/></div>
                  <div className="space-y-1"><Label htmlFor="float-source">Source of cash</Label><select id="float-source" value={floatSource} onChange={e => setFloatSource(e.target.value)} className="h-10 w-full rounded-lg border bg-background px-3"><option value="owner_float">Owner capital</option><option value="bank_withdrawal">Bank withdrawal</option><option value="other">Other — suspense</option></select></div>
                </div>
                <div className="space-y-1"><Label htmlFor="float-reference">Unique receipt / transfer reference</Label><Input id="float-reference" required minLength={4} maxLength={100} value={floatReference} onChange={e => setFloatReference(e.target.value)}/></div>
                <div className="space-y-1"><Label htmlFor="float-reason">Reason</Label><Textarea id="float-reason" required minLength={5} value={floatReason} onChange={e => setFloatReason(e.target.value)}/></div>
                <Button disabled={floatBusy} type="submit"><PlusCircle className="mr-2 h-4 w-4"/>{floatBusy ? "Adding cash..." : "Confirm cash top-up"}</Button>
              </form>
              <div className="rounded-xl bg-muted/30 p-4">
                <p className="mb-3 text-sm font-semibold">Float additions today</p>
                {(cashSession.float_topups ?? []).length === 0 ? <p className="text-sm text-muted-foreground">No additional float recorded yet.</p> : cashSession.float_topups.map(item => <div key={item.reference} className="mb-2 flex justify-between gap-3 border-b pb-2 text-sm"><div><p className="font-semibold">{item.reference}</p><p className="text-xs text-muted-foreground">{item.reason}</p></div><strong>{formatMoney(Number(item.amount))}</strong></div>)}
                <div className="mt-4 flex justify-between border-t pt-3 text-sm"><span>Original opening cash</span><strong>{formatMoney(Number(cashSession.counted_opening))}</strong></div>
                <div className="mt-2 flex justify-between text-sm"><span>Added float</span><strong>{formatMoney((cashSession.float_topups ?? []).reduce((sum, item) => sum + Number(item.amount), 0))}</strong></div>
                <div className="mt-2 flex justify-between border-t pt-3 font-bold"><span>Opening cash + float</span><span>{formatMoney(Number(cashSession.counted_opening) + (cashSession.float_topups ?? []).reduce((sum, item) => sum + Number(item.amount), 0))}</span></div>
              </div>
            </CardContent>
          </Card>
        ) : null}
      </TabsContent>
      <TabsContent value="expenses" className="space-y-4">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card className="rounded-2xl"><CardHeader><CardTitle>Record a daily cash expense</CardTitle><p className="text-sm text-muted-foreground">Creates a posted expense journal for today using LoanHub&apos;s existing accounting service. Report date filters do not change the posting date. Cash expenses only; use the accounting workspace for other payment methods.</p></CardHeader>
        <CardContent><form className="space-y-4" onSubmit={saveExpense}>
          <div className="space-y-1"><Label htmlFor="expense-category">Category</Label><select id="expense-category" className="h-11 w-full rounded-xl border bg-background px-3 text-sm" value={category} onChange={e => setCategory(e.target.value)}>{CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}</select></div>
          <div className="space-y-1"><Label htmlFor="expense-amount">Amount (LSL)</Label><Input id="expense-amount" type="number" step="0.01" min="0.01" required value={amount} onChange={e => setAmount(e.target.value)} placeholder="0.00"/></div>
          <div className="space-y-1"><Label htmlFor="expense-description">What was purchased?</Label><Textarea id="expense-description" minLength={2} required value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe the expense and supplier"/></div>
          <div className="space-y-1"><Label htmlFor="expense-reference">Receipt / document reference (optional)</Label><Input id="expense-reference" value={reference} onChange={e => setReference(e.target.value)} placeholder="Receipt number"/></div>
          <Button disabled={saving || loading || (branches.length > 0 && !selectedBranchId)} type="submit" className="w-full">{saving ? "Recording expense..." : "Post cash expense"}</Button>
        </form></CardContent>
      </Card>
      <Card className="rounded-2xl"><CardHeader><CardTitle>Recent expense entries</CardTitle><p className="text-sm text-muted-foreground">Posted entries from the selected period; full audit details remain in Financial Books.</p></CardHeader><CardContent className="space-y-2">
        {loading ? <p className="text-sm text-muted-foreground">Loading activity…</p> : expenses.length === 0 ? <p className="rounded-xl border p-5 text-sm text-muted-foreground">No posted expenses in the selected period.</p> : expenses.slice(0, 15).map(e => <div key={e.id} className="flex items-center justify-between gap-3 rounded-xl border p-3"><div className="min-w-0"><p className="truncate text-sm font-semibold">{e.description}</p><p className="text-xs text-muted-foreground">{e.entry_date} · {e.entry_number}</p></div><strong className="shrink-0">{formatMoney(e.total_debit)}</strong></div>)}
      </CardContent></Card>
    </div>
      </TabsContent>
      <TabsContent value="payments" className="space-y-4">
        <div className="rounded-xl border bg-muted/20 p-4 text-sm"><p className="font-semibold">LoanHub client payments</p><p className="mt-1 text-muted-foreground">For clients already in LoanHub, use the existing verified repayment process.</p><Button asChild variant="outline" className="mt-3"><Link href="/company/payments">Open LoanHub payments</Link></Button></div>
      </TabsContent>
      <TabsContent value="legacy" className="space-y-4">
        <Card className="rounded-2xl"><CardHeader><CardTitle>Old cash-out / legacy folio payments</CardTitle><p className="text-sm text-muted-foreground">For clients whose cash-out predates LoanHub. A receipt is posted to cash, bank or electronic clearing against the suspense account; it does not silently repay an unrelated loan.</p></CardHeader>
      <CardContent className="grid gap-5 xl:grid-cols-[1fr_1.2fr]">
        <form onSubmit={saveLegacyReceipt} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-1"><Label htmlFor="legacy-folio">Folio number</Label><Input id="legacy-folio" minLength={2} maxLength={80} required value={folio} onChange={e => setFolio(e.target.value)}/></div>
          <div className="space-y-1"><Label htmlFor="legacy-reference">Unique receipt reference</Label><Input id="legacy-reference" minLength={4} maxLength={120} required value={legacyReference} onChange={e => setLegacyReference(e.target.value)}/></div></div>
          <div className="space-y-1"><Label htmlFor="legacy-name">Client name</Label><Input id="legacy-name" minLength={3} required value={legacyClient} onChange={e => setLegacyClient(e.target.value)}/></div>
          <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-1"><Label htmlFor="legacy-amount">Amount paid (LSL)</Label><Input id="legacy-amount" type="number" min="0.01" step="0.01" required value={legacyAmount} onChange={e => setLegacyAmount(e.target.value)}/></div>
          <div className="space-y-1"><Label htmlFor="legacy-channel">Payment channel</Label><select id="legacy-channel" value={legacyChannel} onChange={e => setLegacyChannel(e.target.value as typeof legacyChannel)} className="h-10 w-full rounded-lg border bg-background px-3"><option value="cash">Cash</option><option value="bank">Bank</option><option value="electronic">Mpesa / electronic</option></select></div></div>
          <Button type="submit" className="w-full" disabled={legacySaving || loading || (branches.length > 0 && !selectedBranchId)}>{legacySaving ? "Recording..." : "Record folio receipt"}</Button>
        </form>
        <div className="space-y-2"><p className="text-sm font-semibold">Legacy receipts in selected period</p>
          {loading ? <p className="text-sm text-muted-foreground">Loading...</p> : legacyReceipts.length === 0 ? <p className="rounded-xl border p-5 text-sm text-muted-foreground">No legacy folio receipts in this period.</p> : legacyReceipts.slice(0, 12).map(receipt => <div key={receipt.id} className="flex items-start justify-between gap-3 rounded-xl border p-3"><div className="min-w-0"><p className="text-sm font-semibold">{receipt.receipt_reference}</p><p className="text-xs text-muted-foreground">{receipt.description}</p><p className="text-xs text-amber-700">Pending reconciliation · {receipt.entry_date}</p></div><strong className="shrink-0">{formatMoney(Number(receipt.amount))}</strong></div>)}
        </div>
      </CardContent>
    </Card>
      </TabsContent>
      <TabsContent value="reports" className="space-y-4">
        <div className="rounded-xl border bg-muted/20 p-4 text-sm"><p className="font-semibold">Financial reporting</p><p className="mt-1 text-muted-foreground">Choose the reporting period above. The summary cards remain visible on every tab and use successful payment transactions and posted journal entries.</p></div>
        <div className="grid gap-3 md:grid-cols-3">
      <Action href="/company/payments" icon={<ArrowDownLeft className="h-5 w-5"/>} title="Record client repayments" description="Use LoanHub&apos;s payment register and verified receipt posting."/>
      <Action href="/company/loans" icon={<ArrowUpRight className="h-5 w-5"/>} title="View loans & disbursements" description="Review every client loan and detailed disbursement records."/>
      <Action href="/company/accounting" icon={<BookOpen className="h-5 w-5"/>} title="Financial books" description="Open the full accounting journals, trial balance and statements."/>
    </div>
      </TabsContent>
    </Tabs>
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm"><CalendarDays className="mr-2 inline h-4 w-4"/>The cash close uses posted cash journals after opening. Legacy receipts are held in suspense until matched against the original cash-out records; the posting does not reduce a current LoanHub loan balance.</div>
  </div>;
}
function Metric({icon,title,amount,hint}:{icon:ReactNode;title:string;amount:number|null;hint:string}) {
  return <Card className="rounded-2xl border-border/80 bg-card shadow-sm transition-colors hover:border-primary/30"><CardContent className="space-y-2 p-4 sm:p-5"><div className="flex items-center gap-3 text-sm font-semibold text-muted-foreground"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">{icon}</span>{title}</div><p className="break-words text-2xl font-extrabold tracking-tight">{amount === null ? "Not yet available" : formatMoney(amount)}</p><p className="text-xs leading-relaxed text-muted-foreground">{hint}</p></CardContent></Card>;
}
function Action({href,icon,title,description}:{href:string;icon:ReactNode;title:string;description:string}) {
  return <Link href={href} className="flex min-h-28 items-start gap-3 rounded-2xl border bg-card p-5 shadow-sm transition hover:border-primary/40 hover:bg-primary/5">{icon}<div><p className="font-bold">{title}</p><p className="mt-1 text-xs text-muted-foreground">{description}</p></div></Link>;
}
