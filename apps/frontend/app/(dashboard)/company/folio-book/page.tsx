"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
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

export default function FolioBookPage() {
  const [payload, setPayload] = useState<FolioBookPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [search, setSearch] = useState("");
  const [groupCode, setGroupCode] = useState(ALL);
  const [status, setStatus] = useState(ALL);

  const query = useMemo(() => ({
    search: search.trim() || undefined,
    group_code: groupCode === ALL ? undefined : groupCode,
    status: status === ALL ? undefined : status,
    limit: 2000,
  }), [groupCode, search, status]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setPayload(await getFolioBook(query));
    } catch (error) {
      toast.error(error, { description: "The loan folio sequence book could not be loaded." });
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  const statuses = useMemo(
    () => Array.from(new Set((payload?.rows ?? []).map((row) => row.status).filter(Boolean))).sort(),
    [payload?.rows],
  );

  async function exportCsv() {
    setExporting(true);
    try {
      await downloadFolioBookCsv(query);
    } catch (error) {
      toast.error(error, { description: "The folio book CSV could not be downloaded." });
    } finally {
      setExporting(false);
    }
  }

  if (loading && !payload) return <PageLoader rows={8} />;

  const summary = payload?.summary;
  const rows = payload?.rows ?? [];
  const books = payload?.sequence_books ?? [];
  const integrityCount = summary
    ? summary.missing_folio_count
      + summary.invalid_format_count
      + summary.component_mismatch_count
      + summary.duplicate_folio_count
      + summary.duplicate_sequence_count
    : 0;

  return (
    <div className="loanhub-page space-y-6 pb-12">
      <section className="loanhub-hero overflow-hidden p-6 lg:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1.5 text-xs font-black text-primary">
              <BookOpenCheck className="h-4 w-4" /> Permanent loan sequence book
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl">Loan Folio Book</h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">
              Every loan keeps one immutable operational folio. Each work group has its own append-only sequence, so BFS-LMPS-00001 and BFS-LDF-00001 can coexist without mixing their books. Existing gaps are reported for audit but are never recycled or used to renumber historical loans.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
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

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Loans in folio book" value={String(summary?.total_loans ?? 0)} hint={`${payload?.total ?? 0} matching current filters`} />
        <Metric label="Sequence books" value={String(summary?.sequence_book_count ?? 0)} hint="One independent sequence per work group" />
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
            LoanHub found a folio identity exception. Historical folios are not automatically renumbered; investigate and repair the underlying record deliberately so the audit trail remains intact.
          </AlertDescription>
        </Alert>
      )}

      <Card className="loanhub-panel">
        <CardHeader>
          <CardTitle>Sequence books and next folios</CardTitle>
          <CardDescription>The next number is always the highest issued sequence + 1. A historical gap is never filled automatically.</CardDescription>
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
                  className="rounded-2xl border bg-card p-4 text-left transition hover:border-primary/40 hover:bg-primary/[0.03]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs font-black text-primary">{book.company_code}-{book.group_code}</p>
                      <p className="mt-1 font-black">{book.group_name ?? `${book.group_code} work group`}</p>
                    </div>
                    <Badge variant={book.gap_count ? "secondary" : "outline"}>{book.loan_count} loans</Badge>
                  </div>
                  <div className="mt-4 rounded-xl bg-muted/40 p-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">Next folio</p>
                    <p className="mt-1 font-mono text-sm font-black">{book.next_folio_number}</p>
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
        <CardHeader className="border-b">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <CardTitle>Folio register</CardTitle>
              <CardDescription className="mt-1">Search by folio, borrower, identity number, loan reference, employer, work group, branch or status.</CardDescription>
            </div>
            <div className="grid w-full gap-2 sm:grid-cols-[minmax(220px,1fr)_180px_180px] xl:w-[760px]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search folio, borrower, ID, loan…" className="pl-9" />
              </div>
              <Select value={groupCode} onValueChange={setGroupCode}>
                <SelectTrigger><SelectValue placeholder="Work group" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All work groups</SelectItem>
                  {books.map((book) => <SelectItem key={book.group_code} value={book.group_code}>{book.group_code} · {book.group_name ?? "Work group"}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All statuses</SelectItem>
                  {statuses.map((item) => <SelectItem key={item} value={item}>{titleCase(item)}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          {(groupCode !== ALL || status !== ALL || search) ? (
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <Badge variant="secondary">{payload?.total ?? 0} matching</Badge>
              <Button size="sm" variant="ghost" onClick={() => { setSearch(""); setGroupCode(ALL); setStatus(ALL); }}>Clear filters</Button>
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
"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  RefreshCcw,
  Search,
} from "lucide-react";

import {
  downloadFolioBookCsv,
  downloadFolioBookPdf,
  getFolioBook,
  type FolioBookResponse,
  type FolioBookRow,
} from "@/api/folioBook";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";

const PAGE_SIZE = 100;

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "The folio book could not be loaded.";
}

function loanStatus(row: FolioBookRow) {
  if (row.is_overdue) return <Badge variant="destructive">Overdue</Badge>;
  return <Badge variant="secondary">{titleCase(row.status)}</Badge>;
}

export default function FolioBookPage() {
  const [data, setData] = useState<FolioBookResponse | null>(null);
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("all");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"csv" | "pdf" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getFolioBook({
        search: search.trim() || undefined,
        group_code: group === "all" ? undefined : group,
        status: status === "all" ? undefined : status,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setData(result);
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, [group, page, search, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 180);
    return () => window.clearTimeout(timer);
  }, [load]);

  const groups = useMemo(
    () => data?.integrity.groups.map((item) => item.group_code) ?? [],
    [data],
  );
  const pageCount = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));

  async function exportCsv() {
    setExporting("csv");
    try {
      await downloadFolioBookCsv(group === "all" ? undefined : group);
    } finally {
      setExporting(null);
    }
  }

  async function exportPdf() {
    setExporting("pdf");
    try {
      await downloadFolioBookPdf();
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="space-y-6 pb-12">
      <section className="overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground">
              <BookOpenCheck className="h-4 w-4 text-primary" /> Permanent Loan Sequence Book
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Loan Folio Book</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
              Every loan has one immutable folio. Borrowers do not own folio numbers. Each employer/work-group keeps its own sequential book, for example BFS-LDF-00001 and BFS-LMPS-00001.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading}>
              <RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
            </Button>
            <Button variant="outline" onClick={() => void exportPdf()} disabled={exporting !== null}>
              <FileText className="mr-2 h-4 w-4" /> {exporting === "pdf" ? "Building PDF..." : "Print PDF book"}
            </Button>
            <Button onClick={() => void exportCsv()} disabled={exporting !== null}>
              <Download className="mr-2 h-4 w-4" /> {exporting === "csv" ? "Exporting..." : "Export CSV"}
            </Button>
          </div>
        </div>
      </section>

      {error ? (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">
          {error}
        </div>
      ) : null}

      {data ? (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Card><CardHeader className="pb-2"><CardDescription>Total folio loans</CardDescription><CardTitle>{data.integrity.loan_count}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Sequence books</CardDescription><CardTitle>{data.integrity.groups.length}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Missing folios</CardDescription><CardTitle>{data.integrity.missing_folio_count}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>Sequence gaps</CardDescription><CardTitle>{data.integrity.gap_count}</CardTitle></CardHeader></Card>
          <Card className={data.integrity.healthy ? "border-emerald-500/30" : "border-amber-500/40"}>
            <CardHeader className="pb-2">
              <CardDescription>Book integrity</CardDescription>
              <CardTitle className="flex items-center gap-2 text-lg">
                {data.integrity.healthy ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <AlertTriangle className="h-5 w-5 text-amber-500" />}
                {data.integrity.healthy ? "Healthy" : "Needs attention"}
              </CardTitle>
            </CardHeader>
          </Card>
        </section>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Sequence books</CardTitle>
          <CardDescription>The next folio is calculated independently for each work group. Gaps are highlighted for investigation; LoanHub never silently reuses an old sequence.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {(data?.integrity.groups ?? []).map((item) => (
            <button
              key={item.group_code}
              type="button"
              onClick={() => { setGroup(item.group_code); setPage(1); }}
              className="rounded-2xl border p-4 text-left transition hover:border-primary/50 hover:bg-muted/30"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="font-black">{item.group_code}</p>
                <Badge variant={item.gap_count ? "destructive" : "secondary"}>{item.loan_count} loans</Badge>
              </div>
              <p className="mt-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">Next folio</p>
              <p className="mt-1 font-mono text-sm font-black text-primary">{item.next_folio}</p>
              <p className="mt-2 text-xs text-muted-foreground">Last sequence: {item.last_sequence ?? 0} · Gaps: {item.gap_count}</p>
            </button>
          ))}
          {!data?.integrity.groups.length ? <p className="text-sm text-muted-foreground">No folio sequence has been created yet.</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Folio register</CardTitle>
          <CardDescription>Search by folio, loan reference, borrower name/ID/contact, employer or work group.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_220px_220px_auto]">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search BFS-LMPS-00001, borrower, ID, employer..." className="pl-9" />
            </div>
            <Select value={group} onValueChange={(value) => { setGroup(value); setPage(1); }}>
              <SelectTrigger><SelectValue placeholder="Work group" /></SelectTrigger>
              <SelectContent><SelectItem value="all">All work groups</SelectItem>{groups.map((code) => <SelectItem key={code} value={code}>{code}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={status} onValueChange={(value) => { setStatus(value); setPage(1); }}>
              <SelectTrigger><SelectValue placeholder="Loan status" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {['pending','approved','active','completed','defaulted','rejected','cancelled'].map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => { setSearch(""); setGroup("all"); setStatus("all"); setPage(1); }}>Clear filters</Button>
          </div>

          <div className="overflow-x-auto rounded-2xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Folio No.</TableHead><TableHead>Borrower</TableHead><TableHead>Loan</TableHead><TableHead>Work group</TableHead><TableHead>Principal</TableHead><TableHead>Balance</TableHead><TableHead>Status</TableHead><TableHead>Date</TableHead><TableHead className="text-right">History</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.rows ?? []).map((row) => (
                  <TableRow key={row.loan_id}>
                    <TableCell><span className="font-mono font-black text-primary">{row.folio_number}</span><div className="text-xs text-muted-foreground">Sequence {row.sequence}</div></TableCell>
                    <TableCell><p className="font-bold">{row.borrower_name}</p><p className="text-xs text-muted-foreground">{row.employer_name || "No employer recorded"}</p></TableCell>
                    <TableCell className="font-mono text-xs">{row.loan_reference}</TableCell>
                    <TableCell><Badge variant="outline">{row.group_code}</Badge></TableCell>
                    <TableCell>{formatMoney(row.principal_amount)}</TableCell>
                    <TableCell>{formatMoney(row.balance)}</TableCell>
                    <TableCell>{loanStatus(row)}</TableCell>
                    <TableCell>{row.disbursed_at ? formatDate(row.disbursed_at) : row.approved_at ? formatDate(row.approved_at) : "—"}</TableCell>
                    <TableCell className="text-right"><Button asChild size="sm" variant="ghost"><Link href={`/company/borrowers/${row.borrower_id}`}><ExternalLink className="mr-2 h-4 w-4" /> Borrower</Link></Button></TableCell>
                  </TableRow>
                ))}
                {!loading && !data?.rows.length ? <TableRow><TableCell colSpan={9} className="h-28 text-center text-muted-foreground">No folio records match the current filters.</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </div>

          <div className="flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <p className="text-muted-foreground">Showing {data?.rows.length ?? 0} of {data?.total ?? 0} matching loans.</p>
            <div className="flex items-center gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button><span className="font-bold">Page {page} of {pageCount}</span><Button variant="outline" size="sm" disabled={page >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>Next</Button></div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
