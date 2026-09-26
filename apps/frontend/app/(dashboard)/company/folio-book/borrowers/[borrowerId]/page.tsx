"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, BookOpenCheck, ExternalLink, Loader2 } from "lucide-react";

import { getBorrowerFolioHistory, type BorrowerFolioHistory } from "@/api/folioBook";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Borrower folio history could not be loaded.";
}

export default function BorrowerFolioHistoryPage() {
  const params = useParams<{ borrowerId: string }>();
  const [data, setData] = useState<BorrowerFolioHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getBorrowerFolioHistory(params.borrowerId)
      .then((result) => { if (!cancelled) setData(result); })
      .catch((nextError) => { if (!cancelled) setError(errorText(nextError)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [params.borrowerId]);

  if (loading) {
    return <div className="flex min-h-[40vh] items-center justify-center"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>;
  }

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="outline"><Link href="/company/folio-book"><ArrowLeft className="mr-2 h-4 w-4" /> Folio Book</Link></Button>
        <Button asChild variant="ghost"><Link href={`/company/borrowers/${params.borrowerId}`}><ExternalLink className="mr-2 h-4 w-4" /> Full borrower profile</Link></Button>
      </div>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      {data ? (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2 text-primary"><BookOpenCheck className="h-5 w-5" /><span className="text-xs font-black uppercase tracking-wide">Permanent loan history</span></div>
              <CardTitle className="text-2xl">{data.borrower_name}</CardTitle>
              <CardDescription>{data.loan_count} loan record(s). Each loan retains its own folio permanently; the borrower does not have one shared folio.</CardDescription>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader><CardTitle>Loan folio history</CardTitle><CardDescription>Chronological loan sequence for this borrower within the active company scope.</CardDescription></CardHeader>
            <CardContent>
              <div className="overflow-x-auto rounded-2xl border">
                <Table>
                  <TableHeader><TableRow><TableHead>Folio</TableHead><TableHead>Loan reference</TableHead><TableHead>Work group</TableHead><TableHead>Principal</TableHead><TableHead>Balance</TableHead><TableHead>Status</TableHead><TableHead>Approved / disbursed</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {data.folios.map((row) => (
                      <TableRow key={row.loan_id}>
                        <TableCell><p className="font-mono font-black text-primary">{row.folio_number}</p><p className="text-xs text-muted-foreground">Sequence {row.sequence}</p></TableCell>
                        <TableCell className="font-mono text-xs">{row.loan_reference}</TableCell>
                        <TableCell><Badge variant="outline">{row.group_code}</Badge></TableCell>
                        <TableCell>{formatMoney(row.principal_amount)}</TableCell>
                        <TableCell>{formatMoney(row.balance)}</TableCell>
                        <TableCell><Badge variant={row.is_overdue ? "destructive" : "secondary"}>{row.is_overdue ? "Overdue" : titleCase(row.status)}</Badge></TableCell>
                        <TableCell>{row.disbursed_at ? formatDate(row.disbursed_at) : row.approved_at ? formatDate(row.approved_at) : "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
