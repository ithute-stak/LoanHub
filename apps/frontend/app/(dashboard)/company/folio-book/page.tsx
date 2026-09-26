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
  const [exporting, setExporting] = useState(false);

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
    setExporting(true);
    try {
      await downloadFolioBookCsv(group === "all" ? undefined : group);
    } finally {
      setExporting(false);
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
            <Button onClick={() => void exportCsv()} disabled={exporting}>
              <Download className="mr-2 h-4 w-4" /> Export CSV
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
          <CardDescription>The next folio is calculated independently for each work group.</CardDescription>
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
          <CardDescription>Search by folio, loan reference, borrower contact or employer.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_220px_220px_auto]">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search BFS-LMPS-00001, loan, employer..." className="pl-9" />
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
                  <TableHead>Folio No.</TableHead><TableHead>Borrower</TableHead><TableHead>Loan</TableHead><TableHead>Work group</TableHead><TableHead>Principal</TableHead><TableHead>Balance</TableHead><TableHead>Status</TableHead><TableHead>Date</TableHead><TableHead className="text-right">Open</TableHead>
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
                    <TableCell className="text-right"><Button asChild size="sm" variant="ghost"><Link href={`/company/loans?folio=${encodeURIComponent(row.folio_number)}`}><ExternalLink className="mr-2 h-4 w-4" /> Loan</Link></Button></TableCell>
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
