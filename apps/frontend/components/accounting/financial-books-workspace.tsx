"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { BookOpenCheck, CalendarCheck2, RefreshCcw, Scale, Upload } from "lucide-react";

import { createOpeningBalanceMigration, getFinancialBooks, listAccountingAccounts } from "@/api/accounting";
import { governanceControlsApi, type ControlRecord } from "@/api/governanceControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import type { AccountingAccount, FinancialBooksPack } from "@/types/accounting";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type OpeningLine = { account_id: string; debit: number; credit: number; description: string };

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function yearStart() {
  const now = new Date();
  return `${now.getFullYear()}-01-01`;
}

export function FinancialBooksWorkspace() {
  const { currentCompany, currentBranch, branches } = useAppData();
  const [fromDate, setFromDate] = useState(yearStart());
  const [toDate, setToDate] = useState(isoToday());
  const [branchId, setBranchId] = useState(currentBranch?.id ?? "all");
  const [books, setBooks] = useState<FinancialBooksPack | null>(null);
  const [periods, setPeriods] = useState<ControlRecord[]>([]);
  const [readiness, setReadiness] = useState<Record<string, unknown> | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState<string>("");
  const [accounts, setAccounts] = useState<AccountingAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [periodWorking, setPeriodWorking] = useState(false);
  const [openingWorking, setOpeningWorking] = useState(false);
  const [periodNote, setPeriodNote] = useState("Reviewed and supported by period close evidence.");
  const [newPeriodStart, setNewPeriodStart] = useState(yearStart());
  const [newPeriodEnd, setNewPeriodEnd] = useState(isoToday());
  const [openingDate, setOpeningDate] = useState(yearStart());
  const [openingReference, setOpeningReference] = useState(`OPENING-${new Date().getFullYear()}`);
  const [openingDescription, setOpeningDescription] = useState("Opening balances migrated into LoanHub");
  const [openingLines, setOpeningLines] = useState<OpeningLine[]>([
    { account_id: "", debit: 0, credit: 0, description: "" },
    { account_id: "", debit: 0, credit: 0, description: "" },
  ]);

  useEffect(() => {
    setBranchId(currentBranch?.id ?? "all");
  }, [currentBranch?.id]);

  const companyId = currentCompany?.id;
  const effectiveBranchId = branchId === "all" ? null : branchId;

  const loadBooks = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    try {
      const result = await getFinancialBooks({
        companyId,
        branchId: effectiveBranchId,
        fromDate,
        toDate,
        includeLedgerDetail: true,
      });
      setBooks(result);
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not prepare the financial books"));
    } finally {
      setLoading(false);
    }
  }, [companyId, effectiveBranchId, fromDate, toDate]);

  const loadControls = useCallback(async () => {
    if (!companyId) return;
    try {
      const [periodRows, accountRows] = await Promise.all([
        governanceControlsApi.accountingPeriods(),
        listAccountingAccounts(companyId),
      ]);
      setPeriods(periodRows);
      setAccounts(accountRows);
      setSelectedPeriod((current) => current || periodRows[0]?.id || "");
      if (accountRows.length >= 2) {
        setOpeningLines((current) => current.map((line, index) => ({
          ...line,
          account_id: line.account_id || accountRows[index]?.id || accountRows[0]?.id || "",
        })));
      }
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not load accounting controls"));
    }
  }, [companyId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadBooks();
      void loadControls();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadBooks, loadControls]);

  const openingTotals = useMemo(
    () => openingLines.reduce(
      (sum, line) => ({ debit: sum.debit + Number(line.debit || 0), credit: sum.credit + Number(line.credit || 0) }),
      { debit: 0, credit: 0 },
    ),
    [openingLines],
  );
  const openingBalanced = openingTotals.debit > 0 && Math.abs(openingTotals.debit - openingTotals.credit) < 0.005;

  async function createPeriod() {
    if (!newPeriodStart || !newPeriodEnd) return;
    setPeriodWorking(true);
    try {
      const created = await governanceControlsApi.createAccountingPeriod(newPeriodStart, newPeriodEnd);
      toast.success("Accounting period created");
      await loadControls();
      setSelectedPeriod(created.id);
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not create accounting period"));
    } finally {
      setPeriodWorking(false);
    }
  }

  async function checkReadiness() {
    if (!selectedPeriod) return;
    setPeriodWorking(true);
    try {
      const result = await governanceControlsApi.periodReadiness(selectedPeriod);
      setReadiness(result.close_pack);
      toast.success("Period close readiness refreshed");
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not evaluate period readiness"));
    } finally {
      setPeriodWorking(false);
    }
  }

  async function periodAction(action: "lock" | "close" | "reopen") {
    if (!selectedPeriod || periodNote.trim().length < 5) return;
    setPeriodWorking(true);
    try {
      await governanceControlsApi.periodAction(selectedPeriod, action, periodNote.trim());
      toast.success(action === "lock" ? "Period soft-closed" : action === "close" ? "Period hard-closed" : "Period reopened");
      setReadiness(null);
      await loadControls();
    } catch (error) {
      toast.error(getErrorMessage(error, `Could not ${action} accounting period`));
    } finally {
      setPeriodWorking(false);
    }
  }

  function updateOpeningLine(index: number, patch: Partial<OpeningLine>) {
    setOpeningLines((current) => current.map((line, i) => i === index ? { ...line, ...patch } : line));
  }

  async function createOpeningDraft() {
    if (!companyId || !openingBalanced) {
      toast.error("Opening balance debits and credits must be equal");
      return;
    }
    setOpeningWorking(true);
    try {
      await createOpeningBalanceMigration({
        entry_date: openingDate,
        description: openingDescription.trim(),
        migration_reference: openingReference.trim(),
        branch_id: effectiveBranchId,
        lines: openingLines
          .filter((line) => Number(line.debit || 0) > 0 || Number(line.credit || 0) > 0)
          .map((line) => ({
            account_id: line.account_id,
            description: line.description.trim() || undefined,
            debit: Number(line.debit || 0),
            credit: Number(line.credit || 0),
          })),
      }, companyId);
      toast.success("Opening-balance draft created", { description: "A different finance user must post it before it becomes official ledger truth." });
      await loadBooks();
    } catch (error) {
      toast.error(getErrorMessage(error, "Could not create opening balances"));
    } finally {
      setOpeningWorking(false);
    }
  }

  const currentPeriod = periods.find((period) => period.id === selectedPeriod);
  const closeChecks = ((readiness?.checks ?? {}) as Record<string, boolean>);
  const ratioGroups = books?.financial_ratios ?? {};

  return (
    <div className="loanhub-page space-y-6">
      <section className="loanhub-hero flex flex-col justify-between gap-5 p-6 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Frank Wood engine</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Financial Books</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
            Prepare the official accounting books from posted LoanHub transactions, close accounting periods, and migrate balanced opening balances.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadBooks()} disabled={loading}><RefreshCcw className="h-4 w-4" />Refresh books</Button>
      </section>

      <Tabs defaultValue="books" className="space-y-5">
        <TabsList className="grid h-auto w-full grid-cols-3 rounded-2xl p-1">
          <TabsTrigger value="books">Financial books</TabsTrigger>
          <TabsTrigger value="periods">Period close</TabsTrigger>
          <TabsTrigger value="opening">Opening balances</TabsTrigger>
        </TabsList>

        <TabsContent value="books" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader><CardTitle>Reporting period</CardTitle><CardDescription>Choose the scope used to prepare the complete accounting book pack.</CardDescription></CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-4">
              <Field label="From"><Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} /></Field>
              <Field label="To"><Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} /></Field>
              <Field label="Branch"><Select value={branchId} onValueChange={setBranchId}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All branches</SelectItem>{branches.map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}</SelectItem>)}</SelectContent></Select></Field>
              <div className="flex items-end"><LoadingButton className="w-full" loading={loading} onClick={() => void loadBooks()}><BookOpenCheck className="h-4 w-4" />Prepare books</LoadingButton></div>
            </CardContent>
          </Card>

          {books ? <>
            <div className="grid gap-4 md:grid-cols-4">
              <Metric label="Trial balance difference" value={formatMoney(books.trial_balance.difference)} />
              <Metric label="Net profit" value={formatMoney(Number(books.income_statement.totals.net_profit ?? 0))} />
              <Metric label="Total assets" value={formatMoney(Number(books.statement_of_financial_position.totals.total_assets ?? books.statement_of_financial_position.totals.asset ?? 0))} />
              <Metric label="General ledger accounts" value={String(books.general_ledger.length)} />
            </div>

            <Card className="loanhub-panel overflow-hidden">
              <CardHeader><CardTitle>Book index</CardTitle><CardDescription>{books.preparation_note}</CardDescription></CardHeader>
              <CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>#</TableHead><TableHead>Book</TableHead><TableHead>Purpose</TableHead></TableRow></TableHeader><TableBody>{books.book_index.map((item) => <TableRow key={item.order}><TableCell>{item.order}</TableCell><TableCell className="font-black">{titleCase(item.book)}</TableCell><TableCell>{item.purpose}</TableCell></TableRow>)}</TableBody></Table></CardContent>
            </Card>

            <Card className="loanhub-panel overflow-hidden">
              <CardHeader><CardTitle>General ledger</CardTitle><CardDescription>Opening, period movements and closing balance for every active account.</CardDescription></CardHeader>
              <CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Account</TableHead><TableHead className="text-right">Opening</TableHead><TableHead className="text-right">Debit</TableHead><TableHead className="text-right">Credit</TableHead><TableHead className="text-right">Closing</TableHead></TableRow></TableHeader><TableBody>{books.general_ledger.map((row) => <TableRow key={row.account_id}><TableCell><span className="font-mono text-xs font-black text-primary">{row.account_code}</span><p className="font-semibold">{row.account_name}</p></TableCell><TableCell className="text-right">{formatMoney(row.opening_balance)}</TableCell><TableCell className="text-right">{formatMoney(row.period_debit)}</TableCell><TableCell className="text-right">{formatMoney(row.period_credit)}</TableCell><TableCell className="text-right font-black">{formatMoney(row.closing_balance)}</TableCell></TableRow>)}</TableBody></Table></div></CardContent>
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Statement title="Income statement" statement={books.income_statement} />
              <Statement title="Statement of financial position" statement={books.statement_of_financial_position} />
            </div>

            <Card className="loanhub-panel">
              <CardHeader><CardTitle>Financial analysis</CardTitle><CardDescription>Frank Wood Chapters 38–39 ratios. These are signals for interpretation, not conclusions by themselves.</CardDescription></CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {Object.entries(ratioGroups).filter(([, value]) => value && typeof value === "object" && !Array.isArray(value)).slice(0, 4).map(([group, values]) => <div key={group} className="rounded-2xl border p-4"><p className="mb-3 font-black">{titleCase(group)}</p><div className="space-y-2 text-sm">{Object.entries(values as Record<string, unknown>).slice(0, 6).map(([key, value]) => <div key={key} className="flex justify-between gap-4"><span className="text-muted-foreground">{titleCase(key)}</span><span className="font-bold">{value == null ? "—" : typeof value === "number" ? value.toFixed(2) : String(value)}</span></div>)}</div></div>)}
              </CardContent>
            </Card>
          </> : <Card className="loanhub-panel"><CardContent className="py-14 text-center text-muted-foreground">Prepare the books to view the full accounting pack.</CardContent></Card>}
        </TabsContent>

        <TabsContent value="periods" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader><CardTitle className="flex items-center gap-2"><CalendarCheck2 className="h-5 w-5 text-primary" />Accounting period close</CardTitle><CardDescription>Open → locked (soft-close) → closed (hard-close). Locking is allowed only when the full close pack is green.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
                <Field label="New period start"><Input type="date" value={newPeriodStart} onChange={(e) => setNewPeriodStart(e.target.value)} /></Field>
                <Field label="New period end"><Input type="date" value={newPeriodEnd} onChange={(e) => setNewPeriodEnd(e.target.value)} /></Field>
                <div className="flex items-end"><LoadingButton loading={periodWorking} variant="outline" onClick={() => void createPeriod()}>Create period</LoadingButton></div>
              </div>
              <Field label="Period"><Select value={selectedPeriod} onValueChange={(value) => { setSelectedPeriod(value); setReadiness(null); }}><SelectTrigger><SelectValue placeholder="Select accounting period" /></SelectTrigger><SelectContent>{periods.map((period) => <SelectItem key={period.id} value={period.id}>{String(period.period_start)} – {String(period.period_end)} · {titleCase(period.status)}</SelectItem>)}</SelectContent></Select></Field>
              {currentPeriod ? <div className="flex flex-wrap gap-2"><Badge>{titleCase(currentPeriod.status)}</Badge><Badge variant="outline">{String(currentPeriod.period_start)} – {String(currentPeriod.period_end)}</Badge></div> : null}
              <Field label="Control note"><Textarea value={periodNote} onChange={(e) => setPeriodNote(e.target.value)} /></Field>
              <div className="flex flex-wrap gap-2">
                <LoadingButton loading={periodWorking} variant="outline" onClick={() => void checkReadiness()}><Scale className="h-4 w-4" />Check readiness</LoadingButton>
                {currentPeriod?.status === "open" ? <LoadingButton loading={periodWorking} onClick={() => void periodAction("lock")}>Soft-close</LoadingButton> : null}
                {currentPeriod?.status === "locked" ? <LoadingButton loading={periodWorking} onClick={() => void periodAction("close")}>Hard-close</LoadingButton> : null}
                {currentPeriod && ["locked", "closed"].includes(String(currentPeriod.status)) ? <LoadingButton loading={periodWorking} variant="destructive" onClick={() => void periodAction("reopen")}>Reopen</LoadingButton> : null}
              </div>
            </CardContent>
          </Card>

          {readiness ? <Card className="loanhub-panel"><CardHeader><CardTitle>Close readiness</CardTitle><CardDescription>{Boolean(readiness.ready_to_lock) ? "All hard controls currently pass." : "Resolve the failed controls before soft-close."}</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{Object.entries(closeChecks).map(([key, passed]) => <div key={key} className="flex items-center justify-between rounded-xl border p-3"><span className="text-sm">{titleCase(key)}</span><Badge variant={passed ? "default" : "destructive"}>{passed ? "Pass" : "Fail"}</Badge></div>)}</CardContent></Card> : null}
        </TabsContent>

        <TabsContent value="opening" className="space-y-5">
          <Card className="loanhub-panel">
            <CardHeader><CardTitle className="flex items-center gap-2"><Upload className="h-5 w-5 text-primary" />Opening balance migration</CardTitle><CardDescription>Create a balanced draft. A different authorised finance user must post it through the normal maker/checker journal workflow.</CardDescription></CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-4 md:grid-cols-3">
                <Field label="Opening date"><Input type="date" value={openingDate} onChange={(e) => setOpeningDate(e.target.value)} /></Field>
                <Field label="Migration reference"><Input value={openingReference} onChange={(e) => setOpeningReference(e.target.value)} /></Field>
                <Field label="Description"><Input value={openingDescription} onChange={(e) => setOpeningDescription(e.target.value)} /></Field>
              </div>
              <div className="overflow-x-auto rounded-2xl border">
                <Table><TableHeader><TableRow><TableHead>Account</TableHead><TableHead>Description</TableHead><TableHead className="w-40">Debit</TableHead><TableHead className="w-40">Credit</TableHead></TableRow></TableHeader><TableBody>{openingLines.map((line, index) => <TableRow key={index}><TableCell><Select value={line.account_id} onValueChange={(account_id) => updateOpeningLine(index, { account_id })}><SelectTrigger className="min-w-64"><SelectValue placeholder="Select account" /></SelectTrigger><SelectContent>{accounts.map((account) => <SelectItem key={account.id} value={account.id}>{account.code} · {account.name}</SelectItem>)}</SelectContent></Select></TableCell><TableCell><Input value={line.description} onChange={(e) => updateOpeningLine(index, { description: e.target.value })} /></TableCell><TableCell><Input type="number" min={0} step="0.01" value={line.debit || ""} onChange={(e) => updateOpeningLine(index, { debit: Number(e.target.value || 0), credit: e.target.value ? 0 : line.credit })} /></TableCell><TableCell><Input type="number" min={0} step="0.01" value={line.credit || ""} onChange={(e) => updateOpeningLine(index, { credit: Number(e.target.value || 0), debit: e.target.value ? 0 : line.debit })} /></TableCell></TableRow>)}</TableBody></Table>
              </div>
              <Button variant="outline" onClick={() => setOpeningLines((rows) => [...rows, { account_id: accounts[0]?.id ?? "", debit: 0, credit: 0, description: "" }])}>Add line</Button>
              <div className="grid gap-3 md:grid-cols-3"><Metric label="Opening debits" value={formatMoney(openingTotals.debit)} /><Metric label="Opening credits" value={formatMoney(openingTotals.credit)} /><Metric label="Difference" value={formatMoney(Math.abs(openingTotals.debit - openingTotals.credit))} /></div>
              <LoadingButton loading={openingWorking} disabled={!openingBalanced || !openingReference.trim() || !openingDescription.trim()} onClick={() => void createOpeningDraft()}><Upload className="h-4 w-4" />Create opening-balance draft</LoadingButton>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border bg-card p-4"><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-2 text-xl font-black">{value}</p></div>;
}

function Statement({ title, statement }: { title: string; statement: FinancialBooksPack["income_statement"] }) {
  return <Card className="loanhub-panel"><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="space-y-4">{Object.entries(statement.sections ?? {}).map(([section, rows]) => <div key={section} className="rounded-xl border"><div className="flex justify-between bg-muted/30 px-3 py-2 font-black"><span>{titleCase(section)}</span><span>{formatMoney(Number(statement.totals[section] ?? 0))}</span></div>{rows.map((row) => <div key={`${section}-${row.code}`} className="flex justify-between gap-4 border-t px-3 py-2 text-sm"><span>{row.code} · {row.name}</span><span className="font-bold">{formatMoney(row.amount)}</span></div>)}</div>)}</CardContent></Card>;
}
