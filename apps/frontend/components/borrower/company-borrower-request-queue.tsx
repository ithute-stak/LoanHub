"use client";

import { CheckCircle2, FileClock, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  getCompanyBorrowerServiceRequests,
  updateCompanyBorrowerServiceRequest,
  type BorrowerServiceRequest,
} from "@/api/borrowerCommand";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";

const FILTERS = ["open", "submitted", "under_review", "approved", "declined", "completed", "cancelled"] as const;
const DECISIONS = ["under_review", "approved", "declined", "completed"] as const;

function errorMessage(error: unknown): string {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Unable to update the borrower request.";
}

function RequestCard({ request, onUpdated }: { request: BorrowerServiceRequest; onUpdated: () => Promise<void> }) {
  const [status, setStatus] = useState(request.status === "submitted" ? "under_review" : request.status);
  const [response, setResponse] = useState(request.company_response ?? "");
  const [saving, setSaving] = useState(false);
  const closed = ["cancelled", "declined", "completed"].includes(request.status);

  async function save() {
    setSaving(true);
    try {
      await updateCompanyBorrowerServiceRequest(request.id, { status, company_response: response.trim() || null });
      toast.success("Borrower request updated.");
      await onUpdated();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="rounded-3xl border bg-card p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-lg font-black">{request.request_type_label}</p>
          <p className="mt-1 text-sm font-bold">{request.borrower_name ?? "Borrower"}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {request.loan_reference ? `${request.loan_reference} · ` : ""}{formatDateTime(request.created_at)}
          </p>
        </div>
        <span className="inline-flex w-fit rounded-full border px-3 py-1 text-xs font-black">{titleCase(request.status)}</span>
      </div>
      {request.details ? <div className="mt-4 rounded-2xl bg-muted/50 p-4 text-sm leading-6">{request.details}</div> : null}
      {request.requested_value != null ? <p className="mt-3 text-sm"><span className="text-muted-foreground">Requested value:</span> <strong>{formatMoney(request.requested_value)}</strong></p> : null}
      {closed ? (
        <div className="mt-4 rounded-2xl border p-4 text-sm">
          <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">Final lender response</p>
          <p className="mt-2 leading-6">{request.company_response || "No written response was recorded."}</p>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 lg:grid-cols-[200px_1fr_auto] lg:items-end">
          <label className="text-xs font-black">Status<select value={status} onChange={(event) => setStatus(event.target.value)} className="mt-1.5 h-11 w-full rounded-xl border bg-background px-3 text-sm">{DECISIONS.map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}</select></label>
          <label className="text-xs font-black">Response to borrower<textarea value={response} onChange={(event) => setResponse(event.target.value)} rows={3} maxLength={5000} className="mt-1.5 w-full rounded-xl border bg-background p-3 text-sm" placeholder="Explain the decision, next step, required documents or approved arrangement." /></label>
          <button type="button" onClick={() => void save()} disabled={saving} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Update</button>
        </div>
      )}
    </article>
  );
}

export function CompanyBorrowerRequestQueue() {
  const [rows, setRows] = useState<BorrowerServiceRequest[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("open");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCompanyBorrowerServiceRequests(filter === "open" ? undefined : filter);
      setRows(data);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { void load(); }, [load]);

  const visible = useMemo(() => filter === "open" ? rows.filter((row) => ["submitted", "under_review", "approved"].includes(row.status)) : rows, [filter, rows]);

  return (
    <div className="space-y-5 pb-10">
      <section className="rounded-3xl border bg-card p-5 shadow-sm sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-black text-primary"><FileClock className="h-3.5 w-3.5" /> Borrower servicing</div><h1 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">Borrower service-request queue</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Review settlement quotations, payment arrangements, hardship requests, top-ups, refinancing, consolidation, disputes, statements and paid-up letters submitted by your borrowers.</p></div><button type="button" onClick={() => void load()} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border px-4 text-sm font-black"><RefreshCw className="h-4 w-4" /> Refresh</button></div>
      </section>
      <div className="flex gap-2 overflow-x-auto rounded-2xl border bg-card p-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">{FILTERS.map((value) => <button key={value} type="button" onClick={() => setFilter(value)} className={`h-10 shrink-0 rounded-xl px-3 text-xs font-black ${filter === value ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>{titleCase(value)}</button>)}</div>
      {loading ? <div className="flex min-h-56 items-center justify-center rounded-3xl border bg-card"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div> : <div className="space-y-4">{visible.map((request) => <RequestCard key={request.id} request={request} onUpdated={load} />)}{!visible.length ? <div className="rounded-3xl border border-dashed p-10 text-center text-sm text-muted-foreground">No borrower requests match this view.</div> : null}</div>}
    </div>
  );
}
