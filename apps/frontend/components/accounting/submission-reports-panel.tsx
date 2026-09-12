"use client";

import { useMemo, useState } from "react";
import { Download, FileText, RefreshCcw, ShieldCheck } from "lucide-react";

import { expenseManagementApi } from "@/api/expenseManagement";
import { downloadManagedFile } from "@/api/files";
import { generateReport } from "@/api/reports";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DataPagination } from "@/components/ui/data-pagination";
import { LoadingButton } from "@/components/ui/loading-button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { upsertSubmission } from "@/store/features/slices/financialOperationsSlice";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const PAGE_SIZE = 10;

export function SubmissionReportsPanel({
  branches,
  selectedBranchId,
  dateFrom,
  dateTo,
  onRefresh,
}: {
  branches: Array<{ id: string; name: string }>;
  selectedBranchId: string | null;
  dateFrom: string;
  dateTo: string;
  onRefresh: () => Promise<void> | void;
}) {
  const dispatch = useAppDispatch();
  const { submissions, reports } = useAppSelector((state) => state.financialOperations);
  const [submissionPage, setSubmissionPage] = useState(1);
  const [reportPage, setReportPage] = useState(1);
  const [mode, setMode] = useState<"all" | "automatic" | "manual">("all");
  const [working, setWorking] = useState(false);

  const filtered = useMemo(() => submissions.filter((item) => mode === "all" || (mode === "automatic" ? item.is_automatic : !item.is_automatic)), [mode, submissions]);
  const pagedSubmissions = filtered.slice((submissionPage - 1) * PAGE_SIZE, submissionPage * PAGE_SIZE);
  const pagedReports = reports.slice((reportPage - 1) * PAGE_SIZE, reportPage * PAGE_SIZE);

  function branchName(id: string) { return branches.find((branch) => branch.id === id)?.name ?? id.slice(0, 8); }

  async function downloadSubmission(submissionId: string) {
    setWorking(true);
    try {
      let submission = submissions.find((item) => item.id === submissionId) ?? await expenseManagementApi.submission(submissionId);
      if (!submission.pdf_file) {
        submission = await expenseManagementApi.regenerateSubmissionPdf(submissionId);
      }
      dispatch(upsertSubmission(submission));
      if (!submission.pdf_file) throw new Error("The submission PDF was not generated");
      await downloadManagedFile(submission.pdf_file);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The branch submission PDF could not be downloaded"));
    } finally { setWorking(false); }
  }

  async function createSavedReport(reportType: "financial" | "portfolio" | "operations" | "executive") {
    setWorking(true);
    try {
      await generateReport({
        report_type: reportType,
        output_format: "pdf",
        scope_type: selectedBranchId ? "branch" : "company",
        branch_id: selectedBranchId ?? undefined,
        period_start: dateFrom,
        period_end: dateTo,
      });
      await onRefresh();
      toast.success(`${titleCase(reportType)} report generated and stored in Documents`);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The report could not be generated"));
    } finally { setWorking(false); }
  }

  return (
    <div className="space-y-5">
      <Card className="rounded-3xl border-primary/20 bg-gradient-to-br from-primary/10 via-card to-sky-500/5"><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" />Permanent reports and branch submission documents</CardTitle><CardDescription>Every daily branch submission creates a numbered, immutable PDF stored in Documents. Financial, portfolio, operations and executive reports can also be generated for the selected period.</CardDescription></CardHeader></Card>
      <Tabs defaultValue="submissions" className="space-y-4">
        <TabsList className="h-auto flex-wrap rounded-2xl p-1"><TabsTrigger value="submissions">HQ submissions</TabsTrigger><TabsTrigger value="reports">Saved reports</TabsTrigger></TabsList>
        <TabsContent value="submissions">
          <Card className="overflow-hidden rounded-3xl"><CardHeader className="border-b"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><CardTitle>Branch submission history</CardTitle><CardDescription>Each resubmission creates a new sequence; the previous PDF remains unchanged.</CardDescription></div><Select value={mode} onValueChange={(value) => { setMode(value as "all" | "automatic" | "manual"); setSubmissionPage(1); }}><SelectTrigger className="w-48"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All submissions</SelectItem><SelectItem value="automatic">Automatic only</SelectItem><SelectItem value="manual">Manual only</SelectItem></SelectContent></Select></div></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Date / sequence</TableHead><TableHead>Branch</TableHead><TableHead>Mode</TableHead><TableHead className="text-right">Opening</TableHead><TableHead className="text-right">Money in</TableHead><TableHead className="text-right">Money out</TableHead><TableHead className="text-right">Closing</TableHead><TableHead className="text-right">Variance</TableHead><TableHead className="text-right">File</TableHead></TableRow></TableHeader><TableBody>{pagedSubmissions.length === 0 ? <TableRow><TableCell colSpan={9} className="h-40 text-center text-muted-foreground">No branch submissions match this period.</TableCell></TableRow> : pagedSubmissions.map((item) => <TableRow key={item.id}><TableCell><p className="font-black">{item.business_date}</p><p className="text-xs text-muted-foreground">Sequence {item.sequence_number} · {formatDateTime(item.submitted_at)}</p></TableCell><TableCell>{branchName(item.branch_id)}</TableCell><TableCell><Badge variant={item.is_automatic ? "secondary" : "outline"}>{item.is_automatic ? "Automatic" : "Manual"}</Badge></TableCell><TableCell className="text-right">{formatMoney(item.opening_balance)}</TableCell><TableCell className="text-right text-emerald-600">{formatMoney(item.total_money_in)}</TableCell><TableCell className="text-right text-rose-600">{formatMoney(item.total_money_out)}</TableCell><TableCell className="text-right font-black">{formatMoney(item.closing_balance)}</TableCell><TableCell className={`text-right font-black ${Number(item.variance_amount) === 0 ? "text-emerald-600" : "text-amber-600"}`}>{formatMoney(item.variance_amount)}</TableCell><TableCell className="text-right"><LoadingButton size="sm" variant="outline" loading={working} onClick={() => void downloadSubmission(item.id)}><Download className="h-4 w-4" />PDF</LoadingButton></TableCell></TableRow>)}</TableBody></Table></div><DataPagination page={submissionPage} pageSize={PAGE_SIZE} total={filtered.length} onPageChange={setSubmissionPage} /></CardContent></Card>
        </TabsContent>
        <TabsContent value="reports" className="space-y-4">
          <Card className="rounded-3xl"><CardHeader><CardTitle>Generate and save a report</CardTitle><CardDescription>The PDF is encrypted according to the file-storage configuration and remains available in the company Files centre.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{(["financial", "portfolio", "operations", "executive"] as const).map((type) => <LoadingButton key={type} variant="outline" loading={working} onClick={() => void createSavedReport(type)}><FileText className="h-4 w-4" />{titleCase(type)} PDF</LoadingButton>)}</CardContent></Card>
          <Card className="overflow-hidden rounded-3xl"><CardHeader><CardTitle>Saved report library</CardTitle><CardDescription>Generated reports are stored as managed files rather than temporary browser downloads.</CardDescription></CardHeader><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>Report</TableHead><TableHead>Period</TableHead><TableHead>Status</TableHead><TableHead className="text-right">File</TableHead></TableRow></TableHeader><TableBody>{pagedReports.length === 0 ? <TableRow><TableCell colSpan={4} className="h-40 text-center text-muted-foreground">No saved financial reports yet.</TableCell></TableRow> : pagedReports.map((report) => <TableRow key={report.id}><TableCell><p className="font-black">{report.title}</p><p className="font-mono text-xs text-muted-foreground">{report.reference}</p></TableCell><TableCell>{report.period_start} to {report.period_end}</TableCell><TableCell><Badge variant="secondary">{titleCase(report.status)}</Badge></TableCell><TableCell className="text-right">{report.file ? <Button size="sm" variant="outline" onClick={() => void downloadManagedFile(report.file!)}><Download className="h-4 w-4" />Download</Button> : <Button size="sm" variant="ghost" disabled><RefreshCcw className="h-4 w-4" />Pending</Button>}</TableCell></TableRow>)}</TableBody></Table><DataPagination page={reportPage} pageSize={PAGE_SIZE} total={reports.length} onPageChange={setReportPage} /></CardContent></Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
