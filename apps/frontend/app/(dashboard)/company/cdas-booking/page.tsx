"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ClipboardEvent } from "react";
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
const CDAS_CLIPBOARD_LABELS = ["Compulsory Retirement Date", "Early Retirement Date", "Max Available Deduction Amount", "Date of Birth", "Employee No", "Joining Date", "End Date", "Surname", "Employer", "Gender", "NID", "Name"] as const;
type Tab = "analyze" | "upcoming" | "book-now" | "booked";

function splitList(value: string) { return value.split(/[\n,;]+/).map((v) => v.trim()).filter(Boolean); }
function normaliseListValue(value: string) { return value.trim().toLowerCase().replace(/\s+/g, " "); }
function mergeList(existing: string, values: Array<string | null | undefined>) {
  const merged = [...values.map((value) => value?.trim() || "").filter(Boolean), ...splitList(existing)];
  const unique = new Map<string, string>();
  for (const value of merged) if (!unique.has(normaliseListValue(value))) unique.set(normaliseListValue(value), value);
  return Array.from(unique.values()).join(", ");
}
function normaliseClipboardLabel(value: string) { return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " "); }
function detectClipboardLabel(candidates: Array<string | null | undefined>) {
  for (const candidate of candidates) {
    if (!candidate) continue;
    const key = normaliseClipboardLabel(candidate);
    for (const label of CDAS_CLIPBOARD_LABELS) {
      const labelKey = normaliseClipboardLabel(label);
      if (key === labelKey || key.startsWith(`${labelKey} `) || key.endsWith(` ${labelKey}`)) return label;
    }
  }
  return null;
}
function extractClipboardFormText(html: string) {
  if (!html || typeof DOMParser === "undefined") return "";
  const doc = new DOMParser().parseFromString(html, "text/html");
  const labels = Array.from(doc.querySelectorAll("label"));
  const recovered = new Map<string, string>();

  for (const field of Array.from(doc.querySelectorAll("input, textarea, select"))) {
    let value = "";
    if (field instanceof HTMLSelectElement) value = field.selectedOptions[0]?.textContent?.trim() || field.value.trim();
    else value = (field as HTMLInputElement | HTMLTextAreaElement).value?.trim() || field.getAttribute("value")?.trim() || "";
    if (!value || /^search$/i.test(value)) continue;

    const id = field.getAttribute("id");
    const explicitLabel = id ? labels.find((label) => label.getAttribute("for") === id)?.textContent : null;
    const label = detectClipboardLabel([
      explicitLabel,
      field.closest("label")?.textContent,
      field.getAttribute("aria-label"),
      field.getAttribute("placeholder"),
      field.getAttribute("name"),
      field.getAttribute("id"),
      field.parentElement?.textContent,
    ]);
    if (label && !recovered.has(label)) recovered.set(label, value);
  }

  return Array.from(recovered.entries()).map(([label, value]) => `${label}: ${value}`).join("\n");
}
function money(value: number) { return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }
function dateLabel(value?: string | null) { if (!value) return "—"; const d = new Date(`${value.slice(0,10)}T00:00:00`); return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" }); }

function CapacitySummary({ result }: { result: CdasBookingAnalysis }) {
  const capacity = result.capacity;
  const assessedAmount = capacity.max_available_after_selected_deductions ?? capacity.max_available_deduction_amount;
  if (capacity.status === "UNKNOWN" || assessedAmount === null) return null;

  const current = capacity.max_available_deduction_amount;
  const afterSelected = capacity.max_available_after_selected_deductions;
  const isNegative = capacity.status === "NEGATIVE_AVAILABLE";
  const isZero = capacity.status === "NO_HEADROOM";

  const title = isNegative
    ? `No deduction headroom — over limit by ${money(capacity.shortfall_amount)}`
    : isZero
      ? "No deduction headroom available"
      : `${money(assessedAmount)} monthly deduction headroom available`;

  const message = isNegative
    ? `CDAS reports ${money(assessedAmount)} as the available deduction amount. Because it is negative, this does not mean money is available — it means the payroll deduction limit is exceeded by ${money(capacity.shortfall_amount)}. Do not treat the client as having room for another deduction unless a consolidation calculation becomes positive.`
    : isZero
      ? "CDAS reports exactly M 0.00 available. LoanHub treats this as no additional payroll deduction headroom."
      : `CDAS reports a positive available amount of ${money(assessedAmount)}. LoanHub treats this as payroll deduction headroom only; it is not automatic loan approval and other lending rules still apply.`;

  return <div className="space-y-3">
    <Alert variant={isNegative ? "destructive" : "default"} className={!isNegative && isZero ? "border-amber-500/50 bg-amber-50/60 dark:bg-amber-950/20" : !isNegative ? "border-emerald-500/40 bg-emerald-50/50 dark:bg-emerald-950/20" : ""}>
      {isNegative || isZero ? <AlertTriangle className="h-4 w-4"/> : <CheckCircle2 className="h-4 w-4"/>}
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Current CDAS max available</div><div className="font-semibold">{current === null ? "—" : money(current)}</div></div>
      <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">After selected deductions</div><div className="font-semibold">{afterSelected === null ? "Not supplied" : money(afterSelected)}</div></div>
      <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">LoanHub interpretation</div><div className="font-semibold">{isNegative ? `Over limit by ${money(capacity.shortfall_amount)}` : isZero ? "No headroom" : `${money(assessedAmount)} headroom`}</div></div>
    </div>
    {afterSelected !== null && current !== null && afterSelected !== current && <p className="text-xs text-muted-foreground">For consolidation, LoanHub uses the “after selected deductions” amount as the capacity assessment because it reflects the deductions being removed.</p>}
  </div>;
}

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

  function handleCdasPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const html = event.clipboardData.getData("text/html");
    const recovered = extractClipboardFormText(html);
    if (!recovered) return;

    event.preventDefault();
    const plain = event.clipboardData.getData("text/plain");
    const paste = [plain, recovered].filter(Boolean).join("\n");
    const start = event.currentTarget.selectionStart ?? rawText.length;
    const end = event.currentTarget.selectionEnd ?? start;
    setRawText((current) => `${current.slice(0, start)}${paste}${current.slice(end)}`);
  }

  function autoFillBookingRules(analysis: CdasBookingAnalysis) {
    const parsedName = analysis.profile.full_name?.trim();
    const parsedReference = analysis.profile.employee_no?.trim() || analysis.profile.nid?.trim();
    if (parsedName) setClientName(parsedName);
    if (parsedReference) setClientReference(parsedReference);

    const detectedAgency = analysis.application_context.new_deduction_agency_name?.trim()
      || analysis.application_context.current_cdas_agency_name?.trim();
    const detectedAgencyKey = detectedAgency ? normaliseListValue(detectedAgency) : "";
    const ownRows = analysis.deductions.filter((row) =>
      row.is_own_booking || (detectedAgencyKey && normaliseListValue(row.agency_name) === detectedAgencyKey)
    );

    setOwnItemCodes((current) => mergeList(current, ownRows.map((row) => row.item_code)));
    setOwnAgencyNames((current) => mergeList(current, [detectedAgency, ...ownRows.map((row) => row.agency_name)]));
    setBookingLeadMonths(analysis.booking_lead_months);
  }

  async function analyze() {
    if (!rawText.trim()) { setError("Paste the CDAS deduction text first."); return; }
    setLoading(true); setError("");
    try {
      const analysis = await cdasBookingApi.analyze(payload());
      autoFillBookingRules(analysis);
      setResult(analysis);
    }
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
      <Card><CardHeader><CardTitle>Client & booking rules</CardTitle><CardDescription>LoanHub auto-fills these fields from copied CDAS text and, when available, the copied CDAS form controls. Staff can still edit or correct them before saving.</CardDescription></CardHeader><CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"><div className="space-y-2"><Label>Client name</Label><Input value={clientName} onChange={(e)=>setClientName(e.target.value)} placeholder="Employee/client name"/></div><div className="space-y-2"><Label>Client reference</Label><Input value={clientReference} onChange={(e)=>setClientReference(e.target.value)} placeholder="Employee / payroll / internal ref"/></div><div className="space-y-2"><Label>Alert before booking (days)</Label><Input type="number" min={0} max={31} value={alertLeadDays} onChange={(e)=>setAlertLeadDays(Number(e.target.value))}/></div><div className="space-y-2"><Label>Our CDAS item code(s)</Label><Input value={ownItemCodes} onChange={(e)=>setOwnItemCodes(e.target.value)} placeholder="e.g. 3120, 3121"/></div><div className="space-y-2"><Label>Our agency name(s)</Label><Input value={ownAgencyNames} onChange={(e)=>setOwnAgencyNames(e.target.value)} placeholder="e.g. Batlokoa Financial Service"/></div><div className="space-y-2"><Label>Booking opens before expiry (months)</Label><Input type="number" min={0} max={60} value={bookingLeadMonths} onChange={(e)=>setBookingLeadMonths(Number(e.target.value))}/></div></CardContent></Card>
      <Card><CardHeader><CardTitle>Paste CDAS deductions</CardTitle></CardHeader><CardContent className="space-y-4"><Textarea className="min-h-48 font-mono text-sm" value={rawText} onChange={(e)=>setRawText(e.target.value)} onPaste={handleCdasPaste} placeholder="Paste copied CDAS deduction rows here..."/>{error && <Alert variant="destructive"><AlertTitle>Action failed</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}<div className="flex flex-wrap gap-2"><LoadingButton loading={loading} loadingText="Analyzing..." onClick={analyze}><Search className="h-4 w-4"/>Analyze</LoadingButton><Button variant="outline" onClick={()=>setRawText(SAMPLE_TEXT)}><ClipboardPaste className="mr-2 h-4 w-4"/>Load sample</Button></div></CardContent></Card>
      {result && <Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardDescription>Recommendation</CardDescription><CardTitle className="mt-1 text-2xl">{result.decision === "REVIEW_REQUIRED" ? "Review CDAS data" : result.decision === "ALREADY_BOOKED" ? "Already booked by us" : result.decision === "BOOK_NOW" ? "Book now" : `Next booking: ${dateLabel(result.next_possible_booking_date)}`}</CardTitle></div><Badge variant={result.decision === "REVIEW_REQUIRED" ? "outline" : "default"} className={result.decision === "REVIEW_REQUIRED" ? "border-amber-500 text-amber-700 dark:text-amber-300" : ""}>{result.decision.replaceAll("_", " ")}</Badge></div></CardHeader><CardContent className="space-y-5"><p className="text-sm text-muted-foreground">{result.decision_message}</p>
      <CapacitySummary result={result}/>
      {result.data_quality_issue_count > 0 && <Alert className="border-amber-500/50 bg-amber-50/60 dark:bg-amber-950/20"><AlertTriangle className="h-4 w-4 text-amber-600"/><AlertTitle>{result.data_quality_issue_count} CDAS data issue{result.data_quality_issue_count === 1 ? "" : "s"} detected</AlertTitle><AlertDescription>LoanHub excluded {money(result.excluded_monthly_deductions)} from booking-window calculations because one or more Active rows have missing or contradictory expiry information. The amounts remain in the reported financial totals.</AlertDescription></Alert>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Reported active deductions</div><div className="font-semibold">{money(result.reported_active_monthly_deductions)}</div></div><div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Booking-valid deductions</div><div className="font-semibold">{money(result.total_monthly_deductions)}</div></div><div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Other agencies</div><div className="font-semibold">{money(result.competitor_monthly_deductions)}</div></div>{result.data_quality_issue_count > 0 && <div className="rounded-lg border border-amber-500/40 p-3"><div className="text-xs text-muted-foreground">Excluded / needs review</div><div className="font-semibold text-amber-700 dark:text-amber-300">{money(result.excluded_monthly_deductions)}</div></div>}</div>
      <div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Agency</TableHead><TableHead>Reference</TableHead><TableHead>Deduction</TableHead><TableHead>Effective</TableHead><TableHead>Expiry</TableHead><TableHead>Quality</TableHead><TableHead>Booking opens</TableHead></TableRow></TableHeader><TableBody>{result.deductions.map((r)=><TableRow key={`${r.item_code}-${r.reference_no}`} className={r.data_quality_status !== "OK" ? "bg-amber-50/70 dark:bg-amber-950/20" : ""}><TableCell><div>{r.agency_name}</div><div className="text-xs text-muted-foreground">Item {r.item_code}</div></TableCell><TableCell>{r.reference_no}</TableCell><TableCell>{money(r.deduction_amount)}</TableCell><TableCell>{dateLabel(r.effective_date)}</TableCell><TableCell>{dateLabel(r.expiry_date)}</TableCell><TableCell>{r.data_quality_status === "DATE_CONFLICT" ? <div className="max-w-64"><Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-300">Date conflict</Badge><div className="mt-1 text-xs text-muted-foreground">{r.data_quality_message}</div></div> : r.data_quality_status === "MISSING_EXPIRY" ? <div className="max-w-64"><Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-300">Missing expiry</Badge><div className="mt-1 text-xs text-muted-foreground">{r.data_quality_message}</div></div> : <Badge variant="secondary">Valid</Badge>}</TableCell><TableCell>{r.booking_open_date ? dateLabel(r.booking_open_date) : <span className="text-muted-foreground">Excluded</span>}</TableCell></TableRow>)}</TableBody></Table></div>
      {result.decision === "REVIEW_REQUIRED" ? <Button disabled><AlertTriangle className="mr-2 h-4 w-4"/>Correct CDAS data before monitoring</Button> : <LoadingButton loading={saving} loadingText="Saving..." onClick={saveAndMonitor}><Save className="h-4 w-4"/>Save & monitor until booked</LoadingButton>}
      </CardContent></Card>}
    </div>}
    {tab === "upcoming" && <Queue data={upcoming}/>} {tab === "book-now" && <Queue data={bookNow} allowBook/>} {tab === "booked" && <Queue data={booked}/>} 
  </div>;
}