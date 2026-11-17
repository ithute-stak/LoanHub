"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  Download,
  ExternalLink,
  RefreshCcw,
  Search,
} from "lucide-react";

import {
  downloadFolioBookCsv,
  downloadFolioDueInstallmentsPdf,
  downloadFolioNextInstallmentsPdf,
  getFolioBook,
  type FolioBookPayload,
  type FolioBookRow,
} from "@/api/folioBook";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoader } from "@/components/ui/page-loader";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { toast } from "@/utils/toast";

const ALL = "__all__";
const PAGE_SIZE = 25;
const LOAN_STATUSES = ["pending", "approved", "active", "completed", "defaulted", "rejected", "cancelled"] as const;

export default function FolioBookPage() {
  const [payload, setPayload] = useState<FolioBookPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportingDue, setExportingDue] = useState(false);
  const [exportingNext, setExportingNext] = useState(false);
  const [nextFromDate, setNextFromDate] = useState("");
  const [nextThroughDate, setNextThroughDate] = useState("");
  const [search, setSearch] = useState("");
  const [groupCode, setGroupCode] = useState(ALL);
  const [status, setStatus] = useState(ALL);
  const [page, setPage] = useState(1);
  const requestSequence = useRef(0);

  const query = useMemo(() => ({
    search: search.trim() || undefined,
    group_code: groupCode === ALL ? undefined : groupCode,
    status: status === ALL ? undefined : status,
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
  }), [groupCode, search, status, page]);

  const load = useCallback(async () => {
    const sequence = ++requestSequence.current;
    setLoading(true);
    try {
      const result = await getFolioBook(query);
      if (sequence === requestSequence.current) {
        setPayload(result);
      }
    } catch (error) {
      if (sequence === requestSequence.current) {
        toast.error(error, { description: "The loan folio sequence book could not be loaded." });
      }
    } finally {
      if (sequence === requestSequence.current) setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    // Invalidate older requests as soon as filters or page change, even
    // while the new request is waiting for the search debounce.
    requestSequence.current += 1;
    const timer = window.setTimeout(() => void load(), 250);
    return () => {
      window.clearTimeout(timer);
      requestSequence.current += 1;
    };
  }, [load]);


  async function exportCsv() {
    setExporting(true);
    try {
      await downloadFolioBookCsv({ search: query.search, group_code: query.group_code, status: query.status });
    } catch (error) {
      toast.error(error, { description: "The folio book CSV could not be downloaded." });
    } finally {
      setExporting(false);
    }
  }

  async function exportDuePdf() {
    setExportingDue(true);
    try {
      await downloadFolioDueInstallmentsPdf(groupCode === ALL ? undefined : groupCode);
      toast.success("Due instalments report generated");
    } catch (error) {
      toast.error(error, { description: "Could not generate the due instalments report." });
    } finally {
      setExportingDue(false);
    }
  }

  async function exportNextPdf() {
    if (nextFromDate && nextThroughDate && nextFromDate > nextThroughDate) {
      toast.error("Start date must not be after end date.");
      return;
    }
    setExportingNext(true);
    try {
      await downloadFolioNextInstallmentsPdf({
        search: search.trim() || undefined,
        group_code: groupCode === ALL ? undefined : groupCode,
        status: status === ALL ? undefined : status,
        from_date: nextFromDate || undefined,
        through_date: nextThroughDate || undefined,
      });
      toast.success("Next installment PDF generated");
    } catch (error) {
      toast.error(error, { description: "Could not generate the next installment report." });
    } finally {
      setExportingNext(false);
    }
  }

  // A loan may be removed or completed while viewing the last page.
  // Recover from an out-of-range page after the current response settles.
  useEffect(() => {
    if (!loading && payload && page > Math.max(1, Math.ceil(payload.total / PAGE_SIZE))) {
      setPage(Math.max(1, Math.ceil(payload.total / PAGE_SIZE)));
    }
  }, [loading, payload, page]);

  if (loading && !payload) return <PageLoader rows={8} />;

  const summary = payload?.summary;
  const rows = payload?.rows ?? [];
  const totalRows = payload?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));
  const firstRow = totalRows ? (page - 1) * PAGE_SIZE + 1 : 0;
  const lastRow = Math.min(page * PAGE_SIZE, totalRows);
  const books = payload?.sequence_books ?? [];
  const integrityCount = summary
    ? summary.missing_folio_count
      + summary.invalid_format_count
      + summary.component_mismatch_count
      + summary.duplicate_folio_count
      + summary.duplicate_sequence_count
    : 0;

  return (
    <div className="loanhub-page space-y-5 pb-12">
      <section className="loanhub-hero overflow-hidden rounded-3xl border border-border/60 bg-gradient-to-br from-card via-card to-primary/[0.06] p-5 shadow-sm lg:p-7">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1.5 text-xs font-black text-primary">
              <BookOpenCheck className="h-4 w-4" /> Permanent loan sequence book
            </div>
            <h1 className="mt-3 text-2xl font-extrabold tracking-tight sm:text-3xl">Loan Folio Book</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Track every loan folio, monitor sequence integrity, and find borrower records in one place. BFS contractual pay-day groups are 15–22 = Force, 23–26 = CIVIL, and 27–31 plus 1–14 = S/E. Examples: BFS-Force-00001, BFS-CIVIL-00001 and BFS-S/E-00001. Historical gaps are preserved for audit.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 xl:max-w-[440px] xl:justify-end">
            <Button variant="outline" asChild>
              <Link href="/company/folio-book/performance">Performance dashboard</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/company/loans">Loans & contracts</Link>
            </Button>
            <Button variant="outline" onClick={() => void load()} disabled={loading}>
              <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
            </Button>
            <Button onClick={() => void exportCsv()} disabled={exporting}>
              <Download className="h-4 w-4" /> {exporting ? "Preparing…" : "Export CSV"}
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
        <Metric label="Loans in folio book" value={String(summary?.total_loans ?? 0)} hint={`${payload?.total ?? 0} matching current filters`} />
        <Metric label="Sequence books" value={String(summary?.sequence_book_count ?? 0)} hint="Independent sequence per folio group" />
        <Metric label="Sequence gaps" value={String(summary?.gap_count ?? 0)} hint="Reported only; gaps are never reused" />
        <Metric label="Integrity exceptions" value={String(integrityCount)} hint="Missing, duplicate or mismatched identifiers" />
        <Metric label="Integrity state" value={summary?.integrity_ok ? "CLEAR" : "ATTENTION"} hint={summary?.integrity_ok ? "No critical folio identity errors detected" : "Review the exception rows below"} />
      </section>

      {summary?.integrity_ok ? (
        <Alert className="border-emerald-500/30 bg-emerald-500/5">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <AlertTitle>Folio identity integrity is clear</AlertTitle>
          <AlertDescription>
            No missing folios, duplicate folios, duplicate sequence positions, malformed folios or component mismatches were detected in the visible company scope.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Folio integrity requires attention</AlertTitle>
          <AlertDescription>
            LoanHub found a folio identity exception. After the approved BFS pay-date migration, folios are append-only; investigate any later exception deliberately so the audit trail remains intact.
          </AlertDescription>
        </Alert>
      )}

      <Card className="loanhub-panel">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg font-bold">Sequence books</CardTitle>
          <CardDescription>Select a group to filter the register. Next folios advance from the highest issued number; historical gaps are never reused.</CardDescription>
        </CardHeader>
        <CardContent>
          {books.length === 0 ? (
            <p className="rounded-2xl border bg-muted/20 p-6 text-sm text-muted-foreground">No folio sequence books are available in this scope.</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {books.map((book) => (
                <button
                  key={book.group_code}
                  type="button"
                  onClick={() => setGroupCode(book.group_code)}
                  className={`group rounded-2xl border p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${groupCode === book.group_code ? "border-primary/60 bg-primary/[0.06] ring-1 ring-primary/20" : "border-border/70 bg-card hover:bg-muted/20"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs font-black text-primary">{book.company_code}-{book.group_code}</p>
                      <p className="mt-1 font-black">{book.group_name ?? `${book.group_code} work group`}</p>
                    </div>
                    <Badge variant={book.gap_count ? "secondary" : "outline"}>{book.loan_count} loans</Badge>
                  </div>
                  <div className="mt-5 rounded-xl border border-border/40 bg-muted/35 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">Next folio</p>
                    <p className="mt-1 break-all font-mono text-base font-bold tracking-tight">{book.next_folio_number}</p>
                  </div>
                  <p className="mt-3 text-xs text-muted-foreground">
                    Issued {book.first_sequence ?? 0}–{book.last_sequence ?? 0} · {book.gap_count} gap{book.gap_count === 1 ? "" : "s"}
                  </p>
                  {book.gap_count > 0 ? (
                    <p className="mt-1 truncate text-[11px] font-semibold text-amber-700" title={book.gaps.join(", ")}>
                      Missing sequence positions: {book.gaps.slice(0, 12).join(", ")}{book.gaps.length > 12 || book.gaps_truncated ? "…" : ""}
                    </p>
                  ) : null}
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="loanhub-panel overflow-hidden">
        <CardHeader className="space-y-4 border-b bg-muted/10">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <CardTitle className="text-lg font-bold">Folio register</CardTitle>
              <CardDescription className="mt-1">Search by folio, borrower, identity number, loan reference, employer, work group, branch or status.</CardDescription>
            </div>
            <div className="grid w-full gap-2 sm:grid-cols-[minmax(220px,1fr)_170px_150px] xl:w-[680px]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search folio, borrower, ID, loan…" className="pl-9" />
              </div>
              <Select value={groupCode} onValueChange={(value) => { setGroupCode(value); setPage(1); }}>
                <SelectTrigger><SelectValue placeholder="Folio group" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All folio groups</SelectItem>
                  {books.map((book) => <SelectItem key={book.group_code} value={book.group_code}>{book.group_code} · {book.group_name ?? "Work group"}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={status} onValueChange={(value) => { setStatus(value); setPage(1); }}>
                <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All statuses</SelectItem>
                  {LOAN_STATUSES.map((item) => <SelectItem key={item} value={item}>{titleCase(item)}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/60 bg-background/70 p-3">
            <p className="text-xs text-muted-foreground">Due report uses the selected work group and includes all unpaid instalments due through today, even if the table has another status or search filter.</p>
            <Button type="button" disabled={exportingDue} onClick={() => void exportDuePdf()}>
              <Download className="h-4 w-4" />{exportingDue ? "Generating due PDF…" : "Download due instalments PDF"}
            </Button>
          </div>
          <div className="flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/70 p-3">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-muted-foreground">New loans disbursed from 01 Sep 2026 only. Payment dates are optional filters.</span>
              <label htmlFor="next-from-date" className="text-xs font-semibold">Payment from</label>
              <Input id="next-from-date" type="date" value={nextFromDate} onChange={(event) => setNextFromDate(event.target.value)} className="w-[170px]" />
            </div>
            <div className="space-y-1">
              <label htmlFor="next-through-date" className="text-xs font-semibold">Payment through</label>
              <Input id="next-through-date" type="date" value={nextThroughDate} onChange={(event) => setNextThroughDate(event.target.value)} className="w-[170px]" />
            </div>
            <Button type="button" variant="outline" disabled={exportingNext} onClick={() => void exportNextPdf()}>
              <Download className="h-4 w-4" />{exportingNext ? "Generating…" : "Download next payments PDF"}
            </Button>
            <p className="text-xs text-muted-foreground">One earliest unpaid instalment per loan. Uses the search, group and status filters above. Leave dates empty to include overdue and future payments.</p>
          </div>
          {(groupCode !== ALL || status !== ALL || search) ? (
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <Badge variant="secondary">{payload?.total ?? 0} matching</Badge>
              <Button size="sm" variant="ghost" onClick={() => { setSearch(""); setGroupCode(ALL); setStatus(ALL); setPage(1); }}>Clear filters</Button>
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="p-0">
          <div className="space-y-3 p-4 md:hidden">
            {rows.map((row) => <MobileRow key={row.loan_id} row={row} />)}
            {rows.length === 0 ? <EmptyRows /> : null}
          </div>
          <div className="hidden overflow-x-auto md:block">
            <Table className="min-w-[1250px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-5">Folio</TableHead>
                  <TableHead>Work group</TableHead>
                  <TableHead>Borrower</TableHead>
                  <TableHead>Loan reference</TableHead>
                  <TableHead className="text-right">Principal</TableHead>
                  <TableHead className="text-right">Paid</TableHead>
                  <TableHead className="text-right">Balance</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Issued</TableHead>
                  <TableHead>Integrity</TableHead>
                  <TableHead className="pr-5 text-right">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length === 0 ? (
                  <TableRow><TableCell colSpan={12} className="h-56"><EmptyRows /></TableCell></TableRow>
                ) : rows.map((row) => (
                  <TableRow key={row.loan_id}>
                    <TableCell className="pl-5">
                      <p className="font-mono text-xs font-black text-primary">{row.folio_number ?? "MISSING"}</p>
                      <p className="mt-1 text-[10px] text-muted-foreground">Sequence {row.folio_sequence || "—"}</p>
                    </TableCell>
                    <TableCell>
                      <p className="font-black">{row.folio_group_code}</p>
                      <p className="mt-1 max-w-[170px] truncate text-[10px] text-muted-foreground" title={row.employer_group_name ?? row.employer_name ?? undefined}>{row.employer_group_name ?? row.employer_name ?? "Unassigned"}</p>
                    </TableCell>
                    <TableCell>
                      <p className="max-w-[180px] truncate text-xs font-bold" title={row.borrower_name}>{row.borrower_name}</p>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">{row.borrower_identity ?? "No identity recorded"}</p>
                    </TableCell>
                    <TableCell className="font-mono text-[11px]">{row.loan_reference}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatMoney(row.principal_amount)}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatMoney(row.amount_paid)}</TableCell>
                    <TableCell className="text-right text-xs font-black tabular-nums">{formatMoney(row.balance)}</TableCell>
                    <TableCell><Badge variant={row.status === "active" || row.status === "completed" ? "default" : "secondary"}>{titleCase(row.status)}</Badge></TableCell>
                    <TableCell className="max-w-[150px] truncate text-xs">{row.branch_name ?? "Unassigned"}</TableCell>
                    <TableCell className="text-xs">{row.created_at ? formatDate(row.created_at) : "—"}</TableCell>
                    <TableCell><IntegrityBadge row={row} /></TableCell>
                    <TableCell className="pr-5 text-right">
                      <Button size="icon-sm" variant="ghost" asChild title={`Open ${row.folio_number ?? row.loan_reference}`}>
                        <Link href={`/company/loans?folio=${encodeURIComponent(row.folio_number ?? row.loan_reference)}`}><ExternalLink className="h-4 w-4" /></Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t px-2 py-4 text-sm">
            <span className="text-muted-foreground">Showing {firstRow}–{lastRow} of {totalRows} folios · Page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={loading || page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button>
              <Button variant="outline" size="sm" disabled={loading || page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>Next</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Alert>
        <BookOpenCheck className="h-4 w-4" />
        <AlertTitle>Sequence-book rule</AlertTitle>
        <AlertDescription>
          The folio belongs to the loan, not to the client. A borrower may therefore have several historical folios across different loans. Once issued, a folio remains attached to that loan even if the borrower&apos;s employer or work group later changes.
        </AlertDescription>
      </Alert>
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return <div className="loanhub-stat">
    <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
    <p className="mt-2 text-2xl font-black tracking-tight">{value}</p>
    <p className="mt-2 text-xs leading-5 text-muted-foreground">{hint}</p>
  </div>;
}

function IntegrityBadge({ row }: { row: FolioBookRow }) {
  if (!row.integrity_issues.length) return <Badge variant="outline" className="border-emerald-500/40 text-emerald-700">OK</Badge>;
  return <Badge variant="destructive" title={row.integrity_issues.join(", ")}>{row.integrity_issues.length} issue{row.integrity_issues.length === 1 ? "" : "s"}</Badge>;
}

function MobileRow({ row }: { row: FolioBookRow }) {
  return <article className="rounded-2xl border bg-card p-4">
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="font-mono text-sm font-black text-primary">{row.folio_number ?? "MISSING FOLIO"}</p>
        <p className="mt-1 text-xs font-bold">{row.borrower_name}</p>
        <p className="mt-1 font-mono text-[10px] text-muted-foreground">{row.loan_reference}</p>
      </div>
      <IntegrityBadge row={row} />
    </div>
    <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
      <div className="rounded-xl bg-muted/40 p-3"><p className="text-[10px] font-black uppercase text-muted-foreground">Work group</p><p className="mt-1 font-black">{row.folio_group_code}</p></div>
      <div className="rounded-xl bg-muted/40 p-3"><p className="text-[10px] font-black uppercase text-muted-foreground">Balance</p><p className="mt-1 font-black">{formatMoney(row.balance)}</p></div>
    </div>
    <div className="mt-3 flex items-center justify-between gap-3">
      <Badge variant="secondary">{titleCase(row.status)}</Badge>
      <Button size="sm" variant="outline" asChild><Link href={`/company/loans?folio=${encodeURIComponent(row.folio_number ?? row.loan_reference)}`}>Open loan</Link></Button>
    </div>
  </article>;
}

function EmptyRows() {
  return <div className="flex min-h-40 flex-col items-center justify-center p-6 text-center">
    <BookOpenCheck className="h-10 w-10 text-muted-foreground" />
    <p className="mt-3 font-black">No folio records match</p>
    <p className="mt-1 text-sm text-muted-foreground">Clear the filters or search with another folio, borrower or loan reference.</p>
  </div>;
}
