"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BellRing,
  CalendarClock,
  CheckCircle2,
  ClipboardPaste,
  Clock3,
  Download,
  Printer,
  RotateCcw,
  Save,
} from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import type {
  CdasBookingAnalysis,
  CdasBookingMonitor,
  CdasBookingMonitorPhase,
  CdasDeductionAnalysis,
} from "@/types/cdasBooking";

const SETTINGS_KEY = "loanhub.cdasBooking.settings.v1";
const SAMPLE_TEXT = `| | 2561 | Lesana Lesotho Limited | | M 3,942.08 | 2026-Mar | 2027-Aug | 1000093084 | Active |
| | 2595 | First National Bank of Lesotho | | M 21,011.86 | 2024-Jan | 2028-Dec | FNB LOAN 62592936979 | Active |`;

type TabKey = "analyze" | "upcoming" | "book-now" | "booked";
type SavedSettings = { bookingLeadMonths: number; ownItemCodes: string; ownAgencyNames: string };

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "analyze", label: "Analyze" },
  { key: "upcoming", label: "Upcoming" },
  { key: "book-now", label: "Book Now" },
  { key: "booked", label: "Booked" },
];

function money(value: number) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

function monthLabel(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-ZA", { month: "short", year: "numeric" });
}

function splitList(value: string) {
  return value.split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean);
}

function requestError(caught: unknown, fallback: string) {
  return typeof caught === "object" && caught && "response" in caught
    ? ((caught as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? fallback)
    : fallback;
}

function phaseLabel(phase: CdasBookingMonitorPhase) {
  if (phase === "BOOK_NOW") return "Book now";
  if (phase === "ALERTING") return "Alerting";
  if (phase === "BOOKED") return "Booked";
  return "Upcoming";
}

function csvCell(value: unknown) {
  const text = String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

function rowResult(row: CdasDeductionAnalysis) {
  if (row.booking_status === "BOOKED_BY_US") return "Already booked by us";
  if (row.booking_status === "BOOK_NOW") return "Book now";
  if (row.booking_status === "WAIT") return `Book from ${monthLabel(row.booking_open_date)}`;
  return "Not active";
}

export default function CdasBookingAnalyzerPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("analyze");
  const [rawText, setRawText] = useState("");
  const [ownItemCodes, setOwnItemCodes] = useState("");
  const [ownAgencyNames, setOwnAgencyNames] = useState("");
  const [bookingLeadMonths, setBookingLeadMonths] = useState(6);
  const [result, setResult] = useState<CdasBookingAnalysis | null>(null);
  const [monitors, setMonitors] = useState<CdasBookingMonitor[]>([]);
  const [clientName, setClientName] = useState("");
  const [clientReference, setClientReference] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [monitorLoading, setMonitorLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function loadMonitors() {
    setMonitorLoading(true);
    try {
      setMonitors(await cdasBookingApi.listMonitors());
    } catch (caught) {
      setError(requestError(caught, "Saved CDAS monitoring could not be loaded."));
    } finally {
      setMonitorLoading(false);
    }
  }

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SETTINGS_KEY);
      if (stored) {
        const settings = JSON.parse(stored) as Partial<SavedSettings>;
        if (typeof settings.bookingLeadMonths === "number") setBookingLeadMonths(settings.bookingLeadMonths);
        if (typeof settings.ownItemCodes === "string") setOwnItemCodes(settings.ownItemCodes);
        if (typeof settings.ownAgencyNames === "string") setOwnAgencyNames(settings.ownAgencyNames);
      }
      const requestedTab = new URLSearchParams(window.location.search).get("tab") as TabKey | null;
      if (requestedTab && tabs.some((tab) => tab.key === requestedTab)) setActiveTab(requestedTab);
    } catch {
      // Local preferences and query parameters are optional conveniences.
    }
    void loadMonitors();
  }, []);

  useEffect(() => {
    const settings: SavedSettings = { bookingLeadMonths, ownItemCodes, ownAgencyNames };
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }, [bookingLeadMonths, ownItemCodes, ownAgencyNames]);

  const groups = useMemo(() => ({
    upcoming: monitors.filter((item) => item.phase === "UPCOMING" || item.phase === "ALERTING"),
    bookNow: monitors.filter((item) => item.phase === "BOOK_NOW"),
    booked: monitors.filter((item) => item.phase === "BOOKED"),
  }), [monitors]);

  async function analyze() {
    setError(""); setSuccess(""); setResult(null);
    if (!rawText.trim()) { setError("Paste the CDAS deduction text first."); return; }
    setLoading(true);
    try {
      setResult(await cdasBookingApi.analyze({
        raw_text: rawText,
        booking_lead_months: Math.max(0, Math.min(60, Number(bookingLeadMonths) || 0)),
        own_item_codes: splitList(ownItemCodes),
        own_agency_names: splitList(ownAgencyNames),
      }));
    } catch (caught) {
      setError(requestError(caught, "CDAS text could not be analyzed."));
    } finally { setLoading(false); }
  }

  async function saveOpportunity() {
    const opportunity = result?.opportunity;
    if (!opportunity) return;
    if (!clientName.trim()) { setError("Enter the client name before saving this opportunity."); return; }
    setSaving(true); setError(""); setSuccess("");
    try {
      await cdasBookingApi.createMonitor({
        client_name: clientName.trim(),
        client_reference: clientReference.trim() || null,
        item_code: opportunity.item_code,
        agency_name: opportunity.agency_name,
        deduction_amount: opportunity.deduction_amount,
        effective_date: opportunity.effective_date,
        expiry_date: opportunity.expiry_date,
        reference_no: opportunity.reference_no || null,
        source_status: opportunity.status,
        booking_lead_months: result.booking_lead_months,
      });
      setSuccess(`${clientName.trim()} is now monitored. Alerts start 3 days before the booking window and repeat daily until booked.`);
      setClientName(""); setClientReference("");
      await loadMonitors();
      setActiveTab("upcoming");
    } catch (caught) {
      setError(requestError(caught, "This booking opportunity could not be saved."));
    } finally { setSaving(false); }
  }

  async function markBooked(item: CdasBookingMonitor) {
    setError(""); setSuccess("");
    try {
      await cdasBookingApi.markBooked(item.id);
      setSuccess(`${item.client_name} has been marked Booked. Reminder alerts have stopped.`);
      await loadMonitors();
    } catch (caught) {
      setError(requestError(caught, "The booking could not be completed."));
    }
  }

  function exportCsv() {
    if (!result) return;
    const headers = ["Item Code", "Agency", "Deduction", "Effective", "Expiry", "Reference", "Booking Opens", "Result"];
    const lines = [
      headers.map(csvCell).join(","),
      ...result.deductions.map((row) => [row.item_code, row.agency_name, row.deduction_amount.toFixed(2), row.effective_date, row.expiry_date, row.reference_no, row.booking_open_date, rowResult(row)].map(csvCell).join(",")),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `cdas-booking-analysis-${result.as_of}.csv`;
    document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
  }

  const monitorCards = (items: CdasBookingMonitor[], empty: string, allowBook = false) => (
    <Card>
      <CardContent className="pt-6">
        {monitorLoading ? <p className="text-sm text-muted-foreground">Loading monitored clients…</p> : items.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">{empty}</div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <div key={item.id} className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold">{item.client_name}</h3>
                      <Badge variant="outline">{phaseLabel(item.phase)}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{item.agency_name} · {money(item.deduction_amount)} / month</p>
                    <p className="mt-2 text-xs text-muted-foreground">CDAS ref: {item.reference_no || "—"} · Client ref: {item.client_reference || "—"}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
                    <div><span className="text-xs text-muted-foreground">Expires</span><div className="font-medium">{monthLabel(item.expiry_date)}</div></div>
                    <div><span className="text-xs text-muted-foreground">Alert starts</span><div className="font-medium">{dateLabel(item.alert_start_date)}</div></div>
                    <div><span className="text-xs text-muted-foreground">Book from</span><div className="font-medium">{dateLabel(item.booking_open_date)}</div></div>
                    <div><span className="text-xs text-muted-foreground">Countdown</span><div className="font-medium">{item.phase === "BOOKED" ? "Complete" : item.phase === "BOOK_NOW" ? "Ready now" : `${item.days_until_booking} days`}</div></div>
                  </div>
                  {allowBook && <Button onClick={() => void markBooked(item)}><CheckCircle2 className="mr-2 h-4 w-4" />Mark Booked</Button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2"><ClipboardPaste className="h-5 w-5" /><h1 className="text-2xl font-semibold tracking-tight">CDAS Booking Workspace</h1></div>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">Analyze CDAS deductions, save the next opportunity, and keep following it until the client is booked.</p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-xs sm:flex">
          <div className="rounded-lg border px-3 py-2"><strong className="block text-base">{groups.upcoming.length}</strong>Upcoming</div>
          <div className="rounded-lg border px-3 py-2"><strong className="block text-base">{groups.bookNow.length}</strong>Book now</div>
          <div className="rounded-lg border px-3 py-2"><strong className="block text-base">{groups.booked.length}</strong>Booked</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 rounded-xl border bg-muted/30 p-2 print:hidden">
        {tabs.map((tab) => (
          <Button key={tab.key} variant={activeTab === tab.key ? "default" : "ghost"} onClick={() => setActiveTab(tab.key)}>
            {tab.key === "analyze" && <ClipboardPaste className="mr-2 h-4 w-4" />}
            {tab.key === "upcoming" && <Clock3 className="mr-2 h-4 w-4" />}
            {tab.key === "book-now" && <BellRing className="mr-2 h-4 w-4" />}
            {tab.key === "booked" && <CheckCircle2 className="mr-2 h-4 w-4" />}
            {tab.label}{tab.key === "upcoming" ? ` (${groups.upcoming.length})` : tab.key === "book-now" ? ` (${groups.bookNow.length})` : tab.key === "booked" ? ` (${groups.booked.length})` : ""}
          </Button>
        ))}
      </div>

      {error && <Alert variant="destructive"><AlertTitle>CDAS workspace</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
      {success && <Alert><CheckCircle2 className="h-4 w-4" /><AlertTitle>Saved</AlertTitle><AlertDescription>{success}</AlertDescription></Alert>}

      {activeTab === "analyze" && <div className="space-y-6">
        <Alert><CalendarClock className="h-4 w-4" /><AlertTitle>Automatic monitoring</AlertTitle><AlertDescription>LoanHub starts warning 3 days before the calculated booking-open date and sends a new high-priority reminder each day until staff mark the opportunity Booked.</AlertDescription></Alert>

        <Card>
          <CardHeader><CardTitle>1. Company booking settings</CardTitle><CardDescription>Identify your own deductions and set how many months before expiry your company starts booking.</CardDescription></CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-3">
            <div className="space-y-2"><Label htmlFor="own-item-codes">Our CDAS item code(s)</Label><Input id="own-item-codes" value={ownItemCodes} onChange={(e) => setOwnItemCodes(e.target.value)} placeholder="e.g. 3120, 3121" /></div>
            <div className="space-y-2"><Label htmlFor="own-agencies">Our agency name(s)</Label><Input id="own-agencies" value={ownAgencyNames} onChange={(e) => setOwnAgencyNames(e.target.value)} placeholder="e.g. Batlokoa Financial Service" /></div>
            <div className="space-y-2"><Label htmlFor="booking-lead">Booking opens before expiry (months)</Label><Input id="booking-lead" type="number" min={0} max={60} value={bookingLeadMonths} onChange={(e) => setBookingLeadMonths(Number(e.target.value))} /></div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>2. Paste CDAS deductions</CardTitle><CardDescription>The employee&apos;s raw CDAS text is analyzed but is not stored when you save monitoring.</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <Textarea value={rawText} onChange={(e) => setRawText(e.target.value)} placeholder="Paste the employee CDAS deduction rows here..." className="min-h-44 font-mono text-sm" />
            <div className="flex flex-wrap gap-2"><LoadingButton loading={loading} loadingText="Analyzing..." onClick={analyze}><CheckCircle2 className="h-4 w-4" />Analyze booking</LoadingButton><Button variant="outline" onClick={() => setRawText(SAMPLE_TEXT)}>Load sample</Button><Button variant="ghost" onClick={() => { setRawText(""); setResult(null); setError(""); }}><RotateCcw className="mr-2 h-4 w-4" />Clear</Button></div>
          </CardContent>
        </Card>

        {result && <div className="space-y-5" id="cdas-booking-report">
          <Card>
            <CardHeader><div className="flex flex-wrap items-center justify-between gap-3"><div><CardDescription>Recommendation</CardDescription><CardTitle className="mt-1 text-2xl">{result.decision === "ALREADY_BOOKED" ? "Already booked by us" : result.decision === "BOOK_NOW" ? "Book now" : `Next booking: ${monthLabel(result.next_possible_booking_date)}`}</CardTitle></div><Badge>{result.decision.replaceAll("_", " ")}</Badge></div></CardHeader>
            <CardContent><p className="text-sm text-muted-foreground">{result.decision_message}</p></CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Card><CardHeader className="pb-2"><CardDescription>Total active</CardDescription><CardTitle>{money(result.total_monthly_deductions)}</CardTitle></CardHeader></Card>
            <Card><CardHeader className="pb-2"><CardDescription>Booked with us</CardDescription><CardTitle>{money(result.own_monthly_deductions)}</CardTitle></CardHeader></Card>
            <Card><CardHeader className="pb-2"><CardDescription>Other agencies</CardDescription><CardTitle>{money(result.competitor_monthly_deductions)}</CardTitle></CardHeader></Card>
            <Card><CardHeader className="pb-2"><CardDescription>Booking rule</CardDescription><CardTitle>{result.booking_lead_months} months</CardTitle></CardHeader></Card>
          </div>

          {result.opportunity && result.own_bookings.length === 0 && <Card>
            <CardHeader><CardTitle>3. Save & monitor this opportunity</CardTitle><CardDescription>Only the parsed booking details below are saved. Enter a client name so staff know who to contact.</CardDescription></CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><div><div className="text-xs text-muted-foreground">Agency</div><div className="font-medium">{result.opportunity.agency_name}</div></div><div><div className="text-xs text-muted-foreground">Deduction</div><div className="font-medium">{money(result.opportunity.deduction_amount)}</div></div><div><div className="text-xs text-muted-foreground">Expiry</div><div className="font-medium">{monthLabel(result.opportunity.expiry_date)}</div></div><div><div className="text-xs text-muted-foreground">Booking opens</div><div className="font-medium">{dateLabel(result.opportunity.booking_open_date)}</div></div></div>
              <div className="grid gap-4 md:grid-cols-2"><div className="space-y-2"><Label htmlFor="client-name">Client name</Label><Input id="client-name" value={clientName} onChange={(e) => setClientName(e.target.value)} placeholder="Employee / borrower full name" /></div><div className="space-y-2"><Label htmlFor="client-reference">Client reference (optional)</Label><Input id="client-reference" value={clientReference} onChange={(e) => setClientReference(e.target.value)} placeholder="ID, payroll or internal reference" /></div></div>
              <LoadingButton loading={saving} loadingText="Saving monitor..." onClick={saveOpportunity}><Save className="h-4 w-4" />Save & Monitor</LoadingButton>
            </CardContent>
          </Card>}

          <Card><CardHeader><div className="flex flex-wrap items-center justify-between gap-2"><div><CardTitle>Deduction report</CardTitle><CardDescription>Every recognized deduction and its calculated booking window.</CardDescription></div><div className="flex gap-2 print:hidden"><Button variant="outline" onClick={() => window.print()}><Printer className="mr-2 h-4 w-4" />Print</Button><Button variant="outline" onClick={exportCsv}><Download className="mr-2 h-4 w-4" />CSV</Button></div></div></CardHeader><CardContent className="overflow-x-auto p-0"><Table><TableHeader><TableRow><TableHead>Item</TableHead><TableHead>Agency</TableHead><TableHead className="text-right">Deduction</TableHead><TableHead>Expiry</TableHead><TableHead>Reference</TableHead><TableHead>Booking opens</TableHead><TableHead>Result</TableHead></TableRow></TableHeader><TableBody>{result.deductions.map((row) => <TableRow key={`${row.item_code}-${row.reference_no}-${row.expiry_date}`}><TableCell className="font-medium">{row.item_code}</TableCell><TableCell>{row.agency_name}</TableCell><TableCell className="text-right">{money(row.deduction_amount)}</TableCell><TableCell>{monthLabel(row.expiry_date)}</TableCell><TableCell>{row.reference_no || "—"}</TableCell><TableCell>{dateLabel(row.booking_open_date)}</TableCell><TableCell><Badge variant="outline">{rowResult(row)}</Badge></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>
        </div>}
      </div>}

      {activeTab === "upcoming" && <div className="space-y-4"><Alert><BellRing className="h-4 w-4" /><AlertTitle>Upcoming booking watch</AlertTitle><AlertDescription>Rows marked Alerting are inside the 3-day warning period. LoanHub will keep creating one reminder per day until booking is completed.</AlertDescription></Alert>{monitorCards(groups.upcoming, "No upcoming CDAS booking opportunities are being monitored yet.")}</div>}
      {activeTab === "book-now" && <div className="space-y-4"><Alert><BellRing className="h-4 w-4" /><AlertTitle>Ready for booking</AlertTitle><AlertDescription>These clients have reached the company booking window. Keep them here until the booking is actually done.</AlertDescription></Alert>{monitorCards(groups.bookNow, "No monitored clients are ready to book right now.", true)}</div>}
      {activeTab === "booked" && monitorCards(groups.booked, "No monitored CDAS opportunities have been marked Booked yet.")}
    </div>
  );
}
