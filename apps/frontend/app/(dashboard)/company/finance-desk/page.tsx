"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { ArrowDownLeft, ArrowUpRight, BookOpen, CalendarDays, HandCoins, ReceiptText, RefreshCcw, Wallet } from "lucide-react";
import { listJournalEntries } from "@/api/accounting";
import { branchApi } from "@/api/branch";
import { useTenant } from "@/provider/tenantProvider";
import type { Branch } from "@/types/branch";
import { listLoans } from "@/api/loans";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { JournalEntry } from "@/types/accounting";
import type { Loan } from "@/types/loan";
import { toast } from "@/utils/toast";
import { getErrorMessage } from "@/utils/apiError";

type CashSession = {
  id: string; status: "open" | "closed"; business_date: string; branch_id: string | null;
  counted_opening: string; cash_movement: string; expected_closing: string;
  counted_closing: string | null; variance: string | null;
  coverage_note: string;
};
type LegacyReceipt = {id: string; receipt_reference: string; description: string; amount: string; entry_date: string; status: string};
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
  const {activeCompanyId, activeBranchId} = useTenant();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchSelection, setBranchSelection] = useState("");
  const selectedBranchId = branchSelection || activeBranchId || null;
  useEffect(() => { if (!activeCompanyId) return; void branchApi.getByCompany(activeCompanyId).then(res => setBranches(res.data.filter(row => row.is_active))).catch(() => setBranches([])); }, [activeCompanyId]);
  const [period, setPeriod] = useState<Period>("day");
  const [asOf, setAsOf] = useState(() => localDate(new Date()));
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [cashSession, setCashSession] = useState<CashSession | null>(null);
  const [opening, setOpening] = useState("");
  const [closing, setClosing] = useState("");
  const [cashNote, setCashNote] = useState("");
  const [cashBusy, setCashBusy] = useState(false);
  const [loans, setLoans] = useState<Loan[]>([]);
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
      const [journal, currentLoans, session, receipts] = await Promise.all([
        listJournalEntries({ fromDate: rangeStart, toDate: asOf, branchId: selectedBranchId, limit: 500 }),
        listLoans(),
        api.get<CashSession | null>("/accounting/daily-cash", {params: {business_date: localDate(new Date()), branch_id: selectedBranchId || undefined}}).then(res => res.data),
        api.get<LegacyReceipt[]>("/accounting/legacy-folio-receipts", {params: {from_date: rangeStart, to_date: asOf, branch_id: selectedBranchId || undefined}}).then(res => res.data),
      ]);
      setEntries(journal);
      setLoans(currentLoans);
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
  const expenseTotal = expenses.reduce((total, e) => total + Number(e.total_debit), 0);
  const disbursements = useMemo(() => loans.filter(l => (!selectedBranchId || l.branch_id === selectedBranchId) && l.disbursed_at && l.disbursed_at.slice(0, 10) >= rangeStart && l.disbursed_at.slice(0, 10) <= asOf), [loans, rangeStart, asOf, selectedBranchId]);
  const issuedTotal = disbursements.reduce((total, l) => total + Number(l.principal_amount), 0);
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
  return <div className="space-y-6 p-2 sm:p-0">
    <div className="rounded-3xl border bg-gradient-to-br from-primary/10 via-background to-background p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-widest text-primary">Payments & Finance</p><h1 className="mt-2 text-3xl font-black">Daily Finance Desk</h1><p className="mt-2 text-sm text-muted-foreground">Record expenses and see live accounting and loan activity without navigating the full financial books.</p></div>
        <Button variant="outline" onClick={() => void reload()} disabled={loading}><RefreshCcw className="mr-2 h-4 w-4"/>Refresh</Button>
      </div>
      <div className="mt-5 flex flex-wrap items-end gap-3">
        {branches.length ? <div className="space-y-1"><Label htmlFor="finance-branch">Branch</Label><select id="finance-branch" className="h-10 rounded-lg border bg-background px-3" value={selectedBranchId ?? ""} onChange={e => setBranchSelection(e.target.value)}><option value="">All-company / unassigned cash</option>{branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></div> : null}
        <div className="space-y-1"><Label htmlFor="finance-date">Through date</Label><Input id="finance-date" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} max={localDate(new Date())}/></div>
        <div className="flex flex-wrap gap-1 rounded-xl border p-1">{(["day","week","month","year"] as Period[]).map(p => <Button key={p} type="button" size="sm" variant={period === p ? "default" : "ghost"} onClick={() => setPeriod(p)}>{({day:"Day",week:"Week",month:"Month",year:"Year"})[p]}</Button>)}</div>
        <p className="pb-2 text-xs text-muted-foreground">Showing {rangeStart} to {asOf}</p>
      </div>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric icon={<HandCoins className="h-5 w-5"/>} title="Loans issued" amount={issuedTotal} hint={`${disbursements.length} disbursed loans`}/>
      <Metric icon={<ReceiptText className="h-5 w-5"/>} title="Recorded expenses" amount={expenseTotal} hint={`${expenses.length} posted expenses`}/>
      <Metric icon={<ArrowDownLeft className="h-5 w-5"/>} title="Legacy folio receipts" amount={legacyReceipts.reduce((sum, e) => sum + Number(e.amount), 0)} hint={`${legacyReceipts.length} awaiting folio reconciliation`}/>
      <Metric icon={<Wallet className="h-5 w-5"/>} title="Expected closing cash" amount={cashSession ? Number(cashSession.expected_closing) : null} hint={cashSession ? (cashSession.status === "closed" ? "Closed — see confirmed count below" : "Posted cash movements since opening only") : "Open today’s cash session to begin"}/>
    </div>
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
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card className="rounded-2xl"><CardHeader><CardTitle>Record a daily cash expense</CardTitle><p className="text-sm text-muted-foreground">Creates a posted expense journal for today using LoanHub&apos;s existing accounting service. Report date filters do not change the posting date. Cash expenses only; use the accounting workspace for other payment methods.</p></CardHeader>
        <CardContent><form className="space-y-4" onSubmit={saveExpense}>
          <div className="space-y-1"><Label htmlFor="expense-category">Category</Label><select id="expense-category" className="h-10 w-full rounded-lg border bg-background px-3" value={category} onChange={e => setCategory(e.target.value)}>{CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}</select></div>
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
    <div className="grid gap-3 md:grid-cols-3">
      <Action href="/company/payments" icon={<ArrowDownLeft className="h-5 w-5"/>} title="Record client repayments" description="Use LoanHub's payment register and verified receipt posting."/>
      <Action href="/company/loans" icon={<ArrowUpRight className="h-5 w-5"/>} title="View loans & disbursements" description="Review every client loan and detailed disbursement records."/>
      <Action href="/company/accounting" icon={<BookOpen className="h-5 w-5"/>} title="Financial books" description="Open the full accounting journals, trial balance and statements."/>
    </div>
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm"><CalendarDays className="mr-2 inline h-4 w-4"/>The cash close uses posted cash journals after opening. Legacy receipts are held in suspense until matched against the original cash-out records; the posting does not reduce a current LoanHub loan balance.</div>
  </div>;
}
function Metric({icon,title,amount,hint}:{icon:ReactNode;title:string;amount:number|null;hint:string}) {
  return <Card className="rounded-2xl"><CardContent className="space-y-2 p-5"><div className="flex items-center gap-2 text-sm text-muted-foreground">{icon}{title}</div><p className="text-2xl font-black">{amount === null ? "Not yet available" : formatMoney(amount)}</p><p className="text-xs text-muted-foreground">{hint}</p></CardContent></Card>;
}
function Action({href,icon,title,description}:{href:string;icon:ReactNode;title:string;description:string}) {
  return <Link href={href} className="flex gap-3 rounded-2xl border p-5 transition hover:border-primary/40 hover:bg-primary/5">{icon}<div><p className="font-bold">{title}</p><p className="mt-1 text-xs text-muted-foreground">{description}</p></div></Link>;
}
