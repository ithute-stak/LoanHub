"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, BellRing, CalendarClock, CheckCircle2, ClipboardPaste, RefreshCw, Save, Search } from "lucide-react";

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
import type { CdasBookingAnalysis, CdasBookingOpportunity } from "@/types/cdasBooking";

const SETTINGS_KEY = "loanhub.cdasBooking.settings.v1";
const SAMPLE_TEXT = `| | 2561 | Lesana Lesotho Limited | | M 3,942.08 | 2026-Mar | 2027-Aug | 1000093084 | Active |\n| | 2595 | First National Bank of Lesotho | | M 21,011.86 | 2024-Jan | 2028-Dec | FNB LOAN 62592936979 | Active |`;
type Tab = "analyze" | "upcoming" | "book-now" | "booked";

function splitList(value: string) { return value.split(/[\n,;]+/).map((v) => v.trim()).filter(Boolean); }
function money(value: number) { return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }
function dateLabel(value?: string | null) { if (!value) return "—"; const d = new Date(`${value.slice(0,10)}T00:00:00`); return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" }); }

export default function CdasBookingPage() {
  const [tab, setTab] = useState<Tab>("analyze");
  const [rawText, setRawText] = useState("");
  const [clientName, setClientName] = useState("");
  const [clientReference, setClientReference] = useState("");
  const [ownItemCodes, setOwnItemCodes] = useState("");
  const [ownAgencyNames, setOwnAgencyNames] = useState("");
  const [bookingLeadMonths, setBookingLeadMonths] = useState(6);
  const [alertLeadDays, setAlertLeadDays] = useState(3);
  const [result, setResult] = useState<CdasBookingAnalysis | null>(null);
  const [items, setItems] = useState<CdasBookingOpportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    try { const stored = localStorage.getItem(SETTINGS_KEY); if (stored) { const s = JSON.parse(stored); setOwnItemCodes(s.ownItemCodes || ""); setOwnAgencyNames(s.ownAgencyNames || ""); setBookingLeadMonths(Number(s.bookingLeadMonths ?? 6)); } } catch {}
  }, []);
  useEffect(() => { localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ownItemCodes, ownAgencyNames, bookingLeadMonths })); }, [ownItemCodes, ownAgencyNames, bookingLeadMonths]);

  const refresh = useCallback(async () => { try { setItems((await cdasBookingApi.listOpportunities()).items); } catch {} }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const upcoming = useMemo(() => items.filter((i) => i.state === "UPCOMING"), [items]);
  const bookNow = useMemo(() => items.filter((i) => i.state === "BOOK_NOW"), [items]);
  const booked = useMemo(() => items.filter((i) => i.state === "BOOKED"), [items]);

  const payload = () => ({ raw_text: rawText, booking_lead_months: Math.max(0, Math.min(60, Number(bookingLeadMonths) || 0)), own_item_codes: splitList(ownItemCodes), own_agency_names: splitList(ownAgencyNames) });

  async function analyze() {
    if (!rawText.trim()) { setError("Paste the CDAS deduction text first."); return; }
    setLoading(true); setError("");
    try { setResult(await cdasBookingApi.analyze(payload())); }
    catch (e: any) { setError(e?.response?.data?.detail || "CDAS text could not be analyzed."); }
    finally { setLoading(false); }
  }

  async function saveAndMonitor() {
    if (!rawText.trim()) return;
    setSaving(true); setError("");
    try {
      await cdasBookingApi.saveOpportunity({ ...payload(), client_name: clientName.trim() || undefined, client_reference: clientReference.trim() || undefined, alert_lead_days: alertLeadDays });
      await refresh(); setTab("upcoming");
    } catch (e: any) { setError(e?.response?.data?.detail || "Could not save this CDAS analysis."); }
    finally { setSaving(false); }
  }

  async function markBooked(id: string) { await cdasBookingApi.markBooked(id); await refresh(); }

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "analyze", label: "Analyze" },
    { id: "upcoming", label: "Upcoming", count: upcoming.length },
    { id: "book-now", label: "Book Now", count: bookNow.length },
    { id: "booked", label: "Booked", count: booked.length },
  ];

  function Queue({ data, allowBook }: { data: CdasBookingOpportunity[]; allowBook?: boolean }) {
    if (!data.length) return <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">No records in this queue.</CardContent></Card>;
    return <div className="grid gap-4 lg:grid-cols-2">{data.map((item) => <Card key={item.id} className={item.state === "BOOK_NOW" ? "border-primary/40" : ""}>
      <CardHeader className="pb-3"><div className="flex items-start justify-between gap-3"><div><CardTitle className="text-lg">{item.client_name || item.client_reference || "CDAS client"}</CardTitle><CardDescription>{item.opportunity_agency_name || "No competing agency"} {item.opportunity_reference_no ? `• ${item.opportunity_reference_no}` : ""}</CardDescription></div><Badge variant={item.state === "BOOK_NOW" ? "default" : "secondary"}>{item.state.replaceAll("_", " ")}</Badge></div></CardHeader>
      <CardContent className="space-y-4"><div className="grid grid-cols-2 gap-3 text-sm"><div><div className="text-muted-foreground">Deduction</div><div className="font-semibold">{money(item.opportunity_deduction_amount)}</div></div><div><div className="text-muted-foreground">Booking opens</div><div className="font-semibold">{dateLabel(item.booking_open_date)}</div></div><div><div className="text-muted-foreground">Alerts start</div><div>{dateLabel(item.alert_start_date)}</div></div><div><div className="text-muted-foreground">Expiry</div><div>{dateLabel(item.opportunity_expiry_date)}</div></div></div>
      {item.state === "UPCOMING" && <Alert><BellRing className="h-4 w-4"/><AlertTitle>{item.days_until_booking} day(s) until booking</AlertTitle><AlertDescription>Daily alerts begin {item.alert_lead_days} day(s) before the booking window opens.</AlertDescription></Alert>}
      {allowBook && <Button className="w-full" onClick={() => void markBooked(item.id)}><CheckCircle2 className="mr-2 h-4 w-4"/>Mark booking complete</Button>}
      </CardContent></Card>)}</div>;
  }

  return <div className="space-y-6 pb-10">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><div className="flex items-center gap-2"><CalendarClock className="h-6 w-6"/><h1 className="text-2xl font-semibold tracking-tight">CDAS Booking Centre</h1></div><p className="mt-1 max-w-3xl text-sm text-muted-foreground">Analyze CDAS deductions, save opportunities, and keep reminding the company until each client is booked.</p></div><Button variant="outline" onClick={() => void refresh()}><RefreshCw className="mr-2 h-4 w-4"/>Refresh</Button></div>

    <div className="flex flex-wrap gap-2 rounded-xl border bg-muted/30 p-2">{tabs.map((t) => <Button key={t.id} variant={tab === t.id ? "default" : "ghost"} onClick={() => setTab(t.id)}>{t.label}{t.count !== undefined && <Badge variant="secondary" className="ml-2">{t.count}</Badge>}</Button>)}</div>

    {tab === "analyze" && <div className="space-y-5">
      <Alert><BellRing className="h-4 w-4"/><AlertTitle>Automatic booking reminder</AlertTitle><AlertDescription>When you save an analysis, LoanHub starts monitoring it. By default the company is warned 3 days before the calculated booking-open date and reminded every day until the booking is marked complete.</AlertDescription></Alert>
      <Card><CardHeader><CardTitle>Client & booking rules</CardTitle><CardDescription>Client details help staff recognize the opportunity when the alert appears.</CardDescription></CardHeader><CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"><div className="space-y-2"><Label>Client name</Label><Input value={clientName} onChange={(e)=>setClientName(e.target.value)} placeholder="Employee/client name"/></div><div className="space-y-2"><Label>Client reference</Label><Input value={clientReference} onChange={(e)=>setClientReference(e.target.value)} placeholder="Employee / payroll / internal ref"/></div><div className="space-y-2"><Label>Alert before booking (days)</Label><Input type="number" min={0} max={31} value={alertLeadDays} onChange={(e)=>setAlertLeadDays(Number(e.target.value))}/></div><div className="space-y-2"><Label>Our CDAS item code(s)</Label><Input value={ownItemCodes} onChange={(e)=>setOwnItemCodes(e.target.value)} placeholder="e.g. 3120, 3121"/></div><div className="space-y-2"><Label>Our agency name(s)</Label><Input value={ownAgencyNames} onChange={(e)=>setOwnAgencyNames(e.target.value)} placeholder="e.g. Batlokoa Financial Service"/></div><div className="space-y-2"><Label>Booking opens before expiry (months)</Label><Input type="number" min={0} max={60} value={bookingLeadMonths} onChange={(e)=>setBookingLeadMonths(Number(e.target.value))}/></div></CardContent></Card>
      <Card><CardHeader><CardTitle>Paste CDAS deductions</CardTitle></CardHeader><CardContent className="space-y-4"><Textarea className="min-h-48 font-mono text-sm" value={rawText} onChange={(e)=>setRawText(e.target.value)} placeholder="Paste copied CDAS deduction rows here..."/>{error && <Alert variant="destructive"><AlertTitle>Action failed</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}<div className="flex flex-wrap gap-2"><LoadingButton loading={loading} loadingText="Analyzing..." onClick={analyze}><Search className="h-4 w-4"/>Analyze</LoadingButton><Button variant="outline" onClick={()=>setRawText(SAMPLE_TEXT)}><ClipboardPaste className="mr-2 h-4 w-4"/>Load sample</Button></div></CardContent></Card>
      {result && <Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardDescription>Recommendation</CardDescription><CardTitle className="mt-1 text-2xl">{result.decision === "REVIEW_REQUIRED" ? "Review CDAS data" : result.decision === "ALREADY_BOOKED" ? "Already booked by us" : result.decision === "BOOK_NOW" ? "Book now" : `Next booking: ${dateLabel(result.next_possible_booking_date)}`}</CardTitle></div><Badge variant={result.decision === "REVIEW_REQUIRED" ? "outline" : "default"} className={result.decision === "REVIEW_REQUIRED" ? "border-amber-500 text-amber-700 dark:text-amber-300" : ""}>{result.decision.replaceAll("_", " ")}</Badge></div></CardHeader><CardContent className="space-y-5"><p className="text-sm text-muted-foreground">{result.decision_message}</p>
      {result.data_quality_issue_count > 0 && <Alert className="border-amber-500/50 bg-amber-50/60 dark:bg-amber-950/20"><AlertTriangle className="h-4 w-4 text-amber-600"/><AlertTitle>{result.data_quality_issue_count} CDAS date conflict{result.data_quality_issue_count === 1 ? "" : "s"} detected</AlertTitle><AlertDescription>LoanHub excluded {money(result.excluded_monthly_deductions)} from booking calculations because the effective date is later than the expiry date. Verify or correct the highlighted CDAS row before relying on it.</AlertDescription></Alert>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Valid active deductions</div><div className="font-semibold">{money(result.total_monthly_deductions)}</div></div><div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Ours</div><div className="font-semibold">{money(result.own_monthly_deductions)}</div></div><div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Other agencies</div><div className="font-semibold">{money(result.competitor_monthly_deductions)}</div></div>{result.data_quality_issue_count > 0 && <div className="rounded-lg border border-amber-500/40 p-3"><div className="text-xs text-muted-foreground">Excluded / needs review</div><div className="font-semibold text-amber-700 dark:text-amber-300">{money(result.excluded_monthly_deductions)}</div></div>}</div>
      <div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Agency</TableHead><TableHead>Reference</TableHead><TableHead>Deduction</TableHead><TableHead>Effective</TableHead><TableHead>Expiry</TableHead><TableHead>Quality</TableHead><TableHead>Booking opens</TableHead></TableRow></TableHeader><TableBody>{result.deductions.map((r)=><TableRow key={`${r.item_code}-${r.reference_no}`} className={r.data_quality_status === "DATE_CONFLICT" ? "bg-amber-50/70 dark:bg-amber-950/20" : ""}><TableCell><div>{r.agency_name}</div><div className="text-xs text-muted-foreground">Item {r.item_code}</div></TableCell><TableCell>{r.reference_no}</TableCell><TableCell>{money(r.deduction_amount)}</TableCell><TableCell>{dateLabel(r.effective_date)}</TableCell><TableCell>{dateLabel(r.expiry_date)}</TableCell><TableCell>{r.data_quality_status === "DATE_CONFLICT" ? <div className="max-w-64"><Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-300">Date conflict</Badge><div className="mt-1 text-xs text-muted-foreground">{r.data_quality_message}</div></div> : <Badge variant="secondary">Valid</Badge>}</TableCell><TableCell>{r.booking_open_date ? dateLabel(r.booking_open_date) : <span className="text-muted-foreground">Excluded</span>}</TableCell></TableRow>)}</TableBody></Table></div>
      {result.decision === "REVIEW_REQUIRED" ? <Button disabled><AlertTriangle className="mr-2 h-4 w-4"/>Correct CDAS data before monitoring</Button> : <LoadingButton loading={saving} loadingText="Saving..." onClick={saveAndMonitor}><Save className="h-4 w-4"/>Save & monitor until booked</LoadingButton>}
      </CardContent></Card>}
    </div>}
    {tab === "upcoming" && <Queue data={upcoming}/>} {tab === "book-now" && <Queue data={bookNow} allowBook/>} {tab === "booked" && <Queue data={booked}/>} 
  </div>;
}