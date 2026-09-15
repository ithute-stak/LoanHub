"use client";

import { useMemo, useState } from "react";
import { Layers3, Plus, RefreshCw, Trash2 } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { CdasBulkAnalyzeResponse } from "@/types/cdasBulkProcessing";

interface BulkRow {
  id: string;
  clientName: string;
  clientReference: string;
  amountOwing: string;
  rawText: string;
}

function newRow(): BulkRow {
  return { id: `${Date.now()}-${Math.random()}`, clientName: "", clientReference: "", amountOwing: "", rawText: "" };
}

function splitList(value: string) {
  return value.split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean);
}

function money(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `M ${Number(value).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

export function CdasBulkProcessingView() {
  const [rows, setRows] = useState<BulkRow[]>([newRow()]);
  const [ownItemCodes, setOwnItemCodes] = useState("");
  const [ownAgencyNames, setOwnAgencyNames] = useState("");
  const [bookingLeadMonths, setBookingLeadMonths] = useState(6);
  const [result, setResult] = useState<CdasBulkAnalyzeResponse | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");

  const readyCount = useMemo(() => rows.filter((row) => row.rawText.trim()).length, [rows]);

  function updateRow(id: string, field: keyof Omit<BulkRow, "id">, value: string) {
    setRows((current) => current.map((row) => row.id === id ? { ...row, [field]: value } : row));
  }

  function addRow() {
    setRows((current) => current.length >= 25 ? current : [...current, newRow()]);
  }

  function removeRow(id: string) {
    setRows((current) => current.length === 1 ? current : current.filter((row) => row.id !== id));
  }

  async function processBatch() {
    setError("");
    if (!readyCount) {
      setError("Add CDAS text to at least one client record.");
      return;
    }
    if (rows.some((row) => !row.rawText.trim())) {
      setError("Remove empty client rows or paste CDAS text into every row before processing.");
      return;
    }

    setProcessing(true);
    try {
      const response = await cdasBookingApi.bulkAnalyze({
        items: rows.map((row) => {
          const amount = Number(row.amountOwing.replace(/,/g, ""));
          return {
            raw_text: row.rawText,
            booking_lead_months: Math.max(0, Math.min(60, Number(bookingLeadMonths) || 0)),
            own_item_codes: splitList(ownItemCodes),
            own_agency_names: splitList(ownAgencyNames),
            amount_owing: Number.isFinite(amount) && amount > 0 ? amount : undefined,
            client_name: row.clientName.trim() || undefined,
            client_reference: row.clientReference.trim() || undefined,
          };
        }),
      });
      setResult(response);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not process this CDAS batch.");
    } finally {
      setProcessing(false);
    }
  }

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><Layers3 className="h-5 w-5"/></div>
            <div>
              <CardTitle>Bulk CDAS Processing</CardTitle>
              <CardDescription>Analyze and archive up to 25 client CDAS records in one controlled batch. Every client gets an independent success or error result.</CardDescription>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => setRows([newRow()])} disabled={processing}><RefreshCw className="mr-2 h-4 w-4"/>Clear batch</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg border bg-muted/20 p-3 text-sm text-muted-foreground">
          Successful records are archived in CDAS Analysis History. Exact duplicates reuse the existing archive. This workspace does not automatically create booking opportunities; review the results first.
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-2"><label className="text-sm font-medium">Own item codes</label><Input value={ownItemCodes} onChange={(event) => setOwnItemCodes(event.target.value)} placeholder="Comma separated"/></div>
          <div className="space-y-2"><label className="text-sm font-medium">Own agency names</label><Input value={ownAgencyNames} onChange={(event) => setOwnAgencyNames(event.target.value)} placeholder="Comma separated"/></div>
          <div className="space-y-2"><label className="text-sm font-medium">Booking lead months</label><Input type="number" min={0} max={60} value={bookingLeadMonths} onChange={(event) => setBookingLeadMonths(Number(event.target.value))}/></div>
        </div>
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
      </CardContent>
    </Card>

    <div className="space-y-4">
      {rows.map((row, index) => <Card key={row.id}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-3">
            <div><CardTitle className="text-base">Client record {index + 1}</CardTitle><CardDescription>Keep one client’s CDAS text in this record only.</CardDescription></div>
            <Button variant="ghost" size="sm" onClick={() => removeRow(row.id)} disabled={processing || rows.length === 1}><Trash2 className="h-4 w-4"/></Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-3">
            <Input aria-label={`Client ${index + 1} name`} value={row.clientName} onChange={(event) => updateRow(row.id, "clientName", event.target.value)} placeholder="Client name (optional)"/>
            <Input aria-label={`Client ${index + 1} reference`} value={row.clientReference} onChange={(event) => updateRow(row.id, "clientReference", event.target.value)} placeholder="Employee no. / NID / reference"/>
            <Input aria-label={`Client ${index + 1} amount owing`} value={row.amountOwing} onChange={(event) => updateRow(row.id, "amountOwing", event.target.value)} placeholder="Amount owing (optional)"/>
          </div>
          <Textarea aria-label={`Client ${index + 1} CDAS text`} value={row.rawText} onChange={(event) => updateRow(row.id, "rawText", event.target.value)} placeholder="Paste this client’s CDAS screen/table text here" className="min-h-36 font-mono text-xs"/>
        </CardContent>
      </Card>)}
    </div>

    <div className="flex flex-wrap items-center gap-3">
      <Button variant="outline" onClick={addRow} disabled={processing || rows.length >= 25}><Plus className="mr-2 h-4 w-4"/>Add client record</Button>
      <Button onClick={() => void processBatch()} disabled={processing || !readyCount}>{processing ? "Processing batch…" : `Process ${readyCount || rows.length} record${(readyCount || rows.length) === 1 ? "" : "s"}`}</Button>
      <span className="text-xs text-muted-foreground">{rows.length}/25 batch slots</span>
    </div>

    {result && <Card>
      <CardHeader><CardTitle>Batch results</CardTitle><CardDescription>Results preserve the same order as the submitted client records.</CardDescription></CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Total</div><div className="text-xl font-semibold">{result.summary.total}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Successful</div><div className="text-xl font-semibold">{result.summary.successful}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Errors</div><div className="text-xl font-semibold">{result.summary.errors}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">New archives</div><div className="text-xl font-semibold">{result.summary.archived_new}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Archive reused</div><div className="text-xl font-semibold">{result.summary.archive_reused}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Review required</div><div className="text-xl font-semibold">{result.summary.review_required}</div></div>
        </div>

        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="bg-muted/40 text-left"><tr><th className="p-3">#</th><th className="p-3">Client</th><th className="p-3">Status</th><th className="p-3">Decision</th><th className="p-3">Capacity</th><th className="p-3">Next booking</th><th className="p-3">Quality issues</th><th className="p-3">Archive</th></tr></thead>
            <tbody>{result.items.map((item) => <tr key={item.index} className="border-t align-top">
              <td className="p-3">{item.index}</td>
              <td className="p-3"><div className="font-medium">{item.client_name || "Client name not captured"}</div><div className="text-xs text-muted-foreground">{item.client_reference || "No reference"}</div>{item.error && <div className="mt-2 max-w-md text-xs text-destructive">{item.error}</div>}</td>
              <td className="p-3"><Badge variant={item.status === "SUCCESS" ? "secondary" : "destructive"}>{item.status}</Badge></td>
              <td className="p-3">{item.decision || "—"}</td>
              <td className="p-3">{money(item.assessed_available_amount)}</td>
              <td className="p-3">{dateLabel(item.next_possible_booking_date)}</td>
              <td className="p-3">{item.data_quality_issue_count}</td>
              <td className="p-3">{item.status === "SUCCESS" ? item.archived_new ? "New" : "Existing reused" : "—"}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </CardContent>
    </Card>}
  </div>;
}
