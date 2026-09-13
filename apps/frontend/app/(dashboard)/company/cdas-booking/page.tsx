"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CalendarClock,
  CheckCircle2,
  ClipboardPaste,
  Download,
  Printer,
  RotateCcw,
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
import type { CdasBookingAnalysis, CdasDeductionAnalysis } from "@/types/cdasBooking";

const SETTINGS_KEY = "loanhub.cdasBooking.settings.v1";

const SAMPLE_TEXT = `| | 2561 | Lesana Lesotho Limited | | M 3,942.08 | 2026-Mar | 2027-Aug | 1000093084 | Active |
| | 2595 | First National Bank of Lesotho | | M 21,011.86 | 2024-Jan | 2028-Dec | FNB LOAN 62592936979 | Active |`;

type SavedSettings = {
  bookingLeadMonths: number;
  ownItemCodes: string;
  ownAgencyNames: string;
};

function money(value: number) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function monthLabel(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-ZA", { month: "short", year: "numeric" });
}

function splitList(value: string) {
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
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
  const [rawText, setRawText] = useState("");
  const [ownItemCodes, setOwnItemCodes] = useState("");
  const [ownAgencyNames, setOwnAgencyNames] = useState("");
  const [bookingLeadMonths, setBookingLeadMonths] = useState(6);
  const [result, setResult] = useState<CdasBookingAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SETTINGS_KEY);
      if (!stored) return;
      const settings = JSON.parse(stored) as Partial<SavedSettings>;
      if (typeof settings.bookingLeadMonths === "number") setBookingLeadMonths(settings.bookingLeadMonths);
      if (typeof settings.ownItemCodes === "string") setOwnItemCodes(settings.ownItemCodes);
      if (typeof settings.ownAgencyNames === "string") setOwnAgencyNames(settings.ownAgencyNames);
    } catch {
      // Corrupt local preferences should never prevent the analyzer from opening.
    }
  }, []);

  useEffect(() => {
    const settings: SavedSettings = { bookingLeadMonths, ownItemCodes, ownAgencyNames };
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }, [bookingLeadMonths, ownItemCodes, ownAgencyNames]);

  const primaryOwnBooking = result?.own_bookings[0] ?? null;
  const recommendation = useMemo(() => {
    if (!result) return null;
    if (result.decision === "ALREADY_BOOKED") {
      return {
        title: "Already booked by us",
        detail: primaryOwnBooking
          ? `${primaryOwnBooking.elapsed_months} month(s) since ${monthLabel(primaryOwnBooking.effective_date)}; ${primaryOwnBooking.months_to_expiry} month(s) to expiry.`
          : result.decision_message,
      };
    }
    if (result.decision === "BOOK_NOW") {
      return { title: "Book now", detail: result.decision_message };
    }
    return {
      title: `Next booking: ${monthLabel(result.next_possible_booking_date)}`,
      detail: result.decision_message,
    };
  }, [primaryOwnBooking, result]);

  async function analyze() {
    setError("");
    setResult(null);
    if (!rawText.trim()) {
      setError("Paste the CDAS deduction text first.");
      return;
    }
    setLoading(true);
    try {
      const response = await cdasBookingApi.analyze({
        raw_text: rawText,
        booking_lead_months: Math.max(0, Math.min(60, Number(bookingLeadMonths) || 0)),
        own_item_codes: splitList(ownItemCodes),
        own_agency_names: splitList(ownAgencyNames),
      });
      setResult(response);
    } catch (caught: unknown) {
      const message =
        typeof caught === "object" && caught && "response" in caught
          ? ((caught as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "CDAS text could not be analyzed.")
          : "CDAS text could not be analyzed.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function exportCsv() {
    if (!result) return;
    const summary = [
      ["Analysis date", result.as_of],
      ["Decision", result.decision],
      ["Recommendation", result.decision_message],
      ["Next possible booking", result.next_possible_booking_date ?? ""],
      ["Booking lead months", result.booking_lead_months],
      ["Total monthly deductions", result.total_monthly_deductions],
      ["Our monthly deductions", result.own_monthly_deductions],
      ["Other agencies monthly deductions", result.competitor_monthly_deductions],
    ];
    const headers = [
      "Item Code",
      "Agency",
      "Deduction Amount",
      "Effective Month",
      "Expiry Month",
      "Reference",
      "Status",
      "Our Booking",
      "Months Elapsed",
      "Months To Expiry",
      "Scheduled Deduction Months",
      "Booking Opens",
      "Result",
    ];
    const lines = [
      "CDAS BOOKING ANALYSIS",
      ...summary.map((row) => row.map(csvCell).join(",")),
      "",
      headers.map(csvCell).join(","),
      ...result.deductions.map((row) =>
        [
          row.item_code,
          row.agency_name,
          row.deduction_amount.toFixed(2),
          row.effective_date,
          row.expiry_date,
          row.reference_no,
          row.status,
          row.is_own_booking ? "Yes" : "No",
          row.elapsed_months,
          row.months_to_expiry,
          row.scheduled_deduction_months,
          row.booking_open_date,
          rowResult(row),
        ]
          .map(csvCell)
          .join(","),
      ),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `cdas-booking-analysis-${result.as_of}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function reset() {
    setRawText("");
    setResult(null);
    setError("");
  }

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ClipboardPaste className="h-5 w-5" aria-hidden />
            <h1 className="text-2xl font-semibold tracking-tight">CDAS Booking Analyzer</h1>
          </div>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Paste an employee&apos;s CDAS deductions to see whether your company already has the booking,
            how long it has been running, or the next month the client can enter your booking window.
          </p>
        </div>
        {result && (
          <div className="flex gap-2 print:hidden">
            <Button variant="outline" onClick={() => window.print()}>
              <Printer className="mr-2 h-4 w-4" /> Print report
            </Button>
            <Button variant="outline" onClick={exportCsv}>
              <Download className="mr-2 h-4 w-4" /> CSV
            </Button>
          </div>
        )}
      </div>

      <Alert className="print:hidden">
        <CalendarClock className="h-4 w-4" />
        <AlertTitle>Company booking rule</AlertTitle>
        <AlertDescription>
          The booking lead period is your company&apos;s rule, not a CDAS rule. The default is 6 months before
          the deduction expiry month and can be changed below.
        </AlertDescription>
      </Alert>

      <Card className="print:hidden">
        <CardHeader>
          <CardTitle>Analyzer settings</CardTitle>
          <CardDescription>
            Tell LoanHub which CDAS item codes or agency names belong to your company. These preferences are
            stored only in this browser for this first local version.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="own-item-codes">Our CDAS item code(s)</Label>
            <Input
              id="own-item-codes"
              value={ownItemCodes}
              onChange={(event) => setOwnItemCodes(event.target.value)}
              placeholder="e.g. 3120, 3121"
            />
            <p className="text-xs text-muted-foreground">Separate multiple codes with commas.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="own-agencies">Our agency name(s)</Label>
            <Input
              id="own-agencies"
              value={ownAgencyNames}
              onChange={(event) => setOwnAgencyNames(event.target.value)}
              placeholder="e.g. Batlokoa Financial Service"
            />
            <p className="text-xs text-muted-foreground">Useful if the agency name is more reliable than the item code.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="booking-lead">Booking opens before expiry (months)</Label>
            <Input
              id="booking-lead"
              type="number"
              min={0}
              max={60}
              value={bookingLeadMonths}
              onChange={(event) => setBookingLeadMonths(Number(event.target.value))}
            />
            <p className="text-xs text-muted-foreground">Example: 6 means an Aug 2027 expiry opens in Feb 2027.</p>
          </div>
        </CardContent>
      </Card>

      <Card className="print:hidden">
        <CardHeader>
          <CardTitle>Paste CDAS deductions</CardTitle>
          <CardDescription>
            Copy the deduction table from CDAS and paste it here. Markdown/table rows and normal text rows are supported.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={rawText}
            onChange={(event) => setRawText(event.target.value)}
            placeholder="Paste the employee CDAS deduction rows here..."
            className="min-h-48 font-mono text-sm"
          />
          {error && (
            <Alert variant="destructive">
              <AlertTitle>Could not analyze this CDAS text</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="flex flex-wrap gap-2">
            <LoadingButton loading={loading} loadingText="Analyzing..." onClick={analyze}>
              <CheckCircle2 className="h-4 w-4" /> Analyze booking
            </LoadingButton>
            <Button variant="outline" onClick={() => setRawText(SAMPLE_TEXT)}>
              Load sample
            </Button>
            <Button variant="ghost" onClick={reset}>
              <RotateCcw className="mr-2 h-4 w-4" /> Clear
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && recommendation && (
        <div className="space-y-6" id="cdas-booking-report">
          <div className="hidden print:block">
            <h1 className="text-2xl font-semibold">CDAS Booking Analysis Report</h1>
            <p className="text-sm">Analysis date: {result.as_of}</p>
          </div>

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardDescription>Booking recommendation</CardDescription>
                  <CardTitle className="mt-1 text-2xl">{recommendation.title}</CardTitle>
                </div>
                <Badge>{result.decision.replaceAll("_", " ")}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{recommendation.detail}</p>
              {result.decision === "WAIT_UNTIL" && result.next_possible_booking_date && (
                <div className="mt-4 rounded-lg border p-4">
                  <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Next possible booking</div>
                  <div className="mt-1 text-xl font-semibold">{monthLabel(result.next_possible_booking_date)}</div>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Total active deductions</CardDescription>
                <CardTitle>{money(result.total_monthly_deductions)}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Booked with us</CardDescription>
                <CardTitle>{money(result.own_monthly_deductions)}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Other agencies</CardDescription>
                <CardTitle>{money(result.competitor_monthly_deductions)}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Booking rule</CardDescription>
                <CardTitle>{result.booking_lead_months} months</CardTitle>
              </CardHeader>
            </Card>
          </div>

          {result.own_bookings.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Our existing booking</CardTitle>
                <CardDescription>Active CDAS deductions identified as belonging to your company.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                {result.own_bookings.map((row) => (
                  <div key={`${row.item_code}-${row.reference_no}`} className="rounded-lg border p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold">{row.agency_name}</div>
                        <div className="text-sm text-muted-foreground">Item {row.item_code} · {row.reference_no}</div>
                      </div>
                      <Badge>Our booking</Badge>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <div><span className="text-muted-foreground">Monthly:</span><br /><strong>{money(row.deduction_amount)}</strong></div>
                      <div><span className="text-muted-foreground">Running for:</span><br /><strong>{row.elapsed_months} months</strong></div>
                      <div><span className="text-muted-foreground">Effective:</span><br /><strong>{monthLabel(row.effective_date)}</strong></div>
                      <div><span className="text-muted-foreground">Expires:</span><br /><strong>{monthLabel(row.expiry_date)}</strong></div>
                      <div><span className="text-muted-foreground">To expiry:</span><br /><strong>{row.months_to_expiry} months</strong></div>
                      <div><span className="text-muted-foreground">Scheduled deduction months:</span><br /><strong>{row.scheduled_deduction_months}</strong></div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {result.opportunity && result.own_bookings.length === 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Next booking opportunity</CardTitle>
                <CardDescription>The active external deduction that reaches your booking window first.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div><div className="text-xs text-muted-foreground">Agency</div><div className="font-medium">{result.opportunity.agency_name}</div></div>
                  <div><div className="text-xs text-muted-foreground">Deduction</div><div className="font-medium">{money(result.opportunity.deduction_amount)}</div></div>
                  <div><div className="text-xs text-muted-foreground">Expiry</div><div className="font-medium">{monthLabel(result.opportunity.expiry_date)}</div></div>
                  <div><div className="text-xs text-muted-foreground">Booking opens</div><div className="font-medium">{monthLabel(result.opportunity.booking_open_date)}</div></div>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Deduction report</CardTitle>
              <CardDescription>Every recognized CDAS deduction and the booking calculation applied to it.</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item</TableHead>
                    <TableHead>Agency</TableHead>
                    <TableHead className="text-right">Deduction</TableHead>
                    <TableHead>Effective</TableHead>
                    <TableHead>Expiry</TableHead>
                    <TableHead>Reference</TableHead>
                    <TableHead>Months left</TableHead>
                    <TableHead>Booking opens</TableHead>
                    <TableHead>Result</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.deductions.map((row) => (
                    <TableRow key={`${row.item_code}-${row.reference_no}-${row.expiry_date}`}>
                      <TableCell className="font-medium">{row.item_code}</TableCell>
                      <TableCell>{row.agency_name}</TableCell>
                      <TableCell className="text-right">{money(row.deduction_amount)}</TableCell>
                      <TableCell>{monthLabel(row.effective_date)}</TableCell>
                      <TableCell>{monthLabel(row.expiry_date)}</TableCell>
                      <TableCell className="max-w-52 truncate" title={row.reference_no}>{row.reference_no || "—"}</TableCell>
                      <TableCell>{row.months_to_expiry}</TableCell>
                      <TableCell>{monthLabel(row.booking_open_date)}</TableCell>
                      <TableCell><Badge variant="outline">{rowResult(row)}</Badge></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <p className="text-xs text-muted-foreground">
            Booking dates are calculated from the configured company lead period and CDAS expiry data. Final lending approval remains subject to your normal affordability, payroll and credit rules.
          </p>
        </div>
      )}
    </div>
  );
}
